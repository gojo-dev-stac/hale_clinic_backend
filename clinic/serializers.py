from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from .models import Booking, ContactEnquiry, NewsletterSubscription, Order, OrderLine, Product, Treatment

User = get_user_model()


class AccountSerializer(serializers.Serializer):
    email = serializers.EmailField(read_only=True)
    first_name = serializers.CharField(read_only=True)
    last_name = serializers.CharField(read_only=True)
    full_name = serializers.SerializerMethodField()

    def get_full_name(self, user):
        return user.get_full_name().strip()


class AccountRegisterSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=160)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False, style={"input_type": "password"})

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists() or User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        parts = validated_data["name"].strip().split(maxsplit=1)
        return User.objects.create_user(
            username=validated_data["email"],
            email=validated_data["email"],
            first_name=parts[0],
            last_name=parts[1] if len(parts) > 1 else "",
            password=validated_data["password"],
        )


class AccountLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False, style={"input_type": "password"})


class OrderHistoryLineSerializer(serializers.ModelSerializer):
    line_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = OrderLine
        fields = ("product_name", "product_slug", "unit_price", "quantity", "line_total")


class OrderHistorySerializer(serializers.ModelSerializer):
    lines = OrderHistoryLineSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = ("reference", "status", "subtotal", "created_at", "lines")


class BookingHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = (
            "reference", "treatment_name", "practitioner_preference",
            "requested_date", "requested_time", "status", "created_at",
        )


class ProductSerializer(serializers.ModelSerializer):
    image = serializers.URLField(source="image_url", read_only=True)
    images = serializers.ListField(child=serializers.URLField(), read_only=True)
    blurb = serializers.CharField(source="short_description", read_only=True)
    detail = serializers.CharField(source="description", read_only=True)

    class Meta:
        model = Product
        fields = ("slug", "name", "brand", "category", "price", "size", "image", "images", "blurb", "detail", "key", "approved", "featured", "stock")


class TreatmentSerializer(serializers.ModelSerializer):
    image = serializers.URLField(source="image_url", read_only=True)
    images = serializers.ListField(child=serializers.URLField(), read_only=True)

    class Meta:
        model = Treatment
        fields = (
            "slug", "name", "category", "short_description", "description",
            "price_display", "status", "image", "images",
        )


class BookingCreateSerializer(serializers.ModelSerializer):
    practitioner = serializers.CharField(source="practitioner_preference", required=False, allow_blank=True, max_length=160)
    date = serializers.DateField(source="requested_date")
    time = serializers.TimeField(source="requested_time")
    name = serializers.CharField(source="full_name", max_length=160)
    consent = serializers.BooleanField(write_only=True)

    class Meta:
        model = Booking
        fields = ("treatment_slug", "treatment_name", "practitioner", "date", "time", "name", "email", "phone", "consent")
        extra_kwargs = {"treatment_name": {"required": False, "allow_blank": True}}

    def validate(self, attrs):
        if "message" in self.initial_data:
            raise serializers.ValidationError({"message": "Booking requests do not accept free-text messages. Please do not submit health information."})
        if not attrs.pop("consent", False):
            raise serializers.ValidationError({"consent": "Consent is required to submit this request."})
        slug = attrs["treatment_slug"]
        try:
            treatment = Treatment.objects.get(slug=slug, active=True)
        except Treatment.DoesNotExist:
            raise serializers.ValidationError({"treatment_slug": "Select an available treatment or consultation."})
        if treatment.status == Treatment.REVIEW:
            raise serializers.ValidationError({"treatment_slug": "This service is not accepting booking requests."})
        attrs["treatment_name"] = treatment.name
        attrs["consent_given"] = True
        attrs["consent_at"] = timezone.now()
        return attrs


