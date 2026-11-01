from rest_framework import serializers
from .models import Order, AuditLog, Payment, PrintAgent, PrintJob
from apps.shops.models import Shop
from apps.documents.models import Document


class OrderSerializer(serializers.ModelSerializer):
    document_name = serializers.CharField(source='document.original_name', read_only=True)
    document_download_url = serializers.SerializerMethodField()
    shop_name = serializers.CharField(source='shop.name', read_only=True)
    shop_public_id = serializers.CharField(source='shop.public_id', read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'access_token', 'shop_name', 'shop_public_id',
            'document_name', 'document_download_url', 'customer_name', 'customer_phone',
            'copies', 'selected_pages_count', 'page_range', 'color_mode',
            'paper_size', 'duplex', 'binding', 'total_price', 'currency',
            'payment_method', 'payment_status', 'status', 'is_blocked',
            'blocked_reason', 'special_instructions', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'order_number', 'access_token', 'created_at', 'updated_at']

    def get_document_download_url(self, obj):
        if obj.document:
            return f"/api/v1/documents/{obj.document.id}/download/"
        return None


class OrderCreateSerializer(serializers.Serializer):
    shop_public_id = serializers.CharField()
    document_id = serializers.IntegerField()
    copies = serializers.IntegerField(min_value=1, max_value=500, default=1)
    page_range = serializers.CharField(default='all')
    color_mode = serializers.ChoiceField(choices=['bw', 'color'], default='bw')
    paper_size = serializers.ChoiceField(choices=['A4', 'Letter', 'A3'], default='A4')
    duplex = serializers.BooleanField(default=False)
    binding = serializers.ChoiceField(choices=['none', 'staple', 'spiral', 'hardcover'], default='none')
    payment_method = serializers.ChoiceField(choices=['cash_on_pickup', 'online'], default='cash_on_pickup')
    special_instructions = serializers.CharField(required=False, allow_blank=True, default='')

    def validate(self, data):
        shop = Shop.objects.filter(public_id=data['shop_public_id'], is_active=True).first()
        if not shop:
            raise serializers.ValidationError({"shop_public_id": "Specified print shop does not exist or is inactive."})

        doc = Document.objects.filter(id=data['document_id']).first()
        if not doc:
            raise serializers.ValidationError({"document_id": "Specified document was not found."})

        data['shop'] = shop
        data['document'] = doc
        return data

    def create(self, validated_data):
        shop = validated_data['shop']
        doc = validated_data['document']
        copies = validated_data['copies']
        color_mode = validated_data['color_mode']
        paper_size = validated_data['paper_size']
        duplex = validated_data['duplex']
        binding = validated_data['binding']
        page_range = validated_data['page_range']

        # Parse selected page count
        selected_pages = doc.total_pages
        if page_range and page_range.lower() != 'all':
            # Simple count calculation
            try:
                parts = [p.strip() for p in page_range.split(',') if p.strip()]
                count = 0
                for part in parts:
                    if '-' in part:
                        s, e = map(int, part.split('-'))
                        count += max(0, min(doc.total_pages, e) - max(1, s) + 1)
                    else:
                        num = int(part)
                        if 1 <= num <= doc.total_pages:
                            count += 1
                if count > 0:
                    selected_pages = count
            except Exception:
                selected_pages = doc.total_pages

        # Authoritative calculation formula
        base_rate = 0.50 if color_mode == 'color' else 0.10
        paper_mult = 1.8 if paper_size == 'A3' else 1.0
        pages_subtotal = (base_rate * paper_mult) * selected_pages * copies
        if duplex and selected_pages > 1:
            pages_subtotal *= 0.90  # 10% eco duplex discount

        binding_rates = {'none': 0.0, 'staple': 0.50, 'spiral': 3.00, 'hardcover': 8.00}
        binding_fee = binding_rates.get(binding, 0.0) * copies

        subtotal = pages_subtotal + binding_fee
        tax = subtotal * 0.08
        total_price = round(subtotal + tax, 2)

        order = Order.objects.create(
            shop=shop,
            document=doc,
            copies=copies,
            selected_pages_count=selected_pages,
            page_range=page_range,
            color_mode=color_mode,
            paper_size=paper_size,
            duplex=duplex,
            binding=binding,
            total_price=total_price,
            payment_method=validated_data['payment_method'],
            special_instructions=validated_data.get('special_instructions', '')
        )

        # Create linked Payment record
        Payment.objects.create(
            order=order,
            shop=shop,
            amount=total_price,
            currency=order.currency,
            method=validated_data['payment_method'],
            status='pending'
        )

        return order


class PrintJobSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    document_name = serializers.CharField(source='order.document.original_name', read_only=True)
    document_url = serializers.SerializerMethodField()
    copies = serializers.IntegerField(source='order.copies', read_only=True)
    color_mode = serializers.CharField(source='order.color_mode', read_only=True)
    paper_size = serializers.CharField(source='order.paper_size', read_only=True)
    duplex = serializers.BooleanField(source='order.duplex', read_only=True)
    page_range = serializers.CharField(source='order.page_range', read_only=True)

    class Meta:
        model = PrintJob
        fields = [
            'id', 'order_number', 'document_name', 'document_url',
            'copies', 'color_mode', 'paper_size', 'duplex', 'page_range',
            'status', 'pages_printed', 'started_at', 'completed_at',
            'error_message', 'created_at'
        ]

    def get_document_url(self, obj):
        if obj.order.document:
            return f"/api/v1/documents/{obj.order.document.id}/download/"
        return None



class PrintAgentSerializer(serializers.ModelSerializer):
    shop_name = serializers.CharField(source='shop.name', read_only=True)

    class Meta:
        model = PrintAgent
        fields = ['id', 'shop_name', 'agent_name', 'agent_token', 'printer_name', 'is_online', 'last_heartbeat']
        read_only_fields = ['id', 'agent_token', 'is_online', 'last_heartbeat']

