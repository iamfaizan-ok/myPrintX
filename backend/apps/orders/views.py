import os
import uuid
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .models import Order, AuditLog, Payment, PrintAgent, PrintJob
from .serializers import OrderSerializer, OrderCreateSerializer, PrintJobSerializer, PrintAgentSerializer
from .services import dispatch_print_job
from apps.documents.models import Document


class AdminDashboardStatsView(APIView):
    """
    Dynamically loads real statistics for the authenticated admin's own shop only.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        shop = getattr(request.user, 'owned_shop', None)
        if not shop:
            return Response({'success': False, 'message': 'Admin shop not found.'}, status=status.HTTP_404_NOT_FOUND)

        orders_qs = Order.objects.filter(shop=shop)
        
        total_orders = orders_qs.count()
        pending_orders = orders_qs.filter(status='pending').count()
        payment_pending = orders_qs.filter(payment_status='unpaid').count()
        completed_orders = orders_qs.filter(status='completed').count()
        blocked_orders = orders_qs.filter(is_blocked=True).count()
        
        recent_orders = orders_qs[:6]

        return Response({
            'success': True,
            'data': {
                'shop_name': shop.name,
                'public_id': shop.public_id,
                'total_orders': total_orders,
                'pending_orders': pending_orders,
                'payment_pending_orders': payment_pending,
                'completed_orders': completed_orders,
                'blocked_orders': blocked_orders,
                'recent_orders': OrderSerializer(recent_orders, many=True).data
            }
        })

class AdminOrderListView(APIView):
    """
    List orders belonging strictly to the currently authenticated admin's shop.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        shop = getattr(request.user, 'owned_shop', None)
        if not shop:
            return Response({'success': False, 'message': 'Admin shop not found.'}, status=status.HTTP_404_NOT_FOUND)

        orders_qs = Order.objects.filter(shop=shop)
        
        status_filter = request.query_params.get('status', '').strip()
        if status_filter:
            if status_filter == 'blocked':
                orders_qs = orders_qs.filter(is_blocked=True)
            elif status_filter == 'payment_pending':
                orders_qs = orders_qs.filter(payment_status='unpaid')
            else:
                orders_qs = orders_qs.filter(status=status_filter)

        return Response({
            'success': True,
            'data': OrderSerializer(orders_qs, many=True).data
        })

class AdminOrderPayOKView(APIView):
    """
    Method 2: Admin Pay OK -> Automatic Printing.
    Validates order, payment status, shop ownership and document availability.
    Records payment approval, admin ID and timestamp.
    Automatically creates a print job for the shop's Print Agent.
    Admin does NOT need to click another print button.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        shop = getattr(request.user, 'owned_shop', None)
        if not shop:
            return Response({'success': False, 'message': 'Admin shop not found.'}, status=status.HTTP_404_NOT_FOUND)

        order = get_object_or_404(Order, pk=pk, shop=shop)

        if order.is_blocked:
            return Response({
                'success': False,
                'message': 'Cannot approve payment or print for a blocked order.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # 1. Update order payment status
        order.payment_status = 'paid'
        if order.status == 'pending':
            order.status = 'confirmed'
        order.save(update_fields=['payment_status', 'status', 'updated_at'])

        # 2. Record payment approval with admin ID and timestamp
        Payment.objects.update_or_create(
            order=order,
            defaults={
                'shop': shop,
                'amount': order.total_price,
                'currency': order.currency,
                'method': order.payment_method,
                'status': 'completed',
                'verified_by': request.user,
                'verified_at': timezone.now()
            }
        )

        AuditLog.objects.create(
            shop=shop,
            user=request.user,
            order=order,
            action='pay_ok',
            notes=f"Payment of {order.currency} {order.total_price} verified by admin {request.user.email}."
        )

        # 3. Automatically dispatch print job for shop PC Print Agent (Method 2)
        success, msg, job = dispatch_print_job(
            order=order,
            triggered_by='admin_pay_ok',
            actor_user=request.user,
            notes=f"Triggered by admin {request.user.email} Pay OK."
        )

        return Response({
            'success': True,
            'message': f"Payment approved. {msg}",
            'data': OrderSerializer(order).data,
            'print_job_id': job.id if job else None
        })


class AdminOrderAuthorizePrintView(APIView):
    """
    Authorize manual printing / reprint for an order.
    Enforces rule: Blocked orders must NEVER be printed.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        shop = getattr(request.user, 'owned_shop', None)
        if not shop:
            return Response({'success': False, 'message': 'Admin shop not found.'}, status=status.HTTP_404_NOT_FOUND)

        order = get_object_or_404(Order, pk=pk, shop=shop)

        if order.is_blocked:
            return Response({
                'success': False,
                'message': 'Security Rule Violation: Blocked orders cannot be authorized for printing.'
            }, status=status.HTTP_400_BAD_REQUEST)

        success, msg, job = dispatch_print_job(
            order=order,
            triggered_by='admin_manual_authorize',
            actor_user=request.user,
            notes=f"Manual authorization by admin {request.user.email}."
        )

        if not success:
            return Response({'success': False, 'message': msg}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'success': True,
            'message': msg,
            'data': OrderSerializer(order).data,
            'print_job_id': job.id if job else None
        })

