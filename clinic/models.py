import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


def booking_reference():
    return f"BK-{uuid.uuid4().hex[:12].upper()}"


def order_reference():
    return f"OR-{uuid.uuid4().hex[:12].upper()}"


def enquiry_reference():
    return f"EN-{uuid.uuid4().hex[:12].upper()}"


class Product(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=180)
    brand = models.CharField(max_length=120, blank=True)
    category = models.CharField(max_length=80, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    size = models.CharField(max_length=80, blank=True)
    image_url = models.URLField(max_length=1000, blank=True)
    images = models.JSONField(default=list, blank=True)
    key = models.JSONField(default=list, blank=True)
    short_description = models.TextField(blank=True)
    description = models.TextField(blank=True)
    approved = models.BooleanField(default=False)
    featured = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    stock = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Treatment(models.Model):
    BOOKABLE = "bookable"
    CONSULTATION = "consultation"
    REVIEW = "review"
    STATUS_CHOICES = [(BOOKABLE, "Bookable request"), (CONSULTATION, "Consultation request"), (REVIEW, "Under review")]
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=180)
    category = models.CharField(max_length=80, blank=True)
    short_description = models.CharField(max_length=240, blank=True)
    description = models.TextField(blank=True)
    image_url = models.URLField(max_length=1000, blank=True)
    images = models.JSONField(default=list, blank=True)
    price_display = models.CharField(max_length=160, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=BOOKABLE)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["category", "name"]

    def __str__(self):
        return self.name


class NotificationTrackedModel(models.Model):
    NOTIFICATION_PENDING = "pending"
    NOTIFICATION_SENT = "sent"
    NOTIFICATION_FAILED = "failed"
    NOTIFICATION_CHOICES = [
        (NOTIFICATION_PENDING, "Pending"), (NOTIFICATION_SENT, "Sent"),
        (NOTIFICATION_FAILED, "Failed"),
    ]
    notification_status = models.CharField(max_length=20, choices=NOTIFICATION_CHOICES, default=NOTIFICATION_PENDING)
    notification_error = models.TextField(blank=True)

    class Meta:
        abstract = True


class Booking(NotificationTrackedModel):
    STATUS_CHOICES = [("requested", "Request received"), ("contacted", "Client contacted"), ("confirmed", "Confirmed manually"), ("declined", "Declined"), ("cancelled", "Cancelled")]
    reference = models.CharField(max_length=24, unique=True, default=booking_reference, editable=False)
    treatment_slug = models.SlugField(max_length=120)
    treatment_name = models.CharField(max_length=180)
    practitioner_preference = models.CharField(max_length=160, blank=True)
    requested_date = models.DateField()
    requested_time = models.TimeField()
    full_name = models.CharField(max_length=160)
    email = models.EmailField()
    phone = models.CharField(max_length=40, blank=True)
    consent_given = models.BooleanField(default=False)
    consent_at = models.DateTimeField(null=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="clinic_bookings")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="requested")
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.reference} — {self.treatment_name}"


class Order(NotificationTrackedModel):
    STATUS_CHOICES = [("awaiting_manual_confirmation", "Awaiting manual confirmation/payment"), ("confirmed", "Confirmed manually"), ("cancelled", "Cancelled"), ("fulfilled", "Fulfilled")]
    reference = models.CharField(max_length=24, unique=True, default=order_reference, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="clinic_orders")
    full_name = models.CharField(max_length=160)
    email = models.EmailField()
    phone = models.CharField(max_length=40, blank=True)
    address_line_1 = models.CharField(max_length=200)
    address_line_2 = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=100)
    postcode = models.CharField(max_length=24)
    country = models.CharField(max_length=100, default="United Kingdom")
    customer_note = models.TextField(blank=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField(max_length=40, choices=STATUS_CHOICES, default="awaiting_manual_confirmation")
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.reference


class OrderLine(models.Model):
    order = models.ForeignKey(Order, related_name="lines", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, related_name="order_lines", on_delete=models.PROTECT)
    product_name = models.CharField(max_length=180)
    product_slug = models.SlugField(max_length=120)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()

    class Meta:
        ordering = ["id"]

    @property
    def line_total(self):
        return self.unit_price * self.quantity

    def __str__(self):
        return f"{self.quantity} × {self.product_name}"


class ContactEnquiry(NotificationTrackedModel):
    reference = models.CharField(max_length=24, unique=True, default=enquiry_reference, editable=False)
    full_name = models.CharField(max_length=160)
    email = models.EmailField()
    phone = models.CharField(max_length=40, blank=True)
    subject = models.CharField(max_length=180, blank=True)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=[("new", "New"), ("in_progress", "In progress"), ("resolved", "Resolved")], default="new")
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.reference} — {self.full_name}"


class NewsletterSubscription(models.Model):
    email = models.EmailField(unique=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.email
