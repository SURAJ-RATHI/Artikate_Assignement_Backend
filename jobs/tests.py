import bisect
import time
from unittest import TestCase

from .rate_limiter import RedisSlidingWindowRateLimiter


class FakeRedisForSlidingWindow:
    def __init__(self):
        self.scores = []

    def eval(self, script, key_count, key, now_ms, window_ms, limit, member):
        cutoff = now_ms - window_ms
        self.scores = [score for score in self.scores if score > cutoff]
        if len(self.scores) >= limit:
            retry_after_ms = max(1, self.scores[0] + window_ms - now_ms)
            return [0, retry_after_ms]
        bisect.insort(self.scores, now_ms)
        return [1, 0]


class MutableClock:
    def __init__(self, value):
        self.value = value

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


class RateLimiterTests(TestCase):
    def test_500_jobs_never_exceed_200_per_minute_and_retry_after_window(self):
        clock = MutableClock(time.time())
        redis_client = FakeRedisForSlidingWindow()
        limiter = RedisSlidingWindowRateLimiter(redis_client, "email:rate", 200, 60, clock=clock)

        accepted_at = []
        delayed = []
        failed_once = False

        for job_id in range(500):
            while True:
                decision = limiter.acquire(f"job-{job_id}")
                if decision.allowed:
                    accepted_at.append(clock())
                    if job_id == 17 and not failed_once:
                        failed_once = True
                        continue
                    break
                delayed.append(job_id)
                clock.advance(decision.retry_after_seconds)

        self.assertEqual(len(accepted_at), 501)
        self.assertTrue(failed_once)
        self.assertTrue(delayed)

        for index, timestamp in enumerate(accepted_at):
            window_count = sum(1 for seen_at in accepted_at if timestamp <= seen_at < timestamp + 60)
            self.assertLessEqual(window_count, 200, f"rate exceeded around accepted item {index}")
