from django.core.management.base import BaseCommand
from redis import Redis

from django.conf import settings
from jobs.models import DeadLetteredEmail, EmailJob


class Command(BaseCommand):
    help = "Clear demo email jobs and Redis queue/rate-limit keys."

    def handle(self, *args, **options):
        DeadLetteredEmail.objects.all().delete()
        EmailJob.objects.all().delete()

        redis_client = Redis.from_url(settings.CELERY_BROKER_URL)
        redis_client.delete("email", "email:rate-limit")

        self.stdout.write(self.style.SUCCESS("Cleared demo email jobs and Redis queue state."))
