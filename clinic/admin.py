from django.contrib import admin

from .models import Booking, ContactEnquiry, NewsletterSubscription, Order, OrderLine, Product, Treatment


admin.site.site_header = "The Hale Clinic administration"
admin.site.site_title = "Hale Clinic admin"
admin.site.index_title = "Clinic operations"


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price", "stock", "approved", "active", "featured")
    list_filter = ("approved", "active", "featured", "category")
    search_fields = ("name", "slug", "brand")
    list_editable = ("price", "stock", "approved", "active", "featured")
    actions = ("approve_products", "deactivate_products")
    prepopulated_fields = {"slug": ("name",)}

    @admin.action(description="Approve selected products for the public catalogue")
    def approve_products(self, request, queryset):
        updated = queryset.update(approved=True)
        self.message_user(request, f"{updated} product(s) approved. Check each product is permitted for retail before approval.")

    @admin.action(description="Remove selected products from the public catalogue")
    def deactivate_products(self, request, queryset):
        updated = queryset.update(active=False)
        self.message_user(request, f"{updated} product(s) removed from the public catalogue.")


@admin.register(Treatment)
class TreatmentAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "status", "active")
    list_filter = ("category", "status", "active")
    search_fields = ("name", "slug")


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("reference", "treatment_name", "full_name", "requested_date", "requested_time", "status", "notification_status")
    list_filter = ("status", "notification_status", "requested_date")
    search_fields = ("reference", "full_name", "email", "treatment_name")
    readonly_fields = ("reference", "created_at", "notification_error")
    date_hierarchy = "created_at"
    actions = ("mark_contacted", "confirm_manually", "decline_requests")

    @admin.action(description="Mark selected requests as client contacted")
    def mark_contacted(self, request, queryset):
        updated = queryset.update(status="contacted")
        self.message_user(request, f"{updated} booking request(s) marked as contacted.")

    @admin.action(description="Confirm selected bookings manually")
    def confirm_manually(self, request, queryset):
        updated = queryset.update(status="confirmed")
        self.message_user(request, f"{updated} booking request(s) marked as manually confirmed.")

    @admin.action(description="Decline selected booking requests")
    def decline_requests(self, request, queryset):
        updated = queryset.update(status="declined")
        self.message_user(request, f"{updated} booking request(s) declined.")


class OrderLineInline(admin.TabularInline):
    model = OrderLine
    extra = 0
    can_delete = False
    readonly_fields = ("product", "product_name", "product_slug", "unit_price", "quantity")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("reference", "full_name", "email", "subtotal", "status", "notification_status", "created_at")
    list_filter = ("status", "notification_status", "created_at")
    search_fields = ("reference", "full_name", "email")
    readonly_fields = ("reference", "subtotal", "created_at", "notification_error")
    date_hierarchy = "created_at"
    actions = ("confirm_orders", "fulfil_orders", "cancel_orders")
    inlines = (OrderLineInline,)

    @admin.action(description="Mark selected orders as manually confirmed")
    def confirm_orders(self, request, queryset):
        updated = queryset.update(status="confirmed")
        self.message_user(request, f"{updated} order(s) marked as manually confirmed.")

    @admin.action(description="Mark selected orders as fulfilled")
    def fulfil_orders(self, request, queryset):
        updated = queryset.update(status="fulfilled")
        self.message_user(request, f"{updated} order(s) marked as fulfilled.")

    @admin.action(description="Cancel selected orders")
    def cancel_orders(self, request, queryset):
        updated = queryset.update(status="cancelled")
        self.message_user(request, f"{updated} order(s) cancelled.")


@admin.register(ContactEnquiry)
class ContactEnquiryAdmin(admin.ModelAdmin):
    list_display = ("reference", "full_name", "email", "subject", "status", "notification_status", "created_at")
    list_filter = ("status", "notification_status", "created_at")
    search_fields = ("reference", "full_name", "email", "subject")
    readonly_fields = ("reference", "created_at", "notification_error")
    date_hierarchy = "created_at"
    actions = ("mark_in_progress", "resolve_enquiries")

    @admin.action(description="Mark selected enquiries as in progress")
    def mark_in_progress(self, request, queryset):
        updated = queryset.update(status="in_progress")
        self.message_user(request, f"{updated} enquiry/enquiries marked as in progress.")

    @admin.action(description="Resolve selected enquiries")
    def resolve_enquiries(self, request, queryset):
        updated = queryset.update(status="resolved")
        self.message_user(request, f"{updated} enquiry/enquiries resolved.")


@admin.register(NewsletterSubscription)
class NewsletterSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("email", "active", "created_at")
    list_filter = ("active",)
    search_fields = ("email",)
    readonly_fields = ("created_at",)
