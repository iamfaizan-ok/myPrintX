from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.authtoken.models import Token
from .serializers import (
    AdminSignupRequestSerializer,
    AdminVerifyOTPSerializer,
    AdminResendOTPSerializer,
    AdminLoginSerializer,
    UserSerializer
)
from .services import (
    create_signup_otp,
    resend_signup_otp,
    verify_and_complete_signup
)
from apps.shops.serializers import ShopSerializer

def format_drf_errors(errors_dict) -> str:
    """
    Extracts the first user-friendly error message from DRF validation errors dictionary.
    """
    if not errors_dict:
        return 'Invalid request data.'
    for field, err_list in errors_dict.items():
        err_msg = err_list[0] if isinstance(err_list, list) and err_list else str(err_list)
        if field == 'non_field_errors':
            return str(err_msg)
        field_name = field.replace('_', ' ').capitalize()
        return f"{field_name}: {err_msg}"
    return 'Invalid request data.'


class AdminSignupRequestOTPView(APIView):
    """
    Step 1: Validates registration information and sends a 6-digit OTP code to the admin's email.
    """
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'

    def post(self, request):
        serializer = AdminSignupRequestSerializer(data=request.data)
        if serializer.is_valid():
            try:
                res = create_signup_otp(serializer.validated_data)
                return Response({
                    'success': True,
                    'message': f"A 6-digit verification code has been dispatched to {res['email']}.",
                    'data': res
                }, status=status.HTTP_200_OK)
            except ValueError as val_err:
                return Response({
                    'success': False,
                    'message': str(val_err)
                }, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                return Response({
                    'success': False,
                    'message': 'Unable to send verification code. Please check your email address and try again.'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            'success': False,
            'message': format_drf_errors(serializer.errors),
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class AdminSignupVerifyOTPView(APIView):
    """
    Step 2: Verifies the 6-digit OTP code. If correct, creates the User & Shop accounts in PostgreSQL,
    generates the authentication token, and completes registration.
    """
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'

    def post(self, request):
        serializer = AdminVerifyOTPSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            otp = serializer.validated_data['otp']

            try:
                result = verify_and_complete_signup(email, otp)
                return Response({
                    'success': True,
                    'message': 'Account and shop registered successfully! Welcome to PrintX.',
                    'data': {
                        'token': result['token'],
                        'user': UserSerializer(result['user']).data,
                        'shop': ShopSerializer(result['shop']).data if result['shop'] else None
                    }
                }, status=status.HTTP_201_CREATED)
            except ValueError as val_err:
                return Response({
                    'success': False,
                    'message': str(val_err)
                }, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                return Response({
                    'success': False,
                    'message': f"Registration verification failed: {str(e)}"
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            'success': False,
            'message': format_drf_errors(serializer.errors),
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class AdminSignupResendOTPView(APIView):
    """
    Resends a fresh 6-digit verification code to the user's email with cooldown support.
    """
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'

    def post(self, request):
        serializer = AdminResendOTPSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            try:
                res = resend_signup_otp(email)
                return Response({
                    'success': True,
                    'message': f"A fresh verification code has been dispatched to {email}.",
                    'data': res
                }, status=status.HTTP_200_OK)
            except ValueError as val_err:
                return Response({
                    'success': False,
                    'message': str(val_err)
                }, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                return Response({
                    'success': False,
                    'message': 'Unable to resend verification code. Please try again in a moment.'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            'success': False,
            'message': format_drf_errors(serializer.errors),
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class AdminLoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'

    def post(self, request):
        serializer = AdminLoginSerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data
            return Response({
                'success': True,
                'message': 'Login successful.',
                'data': {
                    'token': data['token'],
                    'user': UserSerializer(data['user']).data,
                    'shop': ShopSerializer(data['shop']).data if data['shop'] else None
                }
            }, status=status.HTTP_200_OK)
        return Response({
            'success': False,
            'message': format_drf_errors(serializer.errors),
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class AdminMeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        shop = getattr(user, 'owned_shop', None)
        return Response({
            'success': True,
            'data': {
                'user': UserSerializer(user).data,
                'shop': ShopSerializer(shop).data if shop else None
            }
        })

    def patch(self, request):
        user = request.user
        name = request.data.get('name')
        phone = request.data.get('phone')
        new_password = request.data.get('new_password')
        current_password = request.data.get('current_password')

        if name:
            user.name = name.strip()
        if phone is not None:
            user.phone = phone.strip()

        if new_password:
            if not current_password or not user.check_password(current_password):
                return Response({
                    'success': False,
                    'message': 'Current password is required and must be correct to set a new password.'
                }, status=status.HTTP_400_BAD_REQUEST)
            if len(new_password) < 6:
                return Response({
                    'success': False,
                    'message': 'New password must be at least 6 characters.'
                }, status=status.HTTP_400_BAD_REQUEST)
            user.set_password(new_password)

        user.save()
        shop = getattr(user, 'owned_shop', None)
        return Response({
            'success': True,
            'message': 'Account settings updated successfully.',
            'data': {
                'user': UserSerializer(user).data,
                'shop': ShopSerializer(shop).data if shop else None
            }
        })


class AdminLogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            Token.objects.filter(user=request.user).delete()
        except Exception:
            pass
        return Response({
            'success': True,
            'message': 'Logged out successfully.'
        }, status=status.HTTP_200_OK)