class StaffProductSerializer(serializers.ModelSerializer):
    image = serializers.URLField(source="image_url", required=False, allow_blank=True)
    images = serializers.ListField(child=serializers.URLField(), required=False)
    blurb = serializers.CharField(source="short_description", required=False, allow_blank=True)
    detail = serializers.CharField(source="description", required=False, allow_blank=True)

    class Meta:
        model = Product
        fields = (
            "id", "slug", "name", "brand", "category", "price", "size", "image", "images",
            "key", "blurb", "detail", "approved", "featured", "active", "stock",
            "created_at", "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_key(self, value):
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise serializers.ValidationError("Enter key points as a list of text.")
        return value

    def validate_images(self, value):
        if len(value) > 12:
            raise serializers.ValidationError("A product can have up to 12 images.")
        return list(dict.fromkeys(url.strip() for url in value if url.strip()))

    def validate(self, attrs):
        if "images" in attrs:
            images = attrs["images"]
            attrs["image_url"] = images[0] if images else ""
        return attrs


class StaffTreatmentSerializer(serializers.ModelSerializer):
    image = serializers.URLField(source="image_url", required=False, allow_blank=True)
    images = serializers.ListField(child=serializers.URLField(), required=False)

    class Meta:
        model = Treatment
        fields = (
            "id", "slug", "name", "category", "short_description", "description",
            "price_display", "image", "images", "status", "active",
        )
        read_only_fields = ("id",)

    def validate_images(self, value):
        if len(value) > 12:
            raise serializers.ValidationError("A treatment can have up to 12 images.")
        return list(dict.fromkeys(url.strip() for url in value if url.strip()))

    def validate(self, attrs):
        if "images" in attrs:
            images = attrs["images"]
            attrs["image_url"] = images[0] if images else ""
        return attrs


class StaffBookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = (
            "reference", "treatment_name", "practitioner_preference", "requested_date",
            "requested_time", "full_name", "email", "phone", "status",
            "notification_status", "created_at",
        )
        read_only_fields = tuple(field for field in fields if field != "status")


class StaffOrderSerializer(serializers.ModelSerializer):
    lines = OrderHistoryLineSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = (
            "reference", "full_name", "email", "phone", "address_line_1",
            "address_line_2", "city", "postcode", "country", "subtotal",
            "status", "notification_status", "created_at", "lines",
        )
        read_only_fields = tuple(field for field in fields if field != "status")


class StaffContactEnquirySerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactEnquiry
        fields = (
            "reference", "full_name", "email", "phone", "subject", "message",
            "status", "notification_status", "created_at",
        )
        read_only_fields = tuple(field for field in fields if field != "status")


class StaffNewsletterSerializer(serializers.ModelSerializer):
    class Meta:
        model = NewsletterSubscription
        fields = ("email", "active", "created_at")
        read_only_fields = ("email", "created_at")


class StaffLoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, trim_whitespace=False, style={"input_type": "password"})


class OrderLineInputSerializer(serializers.Serializer):
    slug = serializers.SlugField()
    quantity = serializers.IntegerField(min_value=1, max_value=100)


class OrderCreateSerializer(serializers.Serializer):
    items = OrderLineInputSerializer(many=True, allow_empty=False)
    customer = serializers.DictField()

    def validate_customer(self, customer):
        fields = {
            "name": serializers.CharField(max_length=160),
            "email": serializers.EmailField(),
            "phone": serializers.CharField(max_length=40, required=False, allow_blank=True),
            "address_line_1": serializers.CharField(max_length=200),
            "address_line_2": serializers.CharField(max_length=200, required=False, allow_blank=True),
            "city": serializers.CharField(max_length=100),
            "postcode": serializers.CharField(max_length=24),
            "country": serializers.CharField(max_length=100, required=False, default="United Kingdom"),
        }
        serializer = serializers.Serializer(data=customer)
        for name, field in fields.items():
            serializer.fields[name] = field
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data

    def validate_items(self, items):
        combined = {}
        for item in items:
            combined[item["slug"]] = combined.get(item["slug"], 0) + item["quantity"]
        if any(quantity > 100 for quantity in combined.values()):
            raise serializers.ValidationError("Combined quantity for a product cannot exceed 100.")
        products = Product.objects.filter(slug__in=combined, approved=True, active=True)
        product_by_slug = {product.slug: product for product in products}
        missing = sorted(set(combined) - set(product_by_slug))
        if missing:
            raise serializers.ValidationError({"items": f"Unavailable or unapproved product(s): {', '.join(missing)}."})
        for slug, quantity in combined.items():
            product = product_by_slug[slug]
            if quantity > product.stock:
                raise serializers.ValidationError({"items": f"Insufficient stock for {slug}."})
        self.context["combined_items"] = combined
        self.context["products_by_slug"] = product_by_slug
        return items

    @transaction.atomic
    def create(self, validated_data):
        customer = validated_data["customer"]
        combined_items = self.context["combined_items"]
        products = {
            product.slug: product
            for product in Product.objects.select_for_update().filter(slug__in=combined_items)
        }
        for slug, quantity in combined_items.items():
            product = products.get(slug)
            if product is None or not product.active or not product.approved:
                raise serializers.ValidationError({"items": f"Product {slug} is no longer available."})
            if quantity > product.stock:
                raise serializers.ValidationError({"items": f"Insufficient stock for {slug}."})
        order = Order.objects.create(
            full_name=customer["name"], email=customer["email"], phone=customer.get("phone", ""),
            address_line_1=customer["address_line_1"], address_line_2=customer.get("address_line_2", ""),
            city=customer["city"], postcode=customer["postcode"], country=customer.get("country", "United Kingdom"),
            user=self.context["request"].user if self.context["request"].user.is_authenticated else None,
        )
        subtotal = Decimal("0.00")
        for slug, quantity in combined_items.items():
            product = products[slug]
            price = product.price
            OrderLine.objects.create(order=order, product=product, product_name=product.name, product_slug=product.slug, unit_price=price, quantity=quantity)
            subtotal += price * quantity
        order.subtotal = subtotal
        order.save(update_fields=["subtotal"])
        return order


class ContactEnquiryCreateSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="full_name", max_length=160)

    class Meta:
        model = ContactEnquiry
        fields = ("name", "email", "phone", "subject", "message")


class NewsletterSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = NewsletterSubscription
        fields = ("email",)
