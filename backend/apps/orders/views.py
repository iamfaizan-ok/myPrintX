import uuid
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .models import Order, AuditLog, Payment, PrintAgent, PrintJob
from .serializers import OrderSerializer, OrderCreateSerializer, PrintJobSerializer, PrintAgentSerializer
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
    Approve cash payment at the counter.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        shop = getattr(request.user, 'owned_shop', None)
        order = get_object_or_404(Order, pk=pk, shop=shop)

        if order.is_blocked:
            return Response({
                'success': False,
                'message': 'Cannot approve payment for a blocked order.'
            }, status=status.HTTP_400_BAD_REQUEST)

        order.payment_status = 'paid'
        if order.status == 'pending':
            order.status = 'confirmed'
        order.save(update_fields=['payment_status', 'status', 'updated_at'])

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
            notes=f"Cash payment of ${order.total_price} verified at shop counter."
        )

        return Response({
            'success': True,
            'message': 'Payment approved successfully.',
            'data': OrderSerializer(order).data
        })

class AdminOrderAuthorizePrintView(APIView):
    """
    Authorize printing for an order.
    Enforces rule: Blocked orders must NEVER be printed.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        shop = getattr(request.user, 'owned_shop', None)
        order = get_object_or_404(Order, pk=pk, shop=shop)

        if order.is_blocked:
            return Response({
                'success': False,
                'message': 'Security Rule Violation: Blocked orders cannot be authorized for printing.'
            }, status=status.HTTP_400_BAD_REQUEST)

        order.status = 'printing'
        order.save(update_fields=['status', 'updated_at'])

        # Create or queue PrintJob for PC Print Agent
        job, _ = PrintJob.objects.get_or_create(
            order=order,
            shop=shop,
            defaults={'status': 'queued'}
        )
        if job.status in ['failed', 'completed']:
            job.status = 'queued'
            job.save(update_fields=['status'])

        AuditLog.objects.create(
            shop=shop,
            user=request.user,
            order=order,
            action='authorize_print',
            notes=f"Print job #{job.id} authorized and queued for shop printer spooler."
        )


        return Response({
            'success': True,
            'message': 'Order authorized for printing.',
            'data': OrderSerializer(order).data
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

        base_rate = 0.50 if color_mode == 'color' else 0.10
        paper_mult = 1.8 if paper_size == 'A3' else 1.0
        pages_subtotal = (base_rate * paper_mult) * selected_pages * copies
        if duplex and selected_pages > 1:
            pages_subtotal *= 0.90

        binding_rates = {'none': 0.0, 'staple': 0.50, 'spiral': 3.00, 'hardcover': 8.00}
        binding_fee = binding_rates.get(binding, 0.0) * copies
        subtotal = pages_subtotal + binding_fee
        tax = subtotal * 0.08
        total_price = round(subtotal + tax, 2)

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
                'tax': round(tax, 2),
                'totalPrice': total_price,
                'currency': 'USD'
            }
        })


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

