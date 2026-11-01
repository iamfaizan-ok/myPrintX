from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser

from .models import Document
from .serializers import DocumentSerializer, DocumentUploadSerializer
from apps.orders.models import PrintAgent, Order

class DocumentUploadView(APIView):
    """
    Customer uploads a PDF document for a specific shop identified by shop_public_id.
    Validates genuine PDF content and saves strictly in private file storage.
    """
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = DocumentUploadSerializer(data=request.data)
        if serializer.is_valid():
            doc = serializer.save()
            return Response({
                'success': True,
                'message': 'Document uploaded and securely stored in private storage.',
                'data': DocumentSerializer(doc).data
            }, status=status.HTTP_201_CREATED)
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class DocumentDetailView(APIView):
    """
    Document metadata retrieval.
    Returns metadata (page count, name, size) for active documents
    needed by customer print settings and shop order processing.
    Actual file binary download remains strictly protected in DocumentDownloadView.
    """
    permission_classes = [AllowAny]

    def get(self, request, pk):
        doc = get_object_or_404(Document, pk=pk)

        if doc.status == 'deleted':
            return Response({
                'success': False,
                'message': 'Document has expired or was removed.'
            }, status=status.HTTP_404_NOT_FOUND)

        return Response({
            'success': True,
            'data': DocumentSerializer(doc).data
        })


class DocumentDownloadView(APIView):
    """
    Secure backend streaming endpoint for private document downloads.
    Enforces strict authorization: Only shop admin or authorized PC Print Agent can retrieve file.
    Does NOT expose public URLs or filesystem paths.
    """
    permission_classes = [AllowAny]

    def get(self, request, pk):
        doc = get_object_or_404(Document, pk=pk)

        is_authorized = False
        actor = "unauthorized"

        # 1. Shop Admin authentication check (Header, Session, or query token)
        admin_token = None
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Token '):
            admin_token = auth_header.split(' ')[1]
        elif request.query_params.get('token'):
            admin_token = request.query_params.get('token')

        if admin_token:
            from rest_framework.authtoken.models import Token
            token_obj = Token.objects.filter(key=admin_token).select_related('user').first()
            if token_obj and hasattr(token_obj.user, 'owned_shop') and token_obj.user.owned_shop == doc.shop:
                is_authorized = True
                actor = f"admin:{token_obj.user.email}"
        elif request.user.is_authenticated and hasattr(request.user, 'owned_shop') and request.user.owned_shop == doc.shop:
            is_authorized = True
            actor = f"admin:{request.user.email}"


        # 2. PC Print Agent token check
        agent_token = request.headers.get('X-Agent-Token') or request.query_params.get('agent_token')
        if not is_authorized and agent_token:
            agent = PrintAgent.objects.filter(agent_token=agent_token, shop=doc.shop).first()
            if agent:
                # Also verify the document is associated with an active/authorized order
                if Order.objects.filter(document=doc, shop=doc.shop, status__in=['confirmed', 'printing', 'ready_for_pickup', 'completed']).exists():
                    is_authorized = True
                    actor = f"agent:{agent.agent_name}"

        # 3. Guest tracking token check
        tracking_token = request.query_params.get('tracking_token')
        if not is_authorized and tracking_token:
            if Order.objects.filter(document=doc, access_token=tracking_token).exists():
                is_authorized = True
                actor = "customer_guest"

        if not is_authorized:
            return Response({
                'success': False,
                'message': 'Security Rule Violation: Unauthorized attempt to download private document.'
            }, status=status.HTTP_403_FORBIDDEN)

        if not doc.file or not doc.file.storage.exists(doc.file.name):
            raise Http404("Document file not found on private storage volume.")

        # Stream file safely with Content-Disposition
        safe_filename = doc.original_name.replace('"', '')
        response = FileResponse(
            doc.file.open('rb'),
            content_type=doc.mime_type or 'application/pdf'
        )
        response['Content-Disposition'] = f'inline; filename="{safe_filename}"'
        response['X-Content-Type-Options'] = 'nosniff'
        return response
