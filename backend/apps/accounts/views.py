from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.authtoken.models import Token
from .serializers import AdminSignupSerializer, AdminLoginSerializer, UserSerializer
from apps.shops.serializers import ShopSerializer

class AdminSignupView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'

    def post(self, request):
        serializer = AdminSignupSerializer(data=request.data)
        if serializer.is_valid():
            result = serializer.save()
            return Response({
                'success': True,
                'message': 'Shop and admin account created successfully.',
                'data': {
                    'token': result['token'],
                    'user': UserSerializer(result['user']).data,
                    'shop': ShopSerializer(result['shop']).data if result['shop'] else None
                }
            }, status=status.HTTP_201_CREATED)
        # Extract the exact human-readable field error
        error_details = []
        for field, err_list in serializer.errors.items():
            err_msg = err_list[0] if isinstance(err_list, list) and err_list else str(err_list)
            if field == 'non_field_errors':
                error_details.append(err_msg)
            else:
                field_name = field.replace('_', ' ').capitalize()
                error_details.append(f"{field_name}: {err_msg}")

        user_friendly_message = error_details[0] if error_details else 'Registration failed. Please check the entered information.'

        return Response({
            'success': False,
            'message': user_friendly_message,
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
            'message': 'Invalid email address or password. Please verify your credentials.',
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
            # Delete user token on logout for security
            Token.objects.filter(user=request.user).delete()
        except Exception:
            pass
        return Response({
            'success': True,
            'message': 'Logged out successfully.'
        }, status=status.HTTP_200_OK)
