from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404
from .models import Shop
from .serializers import ShopSerializer, PublicShopSerializer

class PublicShopDetailView(APIView):
    """
    Public endpoint: Customer scans QR code -> frontend queries shop by public_id
    """
    permission_classes = [AllowAny]

    def get(self, request, public_id):
        shop = get_object_or_404(Shop, public_id=public_id, is_active=True)
        return Response({
            'success': True,
            'data': PublicShopSerializer(shop).data
        })

class PublicShopListView(APIView):
    """
    Lists active shops for customer discovery fallback
    """
    permission_classes = [AllowAny]

    def get(self, request):
        shops = Shop.objects.filter(is_active=True)
        return Response({
            'success': True,
            'data': PublicShopSerializer(shops, many=True).data
        })

class AdminShopProfileView(APIView):
    """
    Shop admin views and updates their own shop details
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        shop = getattr(request.user, 'owned_shop', None)
        if not shop:
            return Response({'success': False, 'message': 'No shop associated with this admin.'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'success': True, 'data': ShopSerializer(shop).data})

    def patch(self, request):
        shop = getattr(request.user, 'owned_shop', None)
        if not shop:
            return Response({'success': False, 'message': 'No shop associated with this admin.'}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = ShopSerializer(shop, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({'success': True, 'message': 'Shop profile updated.', 'data': serializer.data})
        return Response({'success': False, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

def resolve_frontend_url(request):
    """
    Dynamically determines the appropriate customer frontend URL for the shop's QR code.
    Supports explicitly configured URLs (env/payload) and auto-detects LAN / Wi-Fi IP.
    """
    import os
    custom_url = None
    if hasattr(request, 'data') and isinstance(request.data, dict):
        custom_url = request.data.get('frontend_url')
    if not custom_url and hasattr(request, 'query_params'):
        custom_url = request.query_params.get('frontend_url')
    if not custom_url:
        custom_url = os.environ.get('CUSTOMER_FRONTEND_URL')

    if not custom_url:
        host = request.META.get('HTTP_X_FORWARDED_HOST') or request.get_host()
        host_name = host.split(':')[0]
        if host_name in ('localhost', '127.0.0.1') or any(host_name.startswith(p) for p in ('192.168.', '10.', '172.')):
            custom_url = f"http://{host_name}:3000/pages/upload.html"
        else:
            scheme = 'https' if request.is_secure() else 'http'
            custom_url = f"{scheme}://{host}/pages/upload.html"

    # Normalize url path
    if 'upload.html' not in custom_url:
        custom_url = custom_url.rstrip('/') + '/pages/upload.html'

    return custom_url


class AdminQRGenerateView(APIView):
    """
    Generates or retrieves unique shop QR code for currently authenticated shop
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        shop = getattr(request.user, 'owned_shop', None)
        if not shop:
            return Response({'success': False, 'message': 'No shop associated with this admin.'}, status=status.HTTP_404_NOT_FOUND)

        target_base_url = resolve_frontend_url(request)
        qr_url = shop.generate_qr_code(base_url=target_base_url)
        target_customer_url = f"{target_base_url}?shop={shop.public_id}"

        return Response({
            'success': True,
            'message': 'Shop QR Code generated successfully.',
            'data': {
                'public_id': shop.public_id,
                'shop_name': shop.name,
                'qr_code_url': qr_url,
                'scan_target_url': target_customer_url
            }
        })

class AdminQRDetailsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        shop = getattr(request.user, 'owned_shop', None)
        if not shop:
            return Response({'success': False, 'message': 'No shop found.'}, status=status.HTTP_404_NOT_FOUND)

        target_base_url = resolve_frontend_url(request)
        if not shop.qr_code_image:
            shop.generate_qr_code(base_url=target_base_url)

        target_customer_url = f"{target_base_url}?shop={shop.public_id}"
        return Response({
            'success': True,
            'data': {
                'public_id': shop.public_id,
                'shop_name': shop.name,
                'qr_code_url': shop.qr_code_image.url if shop.qr_code_image else None,
                'scan_target_url': target_customer_url
            }
        })
