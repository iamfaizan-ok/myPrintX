import io
from rest_framework import serializers
from pypdf import PdfReader
from .models import Document
from apps.shops.models import Shop

class DocumentSerializer(serializers.ModelSerializer):
    download_url = serializers.SerializerMethodField()
    shop_public_id = serializers.CharField(source='shop.public_id', read_only=True)

    class Meta:
        model = Document
        fields = [
            'id', 'storage_key', 'original_name', 'mime_type',
            'size_bytes', 'total_pages', 'checksum', 'status',
            'download_url', 'shop_public_id', 'uploaded_at'
        ]
        read_only_fields = [
            'id', 'storage_key', 'size_bytes', 'total_pages',
            'checksum', 'status', 'download_url', 'uploaded_at'
        ]

    def get_download_url(self, obj):
        # Protected backend-authenticated download endpoint
        return f"/api/v1/documents/{obj.id}/download/"


class DocumentUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    shop_public_id = serializers.CharField(required=True)

    def validate_shop_public_id(self, value):
        shop = Shop.objects.filter(public_id=value, is_active=True).first()
        if not shop:
            raise serializers.ValidationError("Specified shop public ID does not exist or is inactive.")
        return value

    def validate_file(self, value):
        max_size = 50 * 1024 * 1024  # 50MB
        if value.size > max_size:
            raise serializers.ValidationError("File size exceeds maximum 50MB limit.")

        # Genuine PDF Magic Bytes Check: Must begin with %PDF-
        header = value.read(5)
        value.seek(0)
        if not header.startswith(b'%PDF-'):
            raise serializers.ValidationError("Security Validation Failed: Uploaded file is not a valid PDF document.")

        # Verify PDF structural integrity and parse page count
        try:
            reader = PdfReader(value)
            num_pages = len(reader.pages)
            if num_pages < 1:
                raise serializers.ValidationError("PDF document contains no readable pages.")
            if num_pages > 500:
                raise serializers.ValidationError("PDF exceeds maximum allowed page count (500 pages).")
        except serializers.ValidationError:
            raise
        except Exception as e:
            raise serializers.ValidationError(f"Invalid or corrupted PDF file: {str(e)}")
        finally:
            value.seek(0)

        return value

    def create(self, validated_data):
        file = validated_data['file']
        shop_public_id = validated_data['shop_public_id']
        shop = Shop.objects.get(public_id=shop_public_id)

        import uuid
        key = f"doc_{uuid.uuid4().hex}"
        doc = Document(
            shop=shop,
            storage_key=key,
            original_name=file.name,
            mime_type='application/pdf',
            size_bytes=file.size
        )
        doc.file.save(f"{key}.pdf", file, save=False)

        doc.compute_checksum()
        doc.detect_pages()
        doc.save()

        return doc
