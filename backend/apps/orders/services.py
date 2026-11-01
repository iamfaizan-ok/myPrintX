"""
PrintX Unified Print Job Dispatch Service
Enforces authoritative business rules across both printing workflows:
- Method 1: Verified Online Payment (Webhook)
- Method 2: Admin Pay OK (Counter Verification)
"""

import logging
from django.utils import timezone
from .models import Order, PrintJob, AuditLog

logger = logging.getLogger(__name__)


def dispatch_print_job(order, triggered_by, actor_user=None, notes=""):
    """
    Authoritative print job dispatcher.
    Enforces strict security, payment verification, shop isolation, and idempotency rules:

    Rules:
    1. Order must exist and document must be available.
    2. Blocked orders must NEVER be dispatched or printed.
    3. Payment must be verified ('paid') before print job creation.
    4. Idempotency: Do NOT create duplicate print jobs if an active (queued/printing)
       job already exists for this order.
    5. Completed jobs are not duplicated on repeated Pay OK.
    6. Creates comprehensive audit trail with actor, timestamp, and trigger method.
    """
    if not order:
        return False, "Order does not exist.", None

    # Security Rule: Blocked orders must NEVER print
    if order.is_blocked:
        AuditLog.objects.create(
            shop=order.shop,
            user=actor_user,
            order=order,
            action='print_dispatch_rejected',
            notes=f"Attempted print dispatch rejected: Order is blocked. Trigger: {triggered_by}"
        )
        return False, "Security Rule Violation: Blocked orders must never be printed.", None

    # Verification Rule: Never print unverified orders
    if order.payment_status != 'paid':
        return False, "Payment has not been verified. Unverified orders cannot be dispatched for printing.", None

    # Document Availability Check
    if not order.document or order.document.status == 'deleted':
        return False, "Document is missing or has been deleted from storage.", None

    # Idempotency Rule: Prevent duplicate active print jobs
    existing_active_job = PrintJob.objects.filter(
        order=order,
        status__in=['queued', 'printing']
    ).first()

    if existing_active_job:
        return True, f"Print job #{existing_active_job.id} is already active ({existing_active_job.status}). Duplicate prevented.", existing_active_job

    # Prevent duplicate prints on repeated Pay OK calls if already completed
    existing_completed_job = PrintJob.objects.filter(
        order=order,
        status='completed'
    ).first()

    if existing_completed_job and triggered_by in ['admin_pay_ok', 'online_payment_verified']:
        return True, f"Order #{order.order_number} has already been printed (Job #{existing_completed_job.id}). Duplicate prevented.", existing_completed_job

    # Create the authoritative print job for the shop's PC Print Agent
    job = PrintJob.objects.create(
        order=order,
        shop=order.shop,
        status='queued'
    )

    # Transition order status to 'confirmed' (or keep 'printing' if agent picks it up)
    if order.status in ['pending', 'confirmed']:
        order.status = 'confirmed'
        order.save(update_fields=['status', 'updated_at'])

    # Record Audit Log
    log_notes = f"Print Job #{job.id} automatically created via {triggered_by}. {notes}".strip()
    AuditLog.objects.create(
        shop=order.shop,
        user=actor_user,
        order=order,
        action='print_job_created',
        notes=log_notes
    )

    return True, f"Print job #{job.id} created and queued successfully for shop printer.", job
