import uuid
import hashlib
from django.db import models
from django.conf import settings
from pypdf import PdfReader
from .storage import PrivateDocumentStorage

def generate_storage_key():
    return f"doc_{uuid.uuid4().hex}"

def document_upload_path(instance, filename):
    if not getattr(instance, 'storage_key', None):
        instance.storage_key = f"doc_{uuid.uuid4().hex}"
    return f"{instance.storage_key}.pdf"


class Document(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('archived', 'Archived'),
        ('deleted', 'Deleted'),
    ]

    shop = models.ForeignKey('shops.Shop', on_delete=models.CASCADE, related_name='documents')
    storage_key = models.CharField(max_length=64, unique=True, db_index=True, blank=True)
    original_name = models.CharField(max_length=255)
    file = models.FileField(storage=PrivateDocumentStorage(), upload_to=document_upload_path)
    mime_type = models.CharField(max_length=100, default='application/pdf')
    size_bytes = models.BigIntegerField(default=0)
    total_pages = models.PositiveIntegerField(default=1)
    checksum = models.CharField(max_length=64, blank=True, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    retention_until = models.DateTimeField(null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    def save(self, *args, **kwargs):
        if not self.storage_key:
            self.storage_key = f"doc_{uuid.uuid4().hex}"
        super().save(*args, **kwargs)


    def __str__(self):
        return f"{self.original_name} ({self.total_pages}p) [{self.storage_key}] - Shop: {self.shop.name}"

    def compute_checksum(self):
        """
        Calculates SHA-256 checksum of the stored file.
        """
        if self.file:
            try:
                sha256 = hashlib.sha256()
                self.file.seek(0)
                for chunk in self.file.chunks(4096):
                    sha256.update(chunk)
                self.file.seek(0)
                self.checksum = sha256.hexdigest()
                return self.checksum
            except Exception:
                pass
        return ''

    def detect_pages(self):
        """
        Parses genuine PDF file to extract authoritative page count.
        """
        if self.file:
            try:
                self.file.seek(0)
                reader = PdfReader(self.file)
                self.total_pages = max(1, len(reader.pages))
                self.file.seek(0)
            except Exception:
                pass
        return self.total_pages
