from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static

# Views
from apps.accounts.views import AdminSignupView, AdminLoginView, AdminMeView, AdminLogoutView
from apps.shops.views import PublicShopDetailView, PublicShopListView, AdminShopProfileView, AdminQRGenerateView, AdminQRDetailsView
from apps.documents.views import DocumentUploadView, DocumentDetailView, DocumentDownloadView

from apps.orders.views import (
    AdminDashboardStatsView, AdminOrderListView, AdminOrderDetailView, AdminOrderPayOKView, 
    AdminOrderAuthorizePrintView, AdminOrderBlockView,
    CustomerOrderCreateView, CustomerOrderTrackView, CustomerPricingCalculateView,
    AdminAgentTokenView, AgentPollJobsView, AgentUpdateJobStatusView,
    OnlinePaymentInitiateView, OnlinePaymentWebhookView
)

urlpatterns = [
    path('admin-panel/', admin.site.urls),

    # 1. Admin Authentication
    path('api/v1/admin/auth/signup/', AdminSignupView.as_view(), name='admin_signup'),
    path('api/v1/admin/auth/login/', AdminLoginView.as_view(), name='admin_login'),
    path('api/v1/admin/auth/me/', AdminMeView.as_view(), name='admin_me'),
    path('api/v1/admin/auth/logout/', AdminLogoutView.as_view(), name='admin_logout'),

    # 2. Admin Dashboard & Order Management (Shop-Isolated)
    path('api/v1/admin/dashboard/stats/', AdminDashboardStatsView.as_view(), name='admin_dashboard_stats'),
    path('api/v1/admin/orders/', AdminOrderListView.as_view(), name='admin_orders_list'),
    path('api/v1/admin/orders/<int:pk>/', AdminOrderDetailView.as_view(), name='admin_order_detail'),
    path('api/v1/admin/orders/<int:pk>/pay-ok/', AdminOrderPayOKView.as_view(), name='admin_order_pay_ok'),
    path('api/v1/admin/orders/<int:pk>/authorize-print/', AdminOrderAuthorizePrintView.as_view(), name='admin_order_authorize_print'),
    path('api/v1/admin/orders/<int:pk>/block/', AdminOrderBlockView.as_view(), name='admin_order_block'),
    path('api/v1/admin/agent/token/', AdminAgentTokenView.as_view(), name='admin_agent_token'),

    # 3. QR Code Management
    path('api/v1/admin/qr/generate/', AdminQRGenerateView.as_view(), name='admin_qr_generate'),
    path('api/v1/admin/qr/details/', AdminQRDetailsView.as_view(), name='admin_qr_details'),

    # 4. PC Print Agent Spooling Endpoints (Shop-Isolated)
    path('api/v1/agent/jobs/poll/', AgentPollJobsView.as_view(), name='agent_poll_jobs'),
    path('api/v1/agent/jobs/<int:job_id>/status/', AgentUpdateJobStatusView.as_view(), name='agent_update_job_status'),


    # 4. Shop Management
    path('api/v1/admin/shop/profile/', AdminShopProfileView.as_view(), name='admin_shop_profile'),
    path('api/v1/shops/', PublicShopListView.as_view(), name='public_shops_list'),
    path('api/v1/shops/public/<str:public_id>/', PublicShopDetailView.as_view(), name='public_shop_detail'),

    # 5. Document Uploads & Secure Streaming
    path('api/v1/documents/upload/', DocumentUploadView.as_view(), name='document_upload'),
    path('api/v1/documents/<int:pk>/', DocumentDetailView.as_view(), name='document_detail'),
    path('api/v1/documents/<int:pk>/download/', DocumentDownloadView.as_view(), name='document_download'),


    # 6. Customer Orders & Authoritative Quotation
    path('api/v1/orders/create/', CustomerOrderCreateView.as_view(), name='customer_order_create'),
    path('api/v1/orders/track/<str:order_identifier>/', CustomerOrderTrackView.as_view(), name='customer_order_track'),
    path('api/v1/pricing/calculate/', CustomerPricingCalculateView.as_view(), name='customer_pricing_calculate'),

    # 7. Online Payment Gateways (Method 1: Webhook & Initiation)
    path('api/v1/payments/online/initiate/', OnlinePaymentInitiateView.as_view(), name='online_payment_initiate'),
    path('api/v1/payments/online/webhook/', OnlinePaymentWebhookView.as_view(), name='online_payment_webhook'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
