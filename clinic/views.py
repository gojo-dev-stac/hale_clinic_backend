from django.contrib.auth import authenticate, login, logout
from django.db import transaction
from django.db.models import ProtectedError
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import generics, serializers, status
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Booking, ContactEnquiry, NewsletterSubscription, Order, Product, Treatment
from .notifications import deliver_record_email
from .serializers import (
    BookingCreateSerializer, BookingHistorySerializer, ContactEnquiryCreateSerializer, NewsletterSubscriptionSerializer,
    AccountLoginSerializer, AccountRegisterSerializer, AccountSerializer, OrderCreateSerializer,
    OrderHistorySerializer, ProductSerializer, StaffBookingSerializer, StaffContactEnquirySerializer,
    StaffLoginSerializer, StaffNewsletterSerializer, StaffOrderSerializer, StaffProductSerializer,
    StaffTreatmentSerializer, TreatmentSerializer,
)


def email_status(record):
    if record.notification_status == "failed":
        return "failed"
    if record.notification_status == "sent":
        return "sent"
    return "pending"


def notify_after_save(record, subject, body, customer_email):
    # The API views exit their atomic block before calling this: persistence precedes email.
    return deliver_record_email(record, subject, body, customer_email)


class ProductListView(generics.ListAPIView):
    serializer_class = ProductSerializer
    queryset = Product.objects.filter(active=True, approved=True)


class ProductDetailView(generics.RetrieveAPIView):
    serializer_class = ProductSerializer
    lookup_field = "slug"
    queryset = Product.objects.filter(active=True, approved=True)


class TreatmentListView(generics.ListAPIView):
    serializer_class = TreatmentSerializer
    queryset = Treatment.objects.filter(active=True).exclude(status=Treatment.REVIEW)


class BookingCreateView(APIView):
    def post(self, request):
        serializer = BookingCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            booking = serializer.save(user=request.user if request.user.is_authenticated else None)
        notify_after_save(booking, f"Booking request {booking.reference}",
            f"A booking request was received (not confirmed).\nReference: {booking.reference}\nService: {booking.treatment_name}\nRequested: {booking.requested_date} {booking.requested_time}\nName: {booking.full_name}\nEmail: {booking.email}\nPractitioner preference: {booking.practitioner_preference or 'None'}",
            booking.email)
        return Response({"reference": booking.reference, "status": booking.status, "email_status": email_status(booking)}, status=status.HTTP_201_CREATED)


class OrderCreateView(APIView):
    def post(self, request):
        serializer = OrderCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            order = serializer.save()
        notify_after_save(order, f"Order request {order.reference}",
            f"An order request is awaiting manual confirmation and payment; this is not a placed or paid order.\nReference: {order.reference}\nSubtotal: GBP {order.subtotal}\nName: {order.full_name}\nEmail: {order.email}", order.email)
        return Response({"reference": order.reference, "status": order.status, "email_status": email_status(order), "subtotal": str(order.subtotal)}, status=status.HTTP_201_CREATED)


class ContactEnquiryCreateView(APIView):
    def post(self, request):
        serializer = ContactEnquiryCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            enquiry = serializer.save()
        notify_after_save(enquiry, f"Contact enquiry {enquiry.reference}",
            f"A contact enquiry was received.\nReference: {enquiry.reference}\nName: {enquiry.full_name}\nEmail: {enquiry.email}\nSubject: {enquiry.subject}\nMessage: {enquiry.message}", enquiry.email)
        return Response({"reference": enquiry.reference, "status": enquiry.status, "email_status": email_status(enquiry)}, status=status.HTTP_201_CREATED)


class NewsletterSubscribeView(APIView):
    def post(self, request):
        serializer = NewsletterSubscriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        subscription, created = NewsletterSubscription.objects.get_or_create(
            email=serializer.validated_data["email"]
        )
        if not subscription.active:
            subscription.active = True
            subscription.save(update_fields=["active"])
        return Response({"email": subscription.email, "status": "subscribed", "created": created}, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class CsrfTokenView(APIView):
    def get(self, request):
        return Response({"csrf_token": get_token(request)})


@method_decorator(csrf_protect, name="dispatch")
class AccountRegisterView(APIView):
    def post(self, request):
        serializer = AccountRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        login(request, user)
        return Response(AccountSerializer(user).data, status=status.HTTP_201_CREATED)


@method_decorator(csrf_protect, name="dispatch")
class AccountLoginView(APIView):
    def post(self, request):
        serializer = AccountLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].strip().lower()
        user = authenticate(request, username=email, password=serializer.validated_data["password"])
        if user is None:
            return Response({"detail": "Email or password is incorrect."}, status=status.HTTP_400_BAD_REQUEST)
        login(request, user)
        return Response(AccountSerializer(user).data)


class AccountLogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AccountCurrentView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        if not request.user.is_authenticated:
            return Response(None)
        return Response(AccountSerializer(request.user).data)


class AccountOrdersView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OrderHistorySerializer

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).prefetch_related("lines")


class AccountBookingsView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = BookingHistorySerializer

    def get_queryset(self):
        return Booking.objects.filter(user=self.request.user)


@method_decorator(csrf_protect, name="dispatch")
class StaffLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = StaffLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            request,
            username=serializer.validated_data["username"].strip(),
            password=serializer.validated_data["password"],
        )
        if user is None or not user.is_active or not user.is_staff:
            return Response({"detail": "Staff username or password is incorrect."}, status=status.HTTP_400_BAD_REQUEST)
        login(request, user)
        return Response({"username": user.get_username(), "is_superuser": user.is_superuser})


class StaffCurrentView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        return Response({"username": request.user.get_username(), "is_superuser": request.user.is_superuser})


class StaffLogoutView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class StaffSummaryView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        return Response({
            "products": Product.objects.count(),
            "active_products": Product.objects.filter(active=True, approved=True).count(),
            "treatments": Treatment.objects.count(),
            "bookings": Booking.objects.count(),
            "new_bookings": Booking.objects.filter(status="requested").count(),
            "orders": Order.objects.count(),
            "pending_orders": Order.objects.filter(status="awaiting_manual_confirmation").count(),
            "enquiries": ContactEnquiry.objects.count(),
            "new_enquiries": ContactEnquiry.objects.filter(status="new").count(),
            "newsletter_subscribers": NewsletterSubscription.objects.filter(active=True).count(),
        })


class StaffProductViewSet(generics.ListCreateAPIView):
    permission_classes = [IsAdminUser]
    queryset = Product.objects.all()
    serializer_class = StaffProductSerializer


class StaffProductDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAdminUser]
    queryset = Product.objects.all()
    serializer_class = StaffProductSerializer

    def perform_destroy(self, instance):
        try:
            instance.delete()
        except ProtectedError as error:
            raise serializers.ValidationError(
                {"detail": "This product is part of an order history and cannot be permanently deleted. Edit it and turn off “Visible in shop” instead."},
                code="protected",
            ) from error


class StaffTreatmentViewSet(generics.ListCreateAPIView):
    permission_classes = [IsAdminUser]
    queryset = Treatment.objects.all()
    serializer_class = StaffTreatmentSerializer


class StaffTreatmentDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAdminUser]
    queryset = Treatment.objects.all()
    serializer_class = StaffTreatmentSerializer


class StaffBookingViewSet(generics.ListAPIView):
    permission_classes = [IsAdminUser]
    queryset = Booking.objects.all()
    serializer_class = StaffBookingSerializer


class StaffBookingDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAdminUser]
    queryset = Booking.objects.all()
    serializer_class = StaffBookingSerializer
    lookup_field = "reference"


class StaffOrderViewSet(generics.ListAPIView):
    permission_classes = [IsAdminUser]
    queryset = Order.objects.prefetch_related("lines").all()
    serializer_class = StaffOrderSerializer


class StaffOrderDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAdminUser]
    queryset = Order.objects.prefetch_related("lines").all()
    serializer_class = StaffOrderSerializer
    lookup_field = "reference"


class StaffContactEnquiryViewSet(generics.ListAPIView):
    permission_classes = [IsAdminUser]
    queryset = ContactEnquiry.objects.all()
    serializer_class = StaffContactEnquirySerializer


class StaffContactEnquiryDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAdminUser]
    queryset = ContactEnquiry.objects.all()
    serializer_class = StaffContactEnquirySerializer
    lookup_field = "reference"


class StaffNewsletterViewSet(generics.ListAPIView):
    permission_classes = [IsAdminUser]
    queryset = NewsletterSubscription.objects.all()
    serializer_class = StaffNewsletterSerializer
