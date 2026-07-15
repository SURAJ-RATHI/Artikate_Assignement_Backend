from django.core.management.base import BaseCommand

from jobs.models import DeadLetteredEmail, EmailJob


class Command(BaseCommand):
    help = "Print email job counts by status."

    def handle(self, *args, **options):
        for status in [EmailJob.STATUS_PENDING, EmailJob.STATUS_SENT, EmailJob.STATUS_FAILED]:
            count = EmailJob.objects.filter(status=status).count()
            self.stdout.write(f"{status}: {count}")

        self.stdout.write(f"dead_lettered: {DeadLetteredEmail.objects.count()}")
