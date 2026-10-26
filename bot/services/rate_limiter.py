import time
from collections import defaultdict
from typing import Dict, List, Tuple
from bot.config import RATE_LIMIT_PER_MINUTE

class RateLimiter:
    """In-memory sliding window rate limiter per Telegram user."""

    def __init__(self, max_requests: int = RATE_LIMIT_PER_MINUTE, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._user_requests: Dict[int, List[float]] = defaultdict(list)

    def is_rate_limited(self, user_id: int) -> Tuple[bool, int]:
        """
        Checks if a user has exceeded their request limit.
        Returns (is_limited, seconds_to_wait).
        """
        now = time.time()
        window_start = now - self.window_seconds

        # Clean timestamps older than the window
        timestamps = [t for t in self._user_requests[user_id] if t > window_start]
        self._user_requests[user_id] = timestamps

        if len(timestamps) >= self.max_requests:
            oldest_request = timestamps[0]
            retry_after = int(self.window_seconds - (now - oldest_request)) + 1
            return True, max(1, retry_after)

        # Record this request
        self._user_requests[user_id].append(now)
        return False, 0

    def reset_user(self, user_id: int) -> None:
        """Resets rate limit tracking for a user."""
        if user_id in self._user_requests:
            del self._user_requests[user_id]

rate_limiter = RateLimiter()
