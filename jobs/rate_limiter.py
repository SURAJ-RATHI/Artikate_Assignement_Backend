import time
import uuid
from dataclasses import dataclass


SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local now_ms = tonumber(ARGV[1])
local window_ms = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local member = ARGV[4]

redis.call('ZREMRANGEBYSCORE', key, 0, now_ms - window_ms)
local count = redis.call('ZCARD', key)
if count >= limit then
  local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
  local retry_after_ms = window_ms
  if oldest[2] then
    retry_after_ms = math.max(1, (tonumber(oldest[2]) + window_ms) - now_ms)
  end
  return {0, retry_after_ms}
end

redis.call('ZADD', key, now_ms, member)
redis.call('PEXPIRE', key, window_ms)
return {1, 0}
"""


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    retry_after_seconds: float


class RedisSlidingWindowRateLimiter:
    def __init__(self, redis_client, key, limit, window_seconds, clock=None):
        self.redis_client = redis_client
        self.key = key
        self.limit = limit
        self.window_seconds = window_seconds
        self.clock = clock or time.time

    def acquire(self, identity):
        now_ms = int(self.clock() * 1000)
        allowed, retry_after_ms = self.redis_client.eval(
            SLIDING_WINDOW_LUA,
            1,
            self.key,
            now_ms,
            int(self.window_seconds * 1000),
            self.limit,
            f"{now_ms}:{identity}:{uuid.uuid4()}",
        )
        return RateLimitDecision(bool(allowed), retry_after_ms / 1000)
