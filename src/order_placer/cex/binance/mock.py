import asyncio
from decimal import Decimal
import random
import time
import uuid

import aiohttp

from order_placer.cex.binance.enums import BnceOrderSide, BnceOrderType, BnceOrderTimeInForce
from order_placer.cex.core.throttler import AsyncThrottler
from order_placer.core.mock import MockClientResponse

_VALID_API_SECRET_KEY_PAIR = {
    ("1api", "1secret"),
    ("2api", "2secret"),
    ("3api", "3secret"),
}


class MockBnceRestEndpointV3:
    def __init__(
        self,
        session: aiohttp.ClientSession,
        api_key: str | None = None,
        secret_key: str | None = None,
        mock_failure_rate: float = 0.0,
    ):
        self._api_key = api_key
        self._secret_key = secret_key
        self._throttler = AsyncThrottler(50, 5)
        self._order_counter = 0
        self._mock_failure_rate = mock_failure_rate

    async def get_symbols(self) -> aiohttp.ClientResponse:
        await self._throttler.acquire()
        return MockClientResponse(
            "GET",
            "/api/v3/exchangeInfo",
            200,
            {
                "timezone": "UTC",
                "serverTime": int(time.time() * 1000),
                "rateLimits": [],
                "exchangeFilters": [],
                "symbols": [
                    {
                        "symbol": "ETHBTC",
                        "status": "TRADING",
                        "baseAsset": "ETH",
                        "quoteAsset": "BTC",
                    },
                    {
                        "symbol": "JTOUSDT",
                        "status": "TRADING",
                        "baseAsset": "JTO",
                        "quoteAsset": "USDT",
                    },
                ],
            },
        )

    async def get_account_info(self) -> aiohttp.ClientResponse:
        await self._throttler.acquire()
        if (self._api_key, self._secret_key) in _VALID_API_SECRET_KEY_PAIR:
            return MockClientResponse("GET", "/api/v3/account", 200, {})
        return MockClientResponse("GET", "/api/v3/account", 401, None, "Unauthorized")

    async def post_order(
        self,
        symbol: str,
        qty: Decimal,
        price: Decimal,
        side: BnceOrderSide | None = None,
        type: BnceOrderType | None = None,
        time_in_force: BnceOrderTimeInForce | None = None,
    ) -> aiohttp.ClientResponse:
        self._order_counter += 1
        cnt = self._order_counter
        await self._throttler.acquire()
        # simulate delay of between (200ms to 500ms)
        await asyncio.sleep(random.uniform(0.2, 0.5))
        # if mock fail rate is set check if fail
        if random.random() < self._mock_failure_rate:
            return MockClientResponse(
                "POST", "/api/v3/order", 500, None, reason="Internal server error."
            )
        return MockClientResponse(
            "POST",
            "/api/v3/order",
            200,
            {
                "symbol": symbol,
                "orderId": cnt,
                "orderListId": -1,
                "clientOrderId": uuid.uuid1(),
                "transactTime": int(time.time() * 1000),
            },
        )
