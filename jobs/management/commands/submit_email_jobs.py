from django.core.management.base import BaseCommand

from jobs.models import EmailJob
from jobs.tasks import send_transactional_email


class Command(BaseCommand):
    help = "Create demo email jobs and enqueue them through Celery."

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=100)
        parser.add_argument("--fail-one", action="store_true")

    def handle(self, *args, **options):
        count = options["count"]
        fail_one = options["fail_one"]

        created = []
        for index in range(count):
            payload = {"order_id": f"ORD-{index:04d}"}
            if fail_one and index == 0:
                payload["fail_until_attempt"] = 1

            job = EmailJob.objects.create(
                to_email=f"user{index}@example.test",
                template="order_confirmation",
                payload=payload,
            )
            send_transactional_email.delay(job.id)
            created.append(job.id)

        self.stdout.write(self.style.SUCCESS(f"Queued {len(created)} email jobs."))
        if fail_one:
            self.stdout.write("Job 1 is configured to fail once, then succeed on retry.")
