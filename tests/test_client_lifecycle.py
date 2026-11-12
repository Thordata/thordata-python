from __future__ import annotations

import asyncio

import pytest

from thordata import ThorDataClient, ThorDataConfigurationError


class _FakeAsyncClient:
    def __init__(self, timeout: float) -> None:
        self.timeout = timeout
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_owned_async_client_is_reused_until_aclose(monkeypatch) -> None:
    import thordata.client as client_module

    created: list[_FakeAsyncClient] = []

    def factory(*, timeout: float) -> _FakeAsyncClient:
        client = _FakeAsyncClient(timeout)
        created.append(client)
        return client

    monkeypatch.setattr(client_module.httpx, "AsyncClient", factory)
    client = ThorDataClient(api_key="test-key")

    async with client._async_client_scope() as first, client._async_client_scope() as second:
        assert first is second
    assert created == [first]
    assert first.closed is False

    await client.aclose()

    assert first.closed is True
    assert client._async_http_client is None


def test_owned_async_client_can_be_recreated_across_event_loops(monkeypatch) -> None:
    import thordata.client as client_module

    created: list[_FakeAsyncClient] = []

    def factory(*, timeout: float) -> _FakeAsyncClient:
        client = _FakeAsyncClient(timeout)
        created.append(client)
        return client

    monkeypatch.setattr(client_module.httpx, "AsyncClient", factory)
    client = ThorDataClient(api_key="test-key")

    async def use_client() -> None:
        async with client._async_client_scope() as current:
            assert current is not None

    asyncio.run(use_client())
    asyncio.run(use_client())
    asyncio.run(client.aclose())

    assert len(created) == 2
    assert all(item.closed for item in created)
    assert client._async_http_client is None


def test_busy_sync_scrape_error_explains_previous_operation_cleanup() -> None:
    client = ThorDataClient(api_key="test-key")
    client._sync_scrape_lock.acquire()
    try:
        with pytest.raises(ThorDataConfigurationError, match="previous scrape"):
            client.scrape_response(
                "linkedin_company_information_by-url",
                {"url": "https://example.com/company"},
                max_wait_seconds=1,
            )
    finally:
        client._sync_scrape_lock.release()