class AdminOrderBlockView(APIView):
    """
    Block an inappropriate or unauthorized order.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        shop = getattr(request.user, 'owned_shop', None)
        order = get_object_or_404(Order, pk=pk, shop=shop)

        reason = request.data.get('reason', 'Blocked by shop administrator.')
        order.is_blocked = True
        order.status = 'blocked'
        order.blocked_reason = reason
        order.save(update_fields=['is_blocked', 'status', 'blocked_reason', 'updated_at'])

        AuditLog.objects.create(
            shop=shop,
            user=request.user,
            order=order,
            action='order_blocked',
            notes=f"Order blocked: {reason}"
        )

        return Response({
            'success': True,
            'message': 'Order has been blocked.',
            'data': OrderSerializer(order).data
        })

class CustomerOrderCreateView(APIView):
    """
    Customer places a print order for a specific shop (via QR scan)
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = OrderCreateSerializer(data=request.data)
        if serializer.is_valid():
            order = serializer.save()
            return Response({
                'success': True,
                'message': 'Order submitted successfully to the print queue.',
                'data': OrderSerializer(order).data
            }, status=status.HTTP_201_CREATED)
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

class CustomerOrderTrackView(APIView):
    """
    Secure guest-order tracking view.
    Enforces authorization to prevent guessing of Order IDs.
    Allows access if:
    1. Authenticated shop admin whose shop owns this order.
    2. Customer provides the matching access_token generated upon submission.
    """
    permission_classes = [AllowAny]

    def get(self, request, order_identifier):
        order = Order.objects.filter(order_number__iexact=order_identifier).first()
        if not order and order_identifier.isdigit():
            order = Order.objects.filter(id=int(order_identifier)).first()

        if not order:
            return Response({'success': False, 'message': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)

        is_authorized = False
        if request.user.is_authenticated and hasattr(request.user, 'owned_shop') and request.user.owned_shop == order.shop:
            is_authorized = True

        provided_token = request.query_params.get('token') or request.headers.get('X-Access-Token')
        if provided_token and provided_token == order.access_token:
            is_authorized = True

        if not is_authorized:
            return Response({
                'success': False,
                'message': 'Security Protection: Order tracking requires a valid secret access token.'
            }, status=status.HTTP_403_FORBIDDEN)

        return Response({
            'success': True,
            'data': OrderSerializer(order).data
        })


class CustomerPricingCalculateView(APIView):
    """
    Live authoritative quotation calculation
    """
    permission_classes = [AllowAny]

    def post(self, request):
        document_id = request.data.get('document_id')
        copies = int(request.data.get('copies', 1))
        page_range = request.data.get('page_range', 'all')
        color_mode = request.data.get('color_mode', 'bw')
        paper_size = request.data.get('paper_size', 'A4')
        duplex = bool(request.data.get('duplex', False))
        binding = request.data.get('binding', 'none')

        doc = Document.objects.filter(id=document_id).first()
        total_doc_pages = doc.total_pages if doc else 1

        selected_pages = total_doc_pages
        if page_range and page_range.lower() != 'all':
            try:
                parts = [p.strip() for p in page_range.split(',') if p.strip()]
                count = 0
                for part in parts:
                    if '-' in part:
                        s, e = map(int, part.split('-'))
                        count += max(0, min(total_doc_pages, e) - max(1, s) + 1)
                    else:
                        num = int(part)
                        if 1 <= num <= total_doc_pages:
                            count += 1
                if count > 0:
                    selected_pages = count
            except Exception:
                selected_pages = total_doc_pages

        # PKR live pricing: 1 B&W copy = Rs. 10, 1 Color copy = Rs. 20
        base_rate = 20.0 if color_mode == 'color' else 10.0
        paper_mult = 1.5 if paper_size == 'A3' else 1.0
        pages_subtotal = (base_rate * paper_mult) * selected_pages * copies
        if duplex and selected_pages > 1:
            pages_subtotal *= 0.90

        binding_rates = {'none': 0.0, 'staple': 10.0, 'spiral': 50.0, 'hardcover': 150.0}
        binding_fee = binding_rates.get(binding, 0.0) * copies
        subtotal = pages_subtotal + binding_fee
        total_price = round(subtotal, 2)

        return Response({
            'success': True,
            'data': {
                'totalPagesInDoc': total_doc_pages,
                'selectedPagesCount': selected_pages,
                'copies': copies,
                'ratePerPage': round(base_rate * paper_mult, 2),
                'pagesSubtotal': round(pages_subtotal, 2),
                'bindingFee': round(binding_fee, 2),
                'subtotal': round(subtotal, 2),
                'tax': 0.0,
                'totalPrice': total_price,
                'currency': 'PKR'
            }
        })


class OnlinePaymentInitiateView(APIView):
    """
    Method 1: Customer initiates online payment.
    Checks gateway integration. If credentials unavailable, returns pending integration status.
    Never simulates successful payments without real gateway.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        order_number = request.data.get('order_number')
        token = request.data.get('token')

        order = Order.objects.filter(order_number=order_number).first()
        if not order:
            return Response({'success': False, 'message': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)

        if order.access_token and token and order.access_token != token:
            return Response({'success': False, 'message': 'Security: Invalid order access token.'}, status=status.HTTP_403_FORBIDDEN)

        if order.is_blocked:
            return Response({'success': False, 'message': 'Cannot initiate payment for a blocked order.'}, status=status.HTTP_400_BAD_REQUEST)

        # Verify gateway configuration
        stripe_key = os.environ.get('STRIPE_SECRET_KEY')
        jazzcash_key = os.environ.get('JAZZCASH_MERCHANT_ID')

        if not stripe_key and not jazzcash_key:
            return Response({
                'success': False,
                'status': 'pending_integration',
                'message': 'Online payment gateway is pending integration. Please select Cash on Shop / Counter payment or contact shop operator.',
                'order_number': order.order_number,
                'amount': order.total_price,
                'currency': order.currency
            }, status=status.HTTP_501_NOT_IMPLEMENTED)

        return Response({
            'success': True,
            'status': 'checkout_ready',
            'checkout_url': f"https://checkout.stripe.com/pay/{order.order_number}",
            'order_number': order.order_number
        })


class OnlinePaymentWebhookView(APIView):
    """
    Method 1: Trusted Gateway Webhook / Callback.
    Verifies gateway signature/token. Never trusts unverified frontend callbacks.
    On valid verified payment:
    1. Records Payment status='completed', transaction_id.
    2. Marks order payment_status='paid'.
    3. Automatically creates and dispatches PrintJob to shop Print Agent.
    On failed/unverified:
    Rejects request, does NOT create any print job.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        webhook_secret = os.environ.get('PAYMENT_WEBHOOK_SECRET', 'printx_secure_gateway_webhook_secret_2026')
        provided_sig = request.headers.get('X-Gateway-Signature') or request.headers.get('X-Webhook-Secret')

        # 1. Signature / Authorization Verification
        if not provided_sig or provided_sig != webhook_secret:
            return Response({
                'success': False,
                'message': 'Unauthorized: Invalid or missing gateway webhook signature.'
            }, status=status.HTTP_401_UNAUTHORIZED)

        payload = request.data
        order_number = payload.get('order_number')
        event_type = payload.get('event_type')  # e.g. 'payment.succeeded', 'payment.failed'
        transaction_id = payload.get('transaction_id', f"txn_{uuid.uuid4().hex[:12]}")
        gateway_name = payload.get('gateway', 'online_gateway')

        order = Order.objects.filter(order_number=order_number).first()
        if not order:
            return Response({'success': False, 'message': f'Order {order_number} not found.'}, status=status.HTTP_404_NOT_FOUND)

        # 2. Handle failed / unverified payments -> NEVER PRINT
        if event_type != 'payment.succeeded':
            Payment.objects.update_or_create(
                order=order,
                defaults={
                    'shop': order.shop,
                    'amount': order.total_price,
                    'currency': order.currency,
                    'method': 'online',
                    'status': 'failed',
                    'reference_id': transaction_id
                }
            )
            AuditLog.objects.create(
                shop=order.shop,
                order=order,
                action='online_payment_failed',
                notes=f"Gateway reported payment failed ({event_type}). Transaction: {transaction_id}. No print job created."
            )
            return Response({
                'success': False,
                'message': f"Payment failed ({event_type}). No print job created."
            }, status=status.HTTP_400_BAD_REQUEST)

        # 3. Security Rule: Blocked orders must NEVER print even if payment succeeded
        if order.is_blocked:
            AuditLog.objects.create(
                shop=order.shop,
                order=order,
                action='online_payment_blocked',
                notes=f"Online payment succeeded but order is blocked. No print job created. Transaction: {transaction_id}"
            )
            return Response({
                'success': False,
                'message': 'Security Rule: Order is blocked. Payment received but automatic print aborted.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # 4. Verified Payment: update order & payment record
        order.payment_status = 'paid'
        order.payment_method = 'online'
        if order.status == 'pending':
            order.status = 'confirmed'
        order.save(update_fields=['payment_status', 'payment_method', 'status', 'updated_at'])

        Payment.objects.update_or_create(
            order=order,
            defaults={
                'shop': order.shop,
                'amount': order.total_price,
                'currency': order.currency,
                'method': 'online',
                'status': 'completed',
                'reference_id': transaction_id,
                'verified_at': timezone.now()
            }
        )

        # 5. Method 1: Automatically dispatch print job!
        success, msg, job = dispatch_print_job(
            order=order,
            triggered_by='online_payment_verified',
            notes=f"Gateway: {gateway_name}, Transaction: {transaction_id}"
        )

        return Response({
            'success': True,
            'message': f'Payment verified. {msg}',
            'order_number': order.order_number,
            'print_job_id': job.id if job else None
        }, status=status.HTTP_200_OK)


class AdminAgentTokenView(APIView):
    """
    Shop admin views or provisions their PC Print Agent pairing token.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        shop = getattr(request.user, 'owned_shop', None)
        if not shop:
            return Response({'success': False, 'message': 'Admin shop not found.'}, status=status.HTTP_404_NOT_FOUND)

        agent = PrintAgent.objects.filter(shop=shop).first()
        if not agent:
            token = f"agt_{uuid.uuid4().hex}"
            agent = PrintAgent.objects.create(
                shop=shop,
                agent_name=f"{shop.name} Print Agent",
                agent_token=token
            )

        return Response({
            'success': True,
            'data': PrintAgentSerializer(agent).data
        })

    def post(self, request):
        """Regenerate agent token"""
        shop = getattr(request.user, 'owned_shop', None)
        if not shop:
            return Response({'success': False, 'message': 'Admin shop not found.'}, status=status.HTTP_404_NOT_FOUND)

        new_token = f"agt_{uuid.uuid4().hex}"
        agent, _ = PrintAgent.objects.get_or_create(shop=shop)
        agent.agent_token = new_token
        agent.save(update_fields=['agent_token'])

        return Response({
            'success': True,
            'message': 'PC Print Agent token regenerated.',
            'data': PrintAgentSerializer(agent).data
        })


class AgentPollJobsView(APIView):
    """
    PC Print Agent polls for queued print jobs strictly for its authenticated shop.
    Agent provides authentication token via header 'X-Agent-Token'.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        token = request.headers.get('X-Agent-Token') or request.query_params.get('token')
        if not token:
            return Response({'success': False, 'message': 'Agent authentication token required.'}, status=status.HTTP_401_UNAUTHORIZED)

        agent = PrintAgent.objects.filter(agent_token=token).first()
        if not agent:
            return Response({'success': False, 'message': 'Invalid agent token.'}, status=status.HTTP_401_UNAUTHORIZED)

        # Heartbeat update
        agent.is_online = True
        agent.last_heartbeat = timezone.now()
        agent.save(update_fields=['is_online', 'last_heartbeat'])

        # Strict Shop Isolation: only retrieve queued jobs for this agent's shop
        jobs = PrintJob.objects.filter(shop=agent.shop, status='queued').order_by('created_at')

        return Response({
            'success': True,
            'shop_name': agent.shop.name,
            'jobs_count': jobs.count(),
            'data': PrintJobSerializer(jobs, many=True).data
        })


class AgentUpdateJobStatusView(APIView):
    """
    PC Print Agent updates execution status of a print job.
    Enforces strict shop isolation: Agent can only update jobs belonging to its shop.
    """
    permission_classes = [AllowAny]

    def post(self, request, job_id):
        token = request.headers.get('X-Agent-Token')
        if not token:
            return Response({'success': False, 'message': 'Agent token required.'}, status=status.HTTP_401_UNAUTHORIZED)

        agent = PrintAgent.objects.filter(agent_token=token).first()
        if not agent:
            return Response({'success': False, 'message': 'Invalid agent token.'}, status=status.HTTP_401_UNAUTHORIZED)

        # Validate that the job exists AND belongs strictly to the agent's shop
        job = get_object_or_404(PrintJob, id=job_id, shop=agent.shop)

        new_status = request.data.get('status')  # 'printing', 'completed', 'failed'
        pages_printed = request.data.get('pages_printed', job.pages_printed)
        error_msg = request.data.get('error_message', '')

        if new_status in dict(PrintJob.STATUS_CHOICES):
            job.status = new_status
            job.pages_printed = int(pages_printed)
            job.agent = agent

            if new_status == 'printing' and not job.started_at:
                job.started_at = timezone.now()
            elif new_status == 'completed':
                job.completed_at = timezone.now()
                # Update parent Order status to ready_for_pickup
                job.order.status = 'ready_for_pickup'
                job.order.save(update_fields=['status', 'updated_at'])
            elif new_status == 'failed':
                job.error_message = error_msg

            job.save()

            AuditLog.objects.create(
                shop=agent.shop,
                order=job.order,
                action='agent_status_update',
                notes=f"Print Agent reported job #{job.id} status as '{new_status}'."
            )

            return Response({
                'success': True,
                'message': f"Job #{job.id} updated to {new_status}.",
                'data': PrintJobSerializer(job).data
            })

        return Response({'success': False, 'message': 'Invalid status choice.'}, status=status.HTTP_400_BAD_REQUEST)

