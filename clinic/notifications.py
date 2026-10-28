import logging

from django.conf import settings
from django.core.mail import send_mail

from .models import NotificationTrackedModel

logger = logging.getLogger(__name__)


def deliver_record_email(record, subject, body, customer_email):
    """Send only after the caller has committed the record."""
    if not all((settings.EMAIL_HOST, settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD, settings.NOTIFICATION_EMAIL)):
        record.notification_status = NotificationTrackedModel.NOTIFICATION_PENDING
        record.notification_error = "SMTP host, credentials, or notification recipient are not configured."
        record.save(update_fields=["notification_status", "notification_error"])
        logger.info("Notification not configured for %s", record.pk)
        return record.notification_status

    failures = []
    messages = [(settings.NOTIFICATION_EMAIL, subject, body)]
    if customer_email:
        messages.append((customer_email, f"We received your request — {subject}", body))
    for recipient, email_subject, email_body in messages:
        try:
            sent = send_mail(email_subject, email_body, settings.DEFAULT_FROM_EMAIL, [recipient], fail_silently=False)
            if sent != 1:
                failures.append(f"Delivery to {recipient} was not accepted by the email backend.")
        except Exception as exc:  # The DB record must survive mail-provider failures.
            logger.error("Email delivery failed for record %s (%s)", record.pk, type(exc).__name__)
            failures.append(f"Delivery to {recipient} failed ({type(exc).__name__}); see application logs.")

    if failures:
        record.notification_status = NotificationTrackedModel.NOTIFICATION_FAILED
        record.notification_error = " ".join(failures)[:2000]
    else:
        record.notification_status = NotificationTrackedModel.NOTIFICATION_SENT
        record.notification_error = ""
    record.save(update_fields=["notification_status", "notification_error"])
    return record.notification_status
