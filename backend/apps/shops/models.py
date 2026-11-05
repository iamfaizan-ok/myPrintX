import uuid
import qrcode
from io import BytesIO
from django.db import models
from django.conf import settings
from django.core.files.base import ContentFile

def generate_shop_public_id():
    return f"shp_{uuid.uuid4().hex[:10]}"

class Shop(models.Model):
    public_id = models.CharField(max_length=50, unique=True, default=generate_shop_public_id, db_index=True)
    owner = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='owned_shop')
    name = models.CharField(max_length=255)
    contact_phone = models.CharField(max_length=50)
    address = models.TextField()
    is_active = models.BooleanField(default=True)
    opening_hours = models.CharField(max_length=100, default='08:00 - 20:00')
    qr_code_image = models.ImageField(upload_to='qrcodes/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.public_id})"

    def generate_qr_code(self, base_url=None):
        """
        Generates and saves a high-resolution PNG QR code pointing directly to the customer upload page for this shop.
        """
        import os
        if not base_url:
            base_url = os.environ.get('CUSTOMER_FRONTEND_URL', 'http://localhost:3000/pages/upload.html')
        target_url = f"{base_url}?shop={self.public_id}"
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=3,
        )
        qr.add_data(target_url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="#0F172A", back_color="#FFFFFF")
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        file_name = f"qr_{self.public_id}.png"

        self.qr_code_image.save(file_name, ContentFile(buffer.getvalue()), save=False)
        self.save(update_fields=['qr_code_image', 'updated_at'])
        return self.qr_code_image.url


class ShopMembership(models.Model):
    ROLE_CHOICES = [
        ('owner', 'Shop Owner'),
        ('manager', 'Shop Manager'),
        ('staff', 'Counter Staff'),
    ]

    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='shop_memberships')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='staff')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('shop', 'user')

    def __str__(self):
        return f"{self.user.email} - {self.role} @ {self.shop.name}"


class ShopQR(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='qr_codes')
    counter_label = models.CharField(max_length=100, default='Counter 1')
    qr_image = models.ImageField(upload_to='qrcodes/counters/', blank=True, null=True)
    scan_count = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.shop.name} - {self.counter_label}"

