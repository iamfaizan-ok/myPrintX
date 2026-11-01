import random
import uuid
from django.db import models
from django.conf import settings

def generate_order_number():
    return f"PX-{random.randint(10000, 99999)}"

def generate_access_token():
    return uuid.uuid4().hex

class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('confirmed', 'Confirmed'),
        ('printing', 'Printing in Progress'),
        ('ready_for_pickup', 'Ready for Pickup'),
        ('completed', 'Completed'),
        ('blocked', 'Blocked / Rejected'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('unpaid', 'Payment Pending'),
        ('paid', 'Paid'),
        ('refunded', 'Refunded'),
    ]

    order_number = models.CharField(max_length=50, unique=True, default=generate_order_number, db_index=True)
    access_token = models.CharField(max_length=64, blank=True, db_index=True)
    shop = models.ForeignKey('shops.Shop', on_delete=models.CASCADE, related_name='orders')


    document = models.ForeignKey('documents.Document', on_delete=models.CASCADE, related_name='orders')
    customer_name = models.CharField(max_length=255, default='Counter Customer')
    customer_phone = models.CharField(max_length=50, blank=True, null=True)
    
    # Authoritative print parameters
    copies = models.PositiveIntegerField(default=1)
    selected_pages_count = models.PositiveIntegerField(default=1)
    page_range = models.CharField(max_length=100, default='all')
    color_mode = models.CharField(max_length=20, default='bw')  # 'bw' or 'color'
    paper_size = models.CharField(max_length=20, default='A4')
    duplex = models.BooleanField(default=False)
    binding = models.CharField(max_length=20, default='none')
    
    # Financials
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    currency = models.CharField(max_length=10, default='PKR')
    payment_method = models.CharField(max_length=30, default='cash_on_pickup')
    payment_status = models.CharField(max_length=30, choices=PAYMENT_STATUS_CHOICES, default='unpaid')
    
    # Workflow status
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending')
    is_blocked = models.BooleanField(default=False)
    blocked_reason = models.TextField(blank=True, null=True)
    special_instructions = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.order_number} ({self.shop.name}) - Status: {self.status}"

    def save(self, *args, **kwargs):
        if not self.access_token:
            self.access_token = uuid.uuid4().hex
        super().save(*args, **kwargs)



# Model Alias for Spec Parity
PrintOrder = Order


class Payment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Verification'),
        ('completed', 'Completed / Verified'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='payment_record')
    shop = models.ForeignKey('shops.Shop', on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='PKR')
    method = models.CharField(max_length=50, default='cash_on_pickup')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending')
    reference_id = models.CharField(max_length=100, blank=True, null=True)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payment {self.id} for Order {self.order.order_number} ({self.status})"


class PrintAgent(models.Model):
    shop = models.ForeignKey('shops.Shop', on_delete=models.CASCADE, related_name='print_agents')
    agent_name = models.CharField(max_length=100, default='Counter PC Agent')
    agent_token = models.CharField(max_length=100, unique=True, db_index=True)
    printer_name = models.CharField(max_length=255, default='Default Printer')
    is_online = models.BooleanField(default=False)
    last_heartbeat = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.agent_name} ({self.shop.name}) - {'Online' if self.is_online else 'Offline'}"


class PrintJob(models.Model):
    STATUS_CHOICES = [
        ('queued', 'Queued for Printing'),
        ('printing', 'Printing in Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed / Paper Jam'),
    ]

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='print_jobs')
    shop = models.ForeignKey('shops.Shop', on_delete=models.CASCADE, related_name='print_jobs')
    agent = models.ForeignKey(PrintAgent, on_delete=models.SET_NULL, null=True, blank=True, related_name='jobs')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='queued')
    pages_printed = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"PrintJob #{self.id} for Order {self.order.order_number} ({self.status})"


class AuditLog(models.Model):
    shop = models.ForeignKey('shops.Shop', on_delete=models.CASCADE, related_name='audit_logs')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='audit_logs')
    action = models.CharField(max_length=50)  # 'pay_ok', 'authorize_print', 'block'
    notes = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.action} on {self.order.order_number} by {self.user} at {self.timestamp}"
