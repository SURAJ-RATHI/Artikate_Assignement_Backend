# Artikate Studio Backend Assessment

**Video_DEMO:** https://drive.google.com/file/d/1Vob95CRNwmFc3YYYC9B8OvspU2CN3JBK/view?usp=sharing

Small Django project for the backend assessment. I kept it intentionally local-first: SQLite for tests, Redis only needed when running the Celery worker for real.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py test
```

On macOS/Linux the activation command is:

```bash
source .venv/bin/activate
```

## What is in here

- `orders/` has the Section 1 N+1 example and the fixed queryset.
- `jobs/` has the Celery task, Redis sliding-window rate limiter, retry handling, and dead-letter model.
- `tenancy/` has tenant context middleware and an ORM manager that scopes querysets automatically.
- `DESIGN.md` covers the async job queue design.
- `ANSWERS.md` has the investigation log and written answers for the other sections.

## Running the queue locally

Start Redis on `localhost:6379`, then run:

```bash
celery -A assessment worker -Q email --loglevel=info
```

The task entry point is `jobs.tasks.send_transactional_email`. In a real app, the API would create an `EmailJob` row and enqueue the Celery task with that row id.

On Windows, use Celery's solo pool:

```bash
celery -A assessment worker -Q email --loglevel=info -P solo
```

To submit demo jobs from another terminal:

```bash
python manage.py submit_email_jobs --count 100 --fail-one
```

To check how many jobs finished:

```bash
python manage.py email_job_status
```

The `--fail-one` flag makes the first job fail once and then succeed on retry, so the worker logs show the retry path without needing a real email provider outage.

## Recording the optional demo

I would record this with Loom because it is quick:

1. Open Loom and choose screen recording.
2. Keep three terminals visible:
   - terminal 1: Redis check, `redis-cli ping`
   - terminal 2: Celery worker, `celery -A assessment worker -Q email --loglevel=info -P solo`
   - terminal 3: submit/check commands
3. Run:

```bash
python manage.py migrate
python manage.py submit_email_jobs --count 100 --fail-one
python manage.py email_job_status
```

4. In the worker terminal, point out:
   - tasks being received
   - one intentional failure
   - Celery retrying it
   - jobs finishing without being lost

After recording, Loom gives a share link. Put that link in this README under the optional section before submitting.



