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

class AdminSignupSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=6)
    confirm_password = serializers.CharField(write_only=True, min_length=6)
    shop_name = serializers.CharField(max_length=255)
    shop_phone = serializers.CharField(max_length=50)
    shop_address = serializers.CharField()

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value.lower()

    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        return data

    def create(self, validated_data):
        # 1. Create shop admin user
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            name=validated_data['name'],
            phone=validated_data['shop_phone'],
            role='shop_admin'
        )

        # 2. Create the associated shop
        shop = Shop.objects.create(
            owner=user,
            name=validated_data['shop_name'],
            contact_phone=validated_data['shop_phone'],
            address=validated_data['shop_address']
        )

        # 3. Auto-generate the unique shop QR code
        try:
            shop.generate_qr_code()
        except Exception:
            pass

        # 4. Generate token
        token, _ = Token.objects.get_or_create(user=user)

        return {
            'token': token.key,
            'user': user,
            'shop': shop
        }

class AdminLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        email = data.get('email', '').lower()
        password = data.get('password', '')

        user = authenticate(username=email, password=password)
        if not user:
            raise serializers.ValidationError("Invalid email or password.")

        if user.role not in ['shop_admin', 'superadmin']:
            raise serializers.ValidationError("Access denied. Admin account required.")

        token, _ = Token.objects.get_or_create(user=user)
        shop = getattr(user, 'owned_shop', None)

        return {
            'token': token.key,
            'user': user,
            'shop': shop
        }
