from django.db import models


class EmailJob(models.Model):
    STATUS_PENDING = "pending"
    STATUS_SENT = "sent"
    STATUS_FAILED = "failed"

    to_email = models.EmailField()
    template = models.CharField(max_length=80)
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=20, default=STATUS_PENDING, db_index=True)
    provider_message_id = models.CharField(max_length=120, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class DeadLetteredEmail(models.Model):
    email_job = models.ForeignKey(EmailJob, on_delete=models.CASCADE)
    reason = models.TextField()
    attempts = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
