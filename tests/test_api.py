from datetime import date, time, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from clinic.models import Booking, ContactEnquiry, Order, OrderLine, Product, Treatment


class PublicApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        Treatment.objects.create(slug="botox", name="Botox", category="Face", status=Treatment.BOOKABLE)
        self.product = Product.objects.create(slug="cleanser", name="Cleanser", brand="Brand", category="Cleanse", price="38.00", approved=True, active=True, stock=4)

    def booking_payload(self):
        return {
            "treatment_slug": "botox", "practitioner": "Any", "date": str(date.today() + timedelta(days=14)),
            "time": "10:30", "name": "Alex Client", "email": "alex@example.com", "phone": "0123456789", "consent": True,
        }

    def order_payload(self, slug="cleanser", quantity=2):
        return {
            "items": [{"slug": slug, "quantity": quantity}],
            "customer": {"name": "Alex Client", "email": "alex@example.com", "phone": "0123456789", "address_line_1": "1 High Street", "address_line_2": "", "city": "London", "postcode": "SW1A 1AA", "country": "United Kingdom"},
        }

    def test_public_catalogue_shows_only_approved_active_products(self):
        Product.objects.create(slug="unapproved", name="Hidden", price="4.00", approved=False, active=True, stock=1)
        Product.objects.create(slug="inactive", name="Disabled", price="4.00", approved=True, active=False, stock=1)
        response = self.client.get("/api/v1/products/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["slug"] for item in response.json()], ["cleanser"])
        self.assertEqual(self.client.get("/api/v1/products/unapproved/").status_code, 404)

    def test_product_serializer_returns_key_points(self):
        self.product.key = ["Easy to use", "Fragrance free"]
        self.product.save(update_fields=["key"])
        response = self.client.get("/api/v1/products/cleanser/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["key"], ["Easy to use", "Fragrance free"])

    def test_staff_catalogue_images_round_trip_and_set_primary_image(self):
        staff = get_user_model().objects.create_user(
            username="image-staff", email="image-staff@example.com", password="test-pass-123", is_staff=True
        )
        self.client.force_login(staff)
        product_response = self.client.post(
            "/api/v1/staff/products/",
            {
                "slug": "image-serum",
                "name": "Image Serum",
                "price": "12.00",
                "images": ["https://example.com/front.jpg", "https://example.com/back.jpg"],
                "approved": True,
                "active": True,
                "stock": 5,
            },
            format="json",
        )
        self.assertEqual(product_response.status_code, 201, product_response.content)
        product = Product.objects.get(slug="image-serum")
        self.assertEqual(product.image_url, "https://example.com/front.jpg")
        self.assertEqual(product_response.json()["images"], ["https://example.com/front.jpg", "https://example.com/back.jpg"])
        public_product = self.client.get("/api/v1/products/image-serum/")
        self.assertEqual(public_product.json()["image"], "https://example.com/front.jpg")
        self.assertEqual(public_product.json()["images"], ["https://example.com/front.jpg", "https://example.com/back.jpg"])

        treatment_response = self.client.post(
            "/api/v1/staff/treatments/",
            {
                "slug": "image-treatment",
                "name": "Image Treatment",
                "short_description": "A concise treatment summary.",
                "description": "Detailed information shown in the treatment popup.",
                "images": ["https://example.com/treatment-main.jpg", "https://example.com/treatment-detail.jpg"],
                "status": "bookable",
                "active": True,
            },
            format="json",
        )
        self.assertEqual(treatment_response.status_code, 201, treatment_response.content)
        treatment = Treatment.objects.get(slug="image-treatment")
        self.assertEqual(treatment.image_url, "https://example.com/treatment-main.jpg")
        public_treatment = self.client.get("/api/v1/treatments/")
        serialized = next(item for item in public_treatment.json() if item["slug"] == "image-treatment")
        self.assertEqual(serialized["images"], ["https://example.com/treatment-main.jpg", "https://example.com/treatment-detail.jpg"])
        self.assertEqual(serialized["short_description"], "A concise treatment summary.")
        self.assertEqual(serialized["description"], "Detailed information shown in the treatment popup.")

    def test_seeded_phone_consultation_slug_accepts_booking(self):
        call_command("seed_catalog", verbosity=0)
        seeded_product = Product.objects.get(slug="3d-skin-health-cleanser")
        self.assertEqual(seeded_product.key, ["Sulphate-free", "Removes SPF and light makeup", "pH balanced", "Morning and evening"])
        payload = self.booking_payload()
        payload["treatment_slug"] = "phone-consultation"
        response = self.client.post("/api/v1/bookings/", payload, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Booking.objects.get().treatment_slug, "phone-consultation")

    def test_booking_rejects_free_text_message(self):
        payload = self.booking_payload()
        payload["message"] = "Please call me about my medical history."
        response = self.client.post("/api/v1/bookings/", payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Booking.objects.count(), 0)

    @override_settings(EMAIL_HOST="", EMAIL_HOST_USER="", EMAIL_HOST_PASSWORD="", NOTIFICATION_EMAIL="")
    @patch("clinic.notifications.send_mail")
    def test_booking_persists_and_exposes_unconfigured_email_as_pending(self, send_mail):
        response = self.client.post("/api/v1/bookings/", self.booking_payload(), format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], "requested")
        self.assertEqual(response.json()["email_status"], "pending")
        booking = Booking.objects.get(reference=response.json()["reference"])
        self.assertTrue(booking.consent_given)
        self.assertEqual(booking.notification_status, "pending")
        self.assertTrue(booking.notification_error)
        send_mail.assert_not_called()

    @override_settings(EMAIL_HOST="smtp.example.com", EMAIL_HOST_USER="clinic", EMAIL_HOST_PASSWORD="secret", NOTIFICATION_EMAIL="clinic@example.com")
    @patch("clinic.notifications.send_mail", side_effect=OSError("SMTP unavailable"))
    def test_email_failure_keeps_booking_saved_and_returns_failure(self, send_mail):
        with self.assertLogs("clinic.notifications", level="ERROR"):
            response = self.client.post("/api/v1/bookings/", self.booking_payload(), format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["email_status"], "failed")
        self.assertEqual(Booking.objects.count(), 1)
        self.assertEqual(Booking.objects.get().notification_status, "failed")
        self.assertTrue(Booking.objects.get().notification_error)

    def test_order_prices_are_calculated_from_database_and_snapshotted(self):
        payload = self.order_payload()
        payload["items"][0]["price"] = "0.01"
        response = self.client.post("/api/v1/orders/", payload, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        order = Order.objects.get(reference=response.json()["reference"])
        line = OrderLine.objects.get(order=order)
        self.assertEqual(order.status, "awaiting_manual_confirmation")
        self.assertEqual(order.subtotal, Decimal("76.00"))
        self.assertEqual(line.unit_price, Decimal("38.00"))
        self.assertEqual(line.product_name, "Cleanser")
        self.assertEqual(response.json()["subtotal"], "76.00")

    def test_order_rejects_unapproved_or_out_of_stock_products(self):
        Product.objects.create(slug="held", name="Held", price="12.00", approved=False, active=True, stock=10)
        self.assertEqual(self.client.post("/api/v1/orders/", self.order_payload("held", 1), format="json").status_code, 400)
        self.assertEqual(self.client.post("/api/v1/orders/", self.order_payload("cleanser", 5), format="json").status_code, 400)
        self.assertEqual(Order.objects.count(), 0)

    def test_contact_and_newsletter_records_persist(self):
        response = self.client.post("/api/v1/contact/", {"name": "Alex", "email": "alex@example.com", "phone": "", "subject": "Hello", "message": "Please contact me."}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(ContactEnquiry.objects.count(), 1)
        subscribe = self.client.post("/api/v1/newsletter/", {"email": "news@example.com"}, format="json")
        self.assertEqual(subscribe.status_code, 201)
        self.assertEqual(subscribe.json()["status"], "subscribed")

    def test_admin_requires_authentication_and_allows_staff(self):
        self.assertEqual(self.client.get("/admin/login/").status_code, 200)
        response = self.client.get("/admin/clinic/product/")
        self.assertEqual(response.status_code, 302)
        user = get_user_model().objects.create_superuser(username="admin", email="admin@example.com", password="safe-test-password")
        self.client.force_login(user)
        self.assertEqual(self.client.get("/admin/clinic/product/").status_code, 200)
        for model_path in ("booking", "order", "contactenquiry", "newslettersubscription", "treatment"):
            self.assertEqual(self.client.get(f"/admin/clinic/{model_path}/").status_code, 200)

    def test_admin_actions_approve_product_and_manage_enquiry(self):
        user = get_user_model().objects.create_superuser(username="staff", email="staff@example.com", password="test-pass-123")
        self.client.force_login(user)
        enquiry = ContactEnquiry.objects.create(
            full_name="Alex Client", email="alex@example.com", subject="Question", message="Please call me."
        )

        product_response = self.client.post(
            "/admin/clinic/product/",
            {"action": "approve_products", "_selected_action": [str(self.product.pk)], "index": "0"},
        )
        self.assertEqual(product_response.status_code, 302)
        self.product.refresh_from_db()
        self.assertTrue(self.product.approved)

        enquiry_response = self.client.post(
            "/admin/clinic/contactenquiry/",
            {"action": "mark_in_progress", "_selected_action": [str(enquiry.pk)], "index": "0"},
        )
        self.assertEqual(enquiry_response.status_code, 302)
        enquiry.refresh_from_db()
        self.assertEqual(enquiry.status, "in_progress")

    def test_account_register_requires_csrf_and_starts_session(self):
        client = APIClient(enforce_csrf_checks=True)
        blocked = client.post(
            "/api/v1/auth/register/",
            {"name": "Alex Client", "email": "alex@example.com", "password": "Clinic-secure-password-928!"},
            format="json",
        )
        self.assertEqual(blocked.status_code, 403)

        csrf = client.get("/api/v1/auth/csrf/").json()["csrf_token"]
        response = client.post(
            "/api/v1/auth/register/",
            {"name": "Alex Client", "email": "alex@example.com", "password": "Clinic-secure-password-928!"},
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["email"], "alex@example.com")
        self.assertEqual(client.get("/api/v1/auth/me/").status_code, 200)

    def test_account_login_and_rejects_invalid_password(self):
        user = get_user_model().objects.create_user(
            username="alex@example.com",
            email="alex@example.com",
            password="Clinic-secure-password-928!",
        )
        client = APIClient(enforce_csrf_checks=True)
        csrf = client.get("/api/v1/auth/csrf/").json()["csrf_token"]
        invalid = client.post(
            "/api/v1/auth/login/",
            {"email": user.email, "password": "incorrect"},
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        self.assertEqual(invalid.status_code, 400)
        success = client.post(
            "/api/v1/auth/login/",
            {"email": user.email, "password": "Clinic-secure-password-928!"},
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        self.assertEqual(success.status_code, 200, success.content)
        self.assertEqual(client.get("/api/v1/auth/me/").json()["email"], user.email)
        rotated_csrf = client.get("/api/v1/auth/csrf/").json()["csrf_token"]
        logout_response = client.post(
            "/api/v1/auth/logout/",
            {},
            format="json",
            HTTP_X_CSRFTOKEN=rotated_csrf,
        )
        self.assertEqual(logout_response.status_code, 204)
        current_account = client.get("/api/v1/auth/me/")
        self.assertEqual(current_account.status_code, 200)
        self.assertEqual(current_account.content, b"")

    def test_account_order_history_is_owned_by_authenticated_account(self):
        user_model = get_user_model()
        owner = user_model.objects.create_user(username="owner@example.com", email="owner@example.com", password="test-pass-123")
        other = user_model.objects.create_user(username="other@example.com", email="other@example.com", password="test-pass-123")
        self.client.force_login(owner)
        response = self.client.post("/api/v1/orders/", self.order_payload(), format="json")
        self.assertEqual(response.status_code, 201, response.content)
        order = Order.objects.get(reference=response.json()["reference"])
        self.assertEqual(order.user, owner)
        Order.objects.create(
            user=other,
            full_name="Other Client",
            email=other.email,
            address_line_1="2 High Street",
            city="London",
            postcode="SW1A 1AA",
            subtotal="10.00",
        )
        history = self.client.get("/api/v1/account/orders/")
        self.assertEqual(history.status_code, 200)
        self.assertEqual([item["reference"] for item in history.json()], [order.reference])
        self.assertEqual(history.json()[0]["lines"][0]["product_name"], "Cleanser")

    def test_account_booking_history_shows_own_current_status_only(self):
        user_model = get_user_model()
        owner = user_model.objects.create_user(
            username="booking-owner@example.com",
            email="booking-owner@example.com",
            password="Clinic-test-password-928!",
        )
        other = user_model.objects.create_user(
            username="booking-other@example.com",
            email="booking-other@example.com",
            password="Clinic-test-password-928!",
        )
        self.client.force_login(owner)

        payload = self.booking_payload()
        payload["practitioner"] = "Haleema Hale"
        response = self.client.post("/api/v1/bookings/", payload, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        booking = Booking.objects.get(reference=response.json()["reference"])
        self.assertEqual(booking.user, owner)
        booking.status = "confirmed"
        booking.save(update_fields=["status"])
        Booking.objects.create(
            user=other,
            treatment_slug="botox",
            treatment_name="Botox",
            requested_date=date.today() + timedelta(days=21),
            requested_time=time(11, 0),
            full_name="Other Client",
            email=other.email,
        )

        history = self.client.get("/api/v1/account/bookings/")
        self.assertEqual(history.status_code, 200)
        self.assertEqual(len(history.json()), 1)
        self.assertEqual(history.json()[0]["reference"], booking.reference)
        self.assertEqual(history.json()[0]["status"], "confirmed")
        self.assertEqual(history.json()[0]["treatment_name"], "Botox")
        self.assertEqual(history.json()[0]["practitioner_preference"], "Haleema Hale")

    def test_account_booking_history_requires_authentication(self):
        response = self.client.get("/api/v1/account/bookings/")
        self.assertIn(response.status_code, (401, 403))

    def test_staff_api_rejects_customer_and_anonymous_access(self):
        self.assertIn(self.client.get("/api/v1/staff/products/").status_code, (401, 403))
        customer = get_user_model().objects.create_user(
            username="customer@example.com", email="customer@example.com", password="Clinic-secure-password-928!"
        )
        self.client.force_login(customer)
        self.assertIn(self.client.get("/api/v1/staff/products/").status_code, (401, 403))
        self.assertIn(self.client.get("/api/v1/staff/summary/").status_code, (401, 403))

    def test_staff_can_delete_unreferenced_products_and_treatments(self):
        staff = get_user_model().objects.create_user(
            username="catalogue-delete-staff", email="delete-staff@example.com", is_staff=True
        )
        self.client.force_login(staff)
        treatment = Treatment.objects.get(slug="botox")

        product_response = self.client.delete(f"/api/v1/staff/products/{self.product.id}/")
        treatment_response = self.client.delete(f"/api/v1/staff/treatments/{treatment.id}/")

        self.assertEqual(product_response.status_code, 204, product_response.content)
        self.assertEqual(treatment_response.status_code, 204, treatment_response.content)
        self.assertFalse(Product.objects.filter(pk=self.product.pk).exists())
        self.assertFalse(Treatment.objects.filter(pk=treatment.pk).exists())

    def test_staff_cannot_delete_product_referenced_by_order_history(self):
        staff = get_user_model().objects.create_user(
            username="order-history-staff", email="order-history-staff@example.com", is_staff=True
        )
        self.client.force_login(staff)
        order = Order.objects.create(
            full_name="Alex Client",
            email="alex@example.com",
            address_line_1="1 High Street",
            city="London",
            postcode="SW1A 1AA",
        )
        OrderLine.objects.create(
            order=order,
            product=self.product,
            product_name=self.product.name,
            product_slug=self.product.slug,
            unit_price=self.product.price,
            quantity=1,
        )

        response = self.client.delete(f"/api/v1/staff/products/{self.product.id}/")

        self.assertEqual(response.status_code, 400)
        self.assertIn("cannot be permanently deleted", response.json()["detail"])
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())

    def test_product_and_treatment_deletion_requires_staff(self):
        treatment = Treatment.objects.get(slug="botox")

        product_response = self.client.delete(f"/api/v1/staff/products/{self.product.id}/")
        treatment_response = self.client.delete(f"/api/v1/staff/treatments/{treatment.id}/")

        self.assertIn(product_response.status_code, (401, 403))
        self.assertIn(treatment_response.status_code, (401, 403))

    def test_staff_login_requires_csrf_and_only_accepts_staff_users(self):
        client = APIClient(enforce_csrf_checks=True)
        user_model = get_user_model()
        customer = user_model.objects.create_user(
            username="customer@example.com", email="customer@example.com", password="Clinic-secure-password-928!"
        )
        staff = user_model.objects.create_user(
            username="clinic-staff", email="staff@example.com", password="Clinic-secure-password-928!", is_staff=True
        )
        csrf = client.get("/api/v1/auth/csrf/").json()["csrf_token"]
        blocked = client.post(
            "/api/v1/staff/login/",
            {"username": staff.username, "password": "Clinic-secure-password-928!"},
            format="json",
        )
        self.assertEqual(blocked.status_code, 403)
        csrf = client.get("/api/v1/auth/csrf/").json()["csrf_token"]
        customer_login = client.post(
            "/api/v1/staff/login/",
            {"username": customer.username, "password": "Clinic-secure-password-928!"},
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        self.assertEqual(customer_login.status_code, 400)
        csrf = client.get("/api/v1/auth/csrf/").json()["csrf_token"]
        staff_login = client.post(
            "/api/v1/staff/login/",
            {"username": staff.username, "password": "Clinic-secure-password-928!"},
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        self.assertEqual(staff_login.status_code, 200, staff_login.content)
        self.assertEqual(client.get("/api/v1/staff/me/").json()["username"], staff.username)

    def test_staff_can_manage_catalogue_and_update_request_statuses(self):
        staff = get_user_model().objects.create_user(
            username="clinic-staff", email="staff@example.com", password="test-pass-123", is_staff=True
        )
        self.client.force_login(staff)
        created_product = self.client.post(
            "/api/v1/staff/products/",
            {
                "slug": "new-serum",
                "name": "New Serum",
                "brand": "Hale Edit",
                "category": "Treat",
                "price": "25.00",
                "size": "30ml",
                "image": "https://example.com/serum.jpg",
                "key": ["Fragrance free"],
                "blurb": "A clinic-approved serum.",
                "detail": "Full product details.",
                "approved": True,
                "featured": False,
                "active": True,
                "stock": 12,
            },
            format="json",
        )
        self.assertEqual(created_product.status_code, 201, created_product.content)
        self.assertEqual(created_product.json()["stock"], 12)
        product_id = created_product.json()["id"]
        self.assertEqual(
            self.client.patch(f"/api/v1/staff/products/{product_id}/", {"stock": 7}, format="json").json()["stock"],
            7,
        )

        created_treatment = self.client.post(
            "/api/v1/staff/treatments/",
            {"slug": "new-treatment", "name": "New Treatment", "category": "Skin", "price_display": "From £100", "status": "bookable", "active": True},
            format="json",
        )
        self.assertEqual(created_treatment.status_code, 201, created_treatment.content)

        booking = Booking.objects.create(
            treatment_slug="botox", treatment_name="Botox", requested_date=date.today() + timedelta(days=14),
            requested_time=time(10, 30), full_name="Alex Client", email="alex@example.com",
        )
        response = self.client.patch(
            f"/api/v1/staff/bookings/{booking.reference}/",
            {"status": "contacted"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        booking.refresh_from_db()
        self.assertEqual(booking.status, "contacted")

        order = Order.objects.create(
            full_name="Alex Client", email="alex@example.com", address_line_1="1 High Street",
            city="London", postcode="SW1A 1AA",
        )
        order_response = self.client.patch(
            f"/api/v1/staff/orders/{order.reference}/",
            {"status": "confirmed"},
            format="json",
        )
        self.assertEqual(order_response.status_code, 200, order_response.content)
        order.refresh_from_db()
        self.assertEqual(order.status, "confirmed")

        enquiry = ContactEnquiry.objects.create(
            full_name="Alex Client", email="alex@example.com", subject="Question", message="Please call me."
        )
        enquiry_response = self.client.patch(
            f"/api/v1/staff/enquiries/{enquiry.reference}/",
            {"status": "in_progress"},
            format="json",
        )
        self.assertEqual(enquiry_response.status_code, 200, enquiry_response.content)
        enquiry.refresh_from_db()
        self.assertEqual(enquiry.status, "in_progress")
