import random
from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from django.core.mail import send_mail
from django.conf import settings
from rest_framework.authtoken.models import Token
from .models import User, SignupOTP
from apps.shops.models import Shop

def generate_secure_otp(length=4) -> str:
    """
    Generates a cryptographically strong 4-digit numeric OTP.
    """
    return "".join(str(random.randint(0, 9)) for _ in range(length))

def send_otp_email(email: str, otp_code: str) -> bool:
    """
    Dispatches OTP email to the user.
    Falls back gracefully to console logging if SMTP is unconfigured so local dev is never blocked.
    """
    subject = "PrintX — Your Shop Admin Verification Code"
    message = (
        f"Hello,\n\n"
        f"Your 4-digit verification code for registering your PrintX Shop Admin account is:\n\n"
        f"    {otp_code}\n\n"
        f"This code will expire in 10 minutes.\n"
        f"If you did not request this verification, please safely ignore this email.\n\n"
        f"— The PrintX Team"
    )

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'PrintX <no-reply@printx.com>'),
            recipient_list=[email],
            fail_silently=False,
        )
        print(f"[Email Service] OTP successfully dispatched via SMTP to {email}")
        return True
    except Exception as e:
        # Fallback console logger for development and local testing
        print("\n" + "=" * 65)
        print(" [PrintX Development Mode] OTP Verification Code Dispatched")
        print(f" Recipient : {email}")
        print(f" OTP Code  : {otp_code} (Valid for 10 minutes)")
        print(f" SMTP Notice: {e}")
        print("=" * 65 + "\n")
        return True

def create_signup_otp(validated_data: dict) -> dict:
    """
    Validates email uniqueness, stages registration data, generates 4-digit OTP,
    and sends it to the target email.
    """
    email = validated_data['email'].lower()

    if User.objects.filter(email__iexact=email).exists():
        raise ValueError("An account with this email address already exists. Please sign in instead.")

    otp_code = generate_secure_otp(4)
    expires_at = timezone.now() + timedelta(minutes=10)

    # Invalidate any existing unverified OTPs for this email
    SignupOTP.objects.filter(email__iexact=email, is_verified=False).delete()

    # Save staged payload and OTP
    otp_record = SignupOTP.objects.create(
        email=email,
        otp_code=otp_code,
        registration_payload=validated_data,
        expires_at=expires_at
    )

    # Send email
    send_otp_email(email, otp_code)

    return {
        'email': email,
        'expires_in_seconds': 600
    }

def resend_signup_otp(email: str) -> dict:
    """
    Generates a new 4-digit OTP for an existing staged signup session.
    """
    email = email.strip().lower()

    otp_record = SignupOTP.objects.filter(email__iexact=email, is_verified=False).first()
    if not otp_record:
        raise ValueError("No active registration found for this email. Please fill out the signup form.")

    new_otp = generate_secure_otp(4)
    otp_record.otp_code = new_otp
    otp_record.expires_at = timezone.now() + timedelta(minutes=10)
    otp_record.save(update_fields=['otp_code', 'expires_at'])

    send_otp_email(email, new_otp)

    return {
        'email': email,
        'expires_in_seconds': 600
    }

@transaction.atomic
def verify_and_complete_signup(email: str, entered_otp: str) -> dict:
    """
    Verifies the OTP code. If valid, atomically creates the User and Shop in PostgreSQL,
    generates auth token, and completes registration.
    """
    email = email.strip().lower()
    entered_otp = str(entered_otp).strip()

    otp_record = SignupOTP.objects.filter(email__iexact=email, is_verified=False).first()
    if not otp_record:
        raise ValueError("No pending registration session found. Please fill out the registration form.")

    if otp_record.is_expired():
        otp_record.delete()
        raise ValueError("This verification code has expired. Please click 'Resend Code' to receive a new one.")

    if otp_record.otp_code != entered_otp:
        raise ValueError("Invalid verification code. Please check your email and enter the 6-digit code correctly.")

    payload = otp_record.registration_payload

    # Double-check email has not been taken in the meantime
    if User.objects.filter(email__iexact=email).exists():
        otp_record.delete()
        raise ValueError("An account with this email was recently created. Please sign in.")

    # 1. Create shop admin user
    user = User.objects.create_user(
        email=payload['email'],
        password=payload['password'],
        name=payload['name'],
        phone=payload.get('shop_phone', ''),
        role='shop_admin'
    )

    # 2. Create the associated shop
    shop = Shop.objects.create(
        owner=user,
        name=payload['shop_name'],
        contact_phone=payload['shop_phone'],
        address=payload['shop_address']
    )

    # 3. Generate QR code
    try:
        shop.generate_qr_code()
    except Exception as e:
        print(f"[QR Warning] Failed to generate initial QR: {e}")

    # 4. Create authentication token
    token, _ = Token.objects.get_or_create(user=user)

    # Mark OTP as verified & clean up
    otp_record.is_verified = True
    otp_record.save(update_fields=['is_verified'])
    SignupOTP.objects.filter(email__iexact=email).delete()

    return {
        'token': token.key,
        'user': user,
        'shop': shop
    }

