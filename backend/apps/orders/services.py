"""
PrintX Unified Print Job Dispatch Service
Enforces authoritative business rules across both printing workflows:
- Method 1: Verified Online Payment (Webhook)
- Method 2: Admin Pay OK (Counter Verification)
"""

import logging
from django.db import transaction
from django.utils import timezone
from .models import Order, PrintJob, AuditLog

logger = logging.getLogger(__name__)


def dispatch_print_job(order, triggered_by, actor_user=None, notes=""):
    """
    Authoritative print job dispatcher.
    Enforces strict security, payment verification, shop isolation, and idempotency rules
    within an atomic database transaction with row-level locking (select_for_update)
    to eliminate race conditions and duplicate physical prints.
    """
    if not order:
        return False, "Order does not exist.", None

    with transaction.atomic():
        # Lock the order row to serialize concurrent dispatches
        locked_order = Order.objects.select_for_update().get(id=order.id)

        # Security Rule: Blocked orders must NEVER print
        if locked_order.is_blocked:
            AuditLog.objects.create(
                shop=locked_order.shop,
                user=actor_user,
                order=locked_order,
                action='print_dispatch_rejected',
                notes=f"Attempted print dispatch rejected: Order is blocked. Trigger: {triggered_by}"
            )
            return False, "Security Rule Violation: Blocked orders must never be printed.", None

        # Verification Rule: Never print unverified orders
        if locked_order.payment_status != 'paid':
            return False, "Payment has not been verified. Unverified orders cannot be dispatched for printing.", None

        # Document Availability Check
        if not locked_order.document or locked_order.document.status == 'deleted':
            return False, "Document is missing or has been deleted from storage.", None

        # Idempotency Rule: Prevent duplicate active print jobs
        existing_active_job = PrintJob.objects.select_for_update().filter(
            order=locked_order,
            status__in=['queued', 'printing']
        ).first()

        if existing_active_job:
            return True, f"Print job #{existing_active_job.id} is already active ({existing_active_job.status}). Duplicate prevented.", existing_active_job

        # Prevent duplicate prints on repeated Pay OK calls if already completed
        existing_completed_job = PrintJob.objects.filter(
            order=locked_order,
            status='completed'
        ).first()

        if existing_completed_job and triggered_by in ['admin_pay_ok', 'online_payment_verified']:
            return True, f"Order #{locked_order.order_number} has already been printed (Job #{existing_completed_job.id}). Duplicate prevented.", existing_completed_job

        # Create the authoritative print job for the shop's PC Print Agent
        job = PrintJob.objects.create(
            order=locked_order,
            shop=locked_order.shop,
            status='queued'
        )

        # Transition order status to 'confirmed' (or keep 'printing' if agent picks it up)
        if locked_order.status in ['pending', 'confirmed']:
            locked_order.status = 'confirmed'
            locked_order.save(update_fields=['status', 'updated_at'])

        # Record Audit Log
        log_notes = f"Print Job #{job.id} automatically created via {triggered_by}. {notes}".strip()
        AuditLog.objects.create(
            shop=locked_order.shop,
            user=actor_user,
            order=locked_order,
            action='print_job_created',
            notes=log_notes
        )

        return True, f"Print job #{job.id} created and queued successfully for shop printer.", job
