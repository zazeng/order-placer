from aiohttp import ClientResponse, ClientResponseError
from yarl import URL


class MockClientResponse(ClientResponse):
    def __init__(
        self,
        method: str,
        url: str,
        status: int,
        json: dict | None,
        reason: str | None = None,
    ) -> None:
        self.method = method
        self._url = URL(url)
        self.status = status
        self._resp_json = json
        self.reason = reason

    @property
    def ok(self):
        return self.status and self.status < 300

    async def json(self) -> dict:
        return self._resp_json

    def raise_for_status(self) -> None:
        if self.reason:
            raise ClientResponseError(
                None,
                None,
                status=500,
                message="Internal server error",
                headers={},
            )
