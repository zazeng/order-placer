import asyncio
from enum import IntEnum, unique
import math
import time


@unique
class RefillRateUnit(IntEnum):
    SECOND = 1
    MINUTE = 2
    HOUR = 3


class AsyncThrottler:
    """Throttle with token bucket algorithm"""

    def __init__(
        self,
        bucket_size_max: int,
        refill_rate: int,
        refill_rate_unit: RefillRateUnit | None = RefillRateUnit.SECOND,
    ) -> None:
        self._bucket_size_max = bucket_size_max
        self._refill_rate_s = None

        match refill_rate_unit:
            case RefillRateUnit.HOUR:
                self._refill_rate_s = refill_rate // (60 * 60)
            case RefillRateUnit.MINUTE:
                self._refill_rate_s = refill_rate // 60
            case RefillRateUnit.SECOND:
                self._refill_rate_s = refill_rate
            case _:
                raise ValueError("Invalid refill rate unit, ", refill_rate_unit)

        self._bucket_size = bucket_size_max
        self._last_refill = 0

    def _refill(self):
        now = time.time()
        delta = now - self._last_refill
        refill = self._refill_rate_s * delta
        self._bucket_size = min(self._bucket_size_max, refill + self._bucket_size)
        self._last_refill = now

    async def acquire(self, weight: int = 1):
        if weight > self._bucket_size_max:
            raise ValueError("weight more than bucket size max")

        self._refill()
        tokens_rem = self._bucket_size - weight

        if tokens_rem >= 0:
            self._bucket_size -= weight
            return

        await asyncio.sleep(math.ceil(abs(tokens_rem) / self._refill_rate_s))
        await self.acquire(weight)
