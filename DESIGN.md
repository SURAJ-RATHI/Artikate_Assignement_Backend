# Section 2: Rate-Limited Email Queue Design

I chose Celery with Redis as the broker/backend and a Redis sorted-set sliding window for the provider limit.

My first thought was Django-Q because it is quick to set up and feels lighter for a small Django codebase. I rejected it here because the assignment cares about crash behavior, retry control, acknowledgements, and rate limiting under burst traffic. Celery gives much more direct control over `acks_late`, `reject_on_worker_lost`, retry countdowns, queue routing, and worker prefetching. Those knobs matter when a worker dies halfway through a provider call.

A fully custom queue using Redis lists or streams would also work. Redis Streams with consumer groups can be a nice fit. I did not choose it because I would have to re-build a lot of worker behavior that Celery already has: retry state, task routing, process supervision expectations, dead-letter handling, and observability. For a weekend assessment that is too much surface area. The custom part I did build is the rate limiter, because that is the part where the provider contract is specific.

## Queue behavior

The app stores an `EmailJob` row before enqueueing `send_transactional_email(email_job_id)`. The task loads the row inside `transaction.atomic()` with `select_for_update()` before changing attempt state. That row gives us an idempotency anchor. If Celery retries the same task, the task first checks whether the job is already `sent` and returns the existing provider id.

Celery settings I used:

- `CELERY_TASK_ACKS_LATE = True`
- `CELERY_TASK_REJECT_ON_WORKER_LOST = True`
- `CELERY_WORKER_PREFETCH_MULTIPLIER = 1`

With `acks_late`, Celery acknowledges the message after the task finishes, not before it starts. If the worker process is `SIGKILL`'d while processing a task, the message is not acknowledged. With Redis as broker, the message sits in the broker's unacked area until Redis/Celery's visibility timeout path makes it available again. `reject_on_worker_lost` tells Celery not to treat worker loss as success.

There is still an awkward failure case: the provider may send the email and then the worker may die before the DB row is marked `sent`. The retry can send a duplicate unless the provider supports idempotency keys. In production I would pass `EmailJob.id` as the provider idempotency key if the provider supports it. If it does not, the system is at-least-once, not exactly-once. I would be honest about that in a real design review.

## Retry and dead letters

Provider failures raise `EmailProviderError`. The task retries with exponential backoff using Celery's `self.retry(countdown=...)`. After `max_retries`, it marks the job as `failed` and creates a `DeadLetteredEmail` row with the final reason. I used a DB dead-letter table instead of a separate Redis queue because failed emails are usually something support or ops will inspect later, and SQL is easier to query than broker internals.

## Rate limiter

I used a sliding window with a Redis sorted set:

- Remove timestamps older than the window using `ZREMRANGEBYSCORE`.
- Count active timestamps with `ZCARD`.
- If the count is below 200, add the current send attempt with `ZADD`.
- Set `PEXPIRE` so old keys disappear.

All of that happens in one Lua script via `EVAL`, so Redis executes it atomically. Two workers can hit the limiter at the same time and they still cannot both observe the same free token by accident.

I considered fixed window with `INCR` and `EXPIRE`. It is simpler, but it allows ugly boundary bursts: 200 emails at `12:00:59` and another 200 at `12:01:00`. Token bucket is also reasonable and cheaper than sorted sets, but the refill math needs careful handling under clock skew and concurrent workers. Sliding window is a bit heavier, but for 200/minute the sorted set size is tiny and the behavior is easy to explain when debugging.

If Redis is down, this implementation fails closed: the task errors and Celery retries later. That can delay emails, including OTPs, which is not free. I still prefer it over failing open because failing open can violate the provider limit and get the account throttled or suspended during a flash sale.

## Test shape

The rate limiter test submits 500 logical jobs through the limiter, intentionally retries one failed job, and asserts that no 60-second window has more than 200 accepted attempts. It uses a tiny fake Redis client around the same `eval()` contract so the test can run without Docker or a local Redis service.
