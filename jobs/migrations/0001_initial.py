from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="EmailJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("to_email", models.EmailField(max_length=254)),
                ("template", models.CharField(max_length=80)),
                ("payload", models.JSONField(default=dict)),
                ("status", models.CharField(db_index=True, default="pending", max_length=20)),
                ("provider_message_id", models.CharField(blank=True, max_length=120)),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("last_error", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="DeadLetteredEmail",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reason", models.TextField()),
                ("attempts", models.PositiveIntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "email_job",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="jobs.emailjob"),
                ),
            ],
        ),
    ]
