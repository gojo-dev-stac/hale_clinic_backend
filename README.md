# Hale Clinic backend

Standalone Django 5.2 + Django REST Framework API. This service owns its data and does not depend on frontend runtime packages. It deliberately does not integrate a booking vendor, payment gateway, or card data collection.

## Requirements and local setup

- Python 3.12.3 (3.12+)
- PostgreSQL for deployment, or SQLite for local development

```powershell
cd D:\workflows_void\cyberghostsolutions\hale_clinic_backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py seed_catalog
python manage.py createsuperuser
python manage.py runserver
```

The local default is SQLite (`db.sqlite3`). Set `DATABASE_URL` to any PostgreSQL provider URL to use managed PostgreSQL; no provider is hardcoded. Example: `postgres://user:password@db.example.net:5432/clinic?sslmode=require`. Protect credentials and use a strong `SECRET_KEY`. For production set `DEBUG=False`, `ALLOWED_HOSTS`, and secure TLS database settings.

## Admin

Create the first administrator with `python manage.py createsuperuser`, start the backend, and sign in to the clinic's frontend staff portal at `http://localhost:3000/admin/login`. Use the Django staff username and password (not a customer account); a superuser created by `createsuperuser` is a staff user. The portal at `/admin` manages products, treatments, booking requests, order requests, contact enquiries, and newsletter subscriptions. It provides catalogue creation/editing, up to 12 image URLs per product or treatment (one per line), stock and retail-approval controls, storefront visibility, and request status updates. The first image is used as the card/hero image; detail pages provide selectable image thumbnails. Products and treatments are hidden by deactivation rather than deleted, preserving any order references.

The Django built-in admin at `http://127.0.0.1:8000/admin/` remains available as a technical fallback for creating staff accounts and database administration.

The staff portal's API is under `/api/v1/staff/` and requires an authenticated Django user with `is_staff=True`. It includes login/session endpoints, dashboard counts, catalogue create/edit, and request lists/status updates. Customer accounts cannot access these staff endpoints.

The admin currently supports manual order review only. It does not collect payment or implement shipping rates/labels, refunds, product variants, gift cards, or automatic stock reservation/decrement. Configure a compliant payment and commerce provider, UK tax/shipping rules, and the clinic's permitted-product policy before enabling those workflows. Booking requests are not live appointments; availability, confirmations and rescheduling still require staff/provider handling.

## Customer accounts

Customers can register, sign in/out, and view their own order history at the frontend `/account` page. Django session cookies are HttpOnly; account write requests use CSRF protection. Registration signs the customer in immediately. Orders placed while signed in are associated with that account; guest orders remain guest orders and are not automatically attached to an account by matching email. Only the authenticated account owner can retrieve its order history. Existing accounts have no self-service password reset yet; configure and verify clinic email delivery before adding that recovery flow.

The Next.js frontend proxies `/backend/*` to Django so session cookies remain first-party in the browser. Locally set `BACKEND_URL=http://127.0.0.1:8000` in the frontend environment and restart Next.js; leave the browser site at `http://localhost:3000`. In production, set `BACKEND_URL` to the private/reachable Django API origin, serve the public site over HTTPS, and configure exact CSRF trusted origins. Keep `BACKEND_URL` server-side; do not prefix it with `NEXT_PUBLIC_`.

## API v1

All endpoints are under `/api/v1/`; public API responses are JSON and unauthenticated. Catalogue endpoints return DRF's unpaginated array by default. Write endpoints return `201` on successful record creation, with DRF validation errors as `400`.

- `GET /api/v1/products/` — active and approved products only. `GET /api/v1/products/{slug}/` for detail. Product responses include `image` (primary URL) and `images` (gallery URL array).
- `GET /api/v1/treatments/` — active treatments except those marked under review. Responses include `image` (primary URL) and `images` (gallery URL array).
- `GET /api/v1/auth/csrf/` — bootstrap a CSRF token for browser session requests.
- `POST /api/v1/auth/register/` — create a customer account and sign in; body: `{"name":"Alex Client","email":"alex@example.com","password":"..."}`.
- `POST /api/v1/auth/login/` — sign in with email/password; `POST /api/v1/auth/logout/` — sign out.
- `GET /api/v1/auth/me/` — current authenticated customer; `GET /api/v1/account/orders/` — only that customer's orders and saved line items. These routes require an authenticated session.
- `POST /api/v1/bookings/` — body: `{"treatment_slug":"botox","practitioner":"Any","date":"2026-11-15","time":"10:30","name":"Alex Client","email":"alex@example.com","phone":"...","consent":true}`. Response: `{"reference":"BK-...","status":"requested","email_status":"sent|failed|pending"}`. It records a provider-neutral request only; it is not a confirmed appointment and does not imply live availability. `consent` must be true. `treatment_name` may also be sent but canonical catalog name is stored. Free-text `message` is rejected; do not send medical or other sensitive health information.
- `POST /api/v1/orders/` — body: `{"items":[{"slug":"3d-skin-health-cleanser","quantity":1}],"customer":{"name":"Alex Client","email":"alex@example.com","phone":"...","address_line_1":"1 High Street","address_line_2":"","city":"London","postcode":"SW1A 1AA","country":"United Kingdom"}}`. Response: `{"reference":"OR-...","status":"awaiting_manual_confirmation","email_status":"sent|failed|pending","subtotal":"38.00"}`. Only approved, active products with sufficient stock are accepted. Submitted prices are ignored; name and unit price are snapshotted from the database. Authenticated requests attach the order to the account; guest checkout remains available. This is an order request awaiting manual confirmation/payment, not a placed or paid order.
- `POST /api/v1/contact/` — body: `{"name":"Alex Client","email":"alex@example.com","phone":"...","subject":"Question","message":"..."}`. Response: `{"reference":"EN-...","status":"new","email_status":"sent|failed|pending"}`.
- `POST /api/v1/newsletter/` — body: `{"email":"alex@example.com"}`. Response: `{"email":"alex@example.com","status":"subscribed","created":true}`; repeated subscriptions are idempotent.

Email is attempted only after the record transaction commits. If SMTP host, credentials, or notification recipient are missing, no send is attempted: `email_status` remains `pending`, and the missing configuration is visible in the admin record. `failed` means delivery raised or was rejected; `sent` means both the clinic notification and customer acknowledgement were accepted by the configured SMTP backend. Email failure never rolls back the database record.

The contact message is a generic enquiry field only. Do not send medical history or sensitive health information through website forms.

## SMTP and CORS

Set `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS` (or `EMAIL_USE_SSL`), `DEFAULT_FROM_EMAIL`, and `NOTIFICATION_EMAIL` in environment/secret storage. Keep `.env` out of source control. The backend does not bundle SMTP credentials. Browser origins are restricted by `CORS_ALLOWED_ORIGINS` (comma-separated full origins, e.g. `https://clinic.example`); configure `CSRF_TRUSTED_ORIGINS` for admin origins as needed. Do not use wildcard origins with credentials.

## Catalog seed

`python manage.py seed_catalog` inserts missing rows from the local product and treatment catalog corresponding to the frontend's `hale_clinic/lib/data.ts`, including `phone-consultation`. Product `key` bullet points are editable JSON arrays in admin and included in product API output. It is idempotent, requires no frontend import or network access, and gives new seed products a development stock value of 100; repeated runs preserve admin-managed stock and catalog edits. Adjust stock/approval in admin before production.

## Validation

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```
