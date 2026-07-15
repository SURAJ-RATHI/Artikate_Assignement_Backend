from celery import shared_task
from django.conf import settings
from django.db import transaction
from redis import Redis

from .email_provider import EmailProvider, EmailProviderError
from .models import DeadLetteredEmail, EmailJob
from .rate_limiter import RedisSlidingWindowRateLimiter


def get_rate_limiter():
    redis_client = Redis.from_url(settings.CELERY_BROKER_URL)
    return RedisSlidingWindowRateLimiter(
        redis_client=redis_client,
        key="email:rate-limit",
        limit=settings.EMAIL_RATE_LIMIT,
        window_seconds=settings.EMAIL_RATE_WINDOW_SECONDS,
    )


@shared_task(bind=True, max_retries=5, acks_late=True, reject_on_worker_lost=True)
def send_transactional_email(self, email_job_id):
    limiter = get_rate_limiter()
    decision = limiter.acquire(email_job_id)
    if not decision.allowed:
        raise self.retry(countdown=max(1, int(decision.retry_after_seconds)))

    with transaction.atomic():
        email_job = EmailJob.objects.select_for_update().get(id=email_job_id)
        if email_job.status == EmailJob.STATUS_SENT:
            return email_job.provider_message_id
        email_job.attempts += 1
        email_job.save(update_fields=["attempts", "updated_at"])

    try:
        payload = dict(email_job.payload)
        payload["_attempt"] = email_job.attempts
        provider_message_id = EmailProvider().send(
            email_job.to_email,
            email_job.template,
            payload,
        )
    except EmailProviderError as exc:
        if self.request.retries >= self.max_retries:
            with transaction.atomic():
                email_job = EmailJob.objects.select_for_update().get(id=email_job_id)
                email_job.status = EmailJob.STATUS_FAILED
                email_job.last_error = str(exc)
                email_job.save(update_fields=["status", "last_error", "updated_at"])
                DeadLetteredEmail.objects.create(
                    email_job=email_job,
                    reason=str(exc),
                    attempts=email_job.attempts,
                )
            return None

        countdown = min(300, 2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=countdown)

    EmailJob.objects.filter(id=email_job_id).update(
        status=EmailJob.STATUS_SENT,
        provider_message_id=provider_message_id,
    )
    return provider_message_id
