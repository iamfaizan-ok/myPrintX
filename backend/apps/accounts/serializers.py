from rest_framework import serializers
from django.contrib.auth import authenticate
from rest_framework.authtoken.models import Token
from .models import User
from apps.shops.models import Shop

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'name', 'role', 'phone', 'created_at']
        read_only_fields = ['id', 'created_at']


class AdminSignupRequestSerializer(serializers.Serializer):
    """
    Validates initial shop admin signup data before issuing email OTP.
    """
    name = serializers.CharField(max_length=255, error_messages={'required': 'Full name is required.'})
    email = serializers.EmailField(error_messages={'required': 'Email address is required.'})
    password = serializers.CharField(write_only=True, min_length=6, error_messages={'min_length': 'Password must be at least 6 characters.'})
    confirm_password = serializers.CharField(write_only=True, min_length=6)
    shop_name = serializers.CharField(max_length=255, error_messages={'required': 'Shop name is required.'})
    shop_phone = serializers.CharField(max_length=50, error_messages={'required': 'Shop contact phone is required.'})
    shop_address = serializers.CharField(error_messages={'required': 'Shop physical address is required.'})

    def validate_email(self, value):
        normalized = value.strip().lower()
        if User.objects.filter(email__iexact=normalized).exists():
            raise serializers.ValidationError("An account with this email address already exists. Please sign in.")
        return normalized

    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match. Please re-enter."})
        return data


class AdminVerifyOTPSerializer(serializers.Serializer):
    """
    Validates OTP submission from the short verification screen.
    """
    email = serializers.EmailField(error_messages={'required': 'Email address is required.'})
    otp = serializers.CharField(min_length=4, max_length=4, error_messages={
        'required': 'Please enter the 4-digit verification code.',
        'min_length': 'Verification code must be exactly 4 digits.',
        'max_length': 'Verification code must be exactly 4 digits.'
    })

    def validate_email(self, value):
        return value.strip().lower()

    def validate_otp(self, value):
        clean_otp = value.strip()
        if not clean_otp.isdigit():
            raise serializers.ValidationError("Verification code must contain digits only.")
        return clean_otp


class AdminResendOTPSerializer(serializers.Serializer):
    """
    Validates request to resend a fresh verification code.
    """
    email = serializers.EmailField(error_messages={'required': 'Email address is required.'})

    def validate_email(self, value):
        return value.strip().lower()


class AdminLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')

        user = authenticate(username=email, password=password)
        if not user:
            raise serializers.ValidationError("Invalid email address or password. Please verify your credentials.")

        if user.role not in ['shop_admin', 'superadmin']:
            raise serializers.ValidationError("Access denied. A shop administrator account is required.")

        token, _ = Token.objects.get_or_create(user=user)
        shop = getattr(user, 'owned_shop', None)

        return {
            'token': token.key,
            'user': user,
            'shop': shop
        }
