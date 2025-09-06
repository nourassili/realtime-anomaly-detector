from collections import deque, defaultdict
from typing import Dict
import time

class OnlineFeatures:
    def __init__(self, window_s: int = 60, max_per_user: int = 50):
        self.window_s = window_s
        self.max_per_user = max_per_user
        self.buckets = defaultdict(deque)

    def _prune(self, user_id: int, now: float):
        dq = self.buckets[user_id]
        cutoff = now - self.window_s
        while dq and dq[0][1] < cutoff:
            dq.popleft()

    def update_and_get(self, user_id: int, amount: float, ts: float):
        dq = self.buckets[user_id]
        dq.append((amount, ts))
        if len(dq) > self.max_per_user:
            dq.popleft()
        self._prune(user_id, ts)
        n = len(dq)
        s = sum(a for a, _ in dq) if n else 0.0
        mean = s / n if n else 0.0
        var = sum((a - mean) ** 2 for a, _ in dq) / n if n else 0.0
        std = var ** 0.5
        last_amt = dq[-2][0] if n >= 2 else 0.0
        return {
            "user_avg_60s": mean,
            "user_std_60s": std,
            "user_count_60s": float(n),
            "delta_from_last": amount - last_amt,
            "z_amount": (amount - mean) / std if std > 1e-6 else 0.0,
        }
