from decimal import Decimal
import hashlib
import hmac
import os
import time
from typing_extensions import Self
import urllib.parse

import aiohttp

from order_placer.cex.binance.enums import BnceOrderSide, BnceOrderType, BnceOrderTimeInForce
from order_placer.cex.binance.mock import MockBnceRestEndpointV3
from order_placer.cex.core.throttler import AsyncThrottler, RefillRateUnit


def _hashing(query_string: str, secret_key: str) -> str:
    """hashing used to sign bnce rest requests"""
    return hmac.new(
        secret_key.encode("utf-8"), query_string.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def _get_timestamp_ms() -> int:
    """returns current timestamp in milliseconds rounded down to nearest integer"""
    return int(time.time() * 1000)


class BnceRestEndpointV3:
    def __new__(cls, *args, **kwargs) -> Self:
        if os.environ.get("APP_ENV") == "test":
            return MockBnceRestEndpointV3(*args, **kwargs)
        return super().__new__(cls)

    def __init__(
        self,
        session: aiohttp.ClientSession,
        api_key: str | None = None,
        secret_key: str | None = None,
        throttle_bucket_size: int = 45,
        throttle_refill_rate_s: int = 5,
    ):
        self._session = session
        self._api_key = api_key
        self._secret_key = secret_key
        self._throttler = AsyncThrottler(
            throttle_bucket_size, throttle_refill_rate_s, RefillRateUnit.SECOND
        )

    async def post_order(
        self,
        symbol: str,
        qty: Decimal,
        price: Decimal,
        side: BnceOrderSide | None = None,
        type: BnceOrderType | None = None,
        time_in_force: BnceOrderTimeInForce | None = None,
    ) -> aiohttp.ClientResponse:
        return await self._signed_http_request(
            "POST",
            "/api/v3/order",
            {
                "symbol": symbol,
                "side": side.value,
                "type": type.value,
                "timeInForce": time_in_force.value,
                "quantity": str(qty),
                "price": str(price),
            },
        )

    async def get_symbols(self) -> aiohttp.ClientResponse:
        return await self._unsigned_http_request("GET", "/api/v3/exchangeInfo")

    async def get_account_info(self) -> aiohttp.ClientResponse:
        return await self._signed_http_request("GET", "/api/v3/account")

    async def _unsigned_http_request(
        self, http_method: str, path: str, params: dict | None = None
    ) -> aiohttp.ClientResponse:
        await self._throttler.acquire()
        resp = await self._session.request(
            http_method,
            path,
            params=params,
        )
        return resp

    async def _signed_http_request(
        self, http_method: str, path: str, payload: dict | None = None
    ) -> aiohttp.ClientResponse:
        """Performs a binance signed request"""
        query_string = urllib.parse.urlencode(payload or {}, True)
        if query_string:
            query_string = "{}&timestamp={}".format(query_string, _get_timestamp_ms())
        else:
            query_string = "timestamp={}".format(_get_timestamp_ms())

        url = (
            path
            + "?"
            + query_string
            + "&signature="
            + _hashing(query_string, self._secret_key)
        )
        headers = {
            "Content-Type": "application/json;charset=utf-8",
            "X-MBX-APIKEY": self._api_key,
        }

        await self._throttler.acquire()
        return await self._session.request(
            method=http_method, url=url, params={}, headers=headers
        )
