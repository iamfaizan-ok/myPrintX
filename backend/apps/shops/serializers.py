from rest_framework import serializers
from .models import Shop

class ShopSerializer(serializers.ModelSerializer):
    qr_code_url = serializers.SerializerMethodField()

    class Meta:
        model = Shop
        fields = [
            'id', 'public_id', 'name', 'contact_phone', 
            'address', 'is_active', 'opening_hours', 
            'qr_code_image', 'qr_code_url', 'created_at'
        ]
        read_only_fields = ['id', 'public_id', 'qr_code_image', 'qr_code_url', 'created_at']

    def get_qr_code_url(self, obj):
        if obj.qr_code_image:
            return obj.qr_code_image.url
        return None

class PublicShopSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shop
        fields = ['id', 'public_id', 'name', 'contact_phone', 'address', 'is_active', 'opening_hours']
