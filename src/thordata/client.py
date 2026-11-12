"""HTTP client for ThorData's SERP API."""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from collections.abc import Mapping
from concurrent.futures import Future
from concurrent.futures import TimeoutError as FutureTimeoutError
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from typing import Any, Final

import httpx

from ._version import __version__
from .errors import (
    ThorDataAPIError,
    ThorDataAuthenticationError,
    ThorDataConfigurationError,
    ThorDataConnectionError,
    ThorDataInvalidRequestError,
    ThorDataNotCollectedError,
    ThorDataPermissionError,
    ThorDataRateLimitError,
    ThorDataTimeoutError,
)
from .web_scraper import (
    DEFAULT_MAX_WAIT_SECONDS,
    ThorDataWebScraperError,
    WebScraperResponse,
    _run_web_scraper_async,
    _run_web_scraper_sync,
    _validate_max_wait,
)

DEFAULT_API_URL: Final = "https://scraperapi.thordata.com/request"
INTEGRATION_PLATFORM: Final = "sdk"
INTEGRATION_SOURCE: Final = "python-sdk"

SUPPORTED_ENGINES: Final[tuple[str, ...]] = (
    "google",
    "google_search",
    "google_light",
    "google_web",
    "google_images",
    "google_videos",
    "google_news",
    "google_shopping",
    "google_local",
    "google_places",
    "google_product",
    "google_lens",
    "google_trends",
    "google_maps",
    "google_hotels",
    "google_jobs",
    "google_scholar",
    "google_scholar_cite",
    "google_scholar_author",
    "google_play",
    "google_play_product",
    "google_play_games",
    "google_play_movies",
    "google_play_books",
    "google_finance",
    "google_finance_markets",
    "google_flights",
    "google_patents",
    "google_patents_details",
    "google_ai_mode",
    "bing",
    "bing_images",
    "bing_videos",
    "bing_news",
    "bing_shopping",
    "bing_maps",
    "yandex",
    "duckduckgo",
)

_ENGINE_ALIASES: Final[dict[str, str]] = {
    "google_search": "google",
    "google_places": "google_local",
}
_PARAMETER_ALIASES: Final[dict[str, str]] = {
    "query": "q",
    "country": "gl",
    "language": "hl",
}
_WEB_SCRAPER_ENGINES: Final[frozenset[str]] = frozenset({"google_webpage", "webpage"})
_API_ENGINES: Final[frozenset[str]] = frozenset(
    engine for engine in SUPPORTED_ENGINES if engine not in _ENGINE_ALIASES
)

# Form fields read by Controllers.Request in acen-serp-api-server. Keeping the
# allowlist here preserves the integration requirement that unknown fields are ignored.
_REQUEST_PARAMETERS: Final[frozenset[str]] = frozenset(
    {
        "adlt",
        "adults",
        "after",
        "age",
        "ai_overview",
        "all_reviews",
        "amenities",
        "apps_category",
        "arrival_id",
        "as_rr",
        "as_sdt",
        "as_vis",
        "as_yhi",
        "as_ylo",
        "aspect",
        "assignee",
        "author_id",
        "bags",
        "bathrooms",
        "bedrooms",
        "before",
        "booking_token",
        "books_category",
        "brands",
        "cat",
        "cc",
        "chart",
        "check_in_date",
        "check_out_date",
        "children",
        "children_ages",
        "chips",
        "citation_id",
        "cites",
        "cluster",
        "clustered",
        "color2",
        "count",
        "country",
        "cp",
        "cr",
        "currency",
        "data",
        "data_cid",
        "data_format",
        "data_type",
        "date",
        "deep_search",
        "departure_id",
        "departure_token",
        "device",
        "df",
        "direct_link",
        "dups",
        "eco_certified",
        "efirst",
        "emissions",
        "end_date",
        "exclude_airlines",
        "exclude_conns",
        "face",
        "filter",
        "filters",
        "first",
        "free_cancellation",
        "free_shipping",
        "full",
        "games_category",
        "geo",
        "gl",
        "google_domain",
        "group",
        "hl",
        "hotel_class",
        "ibp",
        "image_color",
        "image_type",
        "imagesize",
        "imgar",
        "imgsz",
        "include_airlines",
        "index_market",
        "infants_in_seat",
        "infants_on_lap",
        "input_proxy",
        "inventor",
        "json",
        "kgmid",
        "kl",
        "kp",
        "lang",
        "language",
        "lat",
        "layover_duration",
        "length",
        "license",
        "licenses",
        "litigation",
        "ll",
        "location",
        "lon",
        "lr",
        "lrad",
        "lsig",
        "ltype",
        "ludocid",
        "max_duration",
        "max_price",
        "min_price",
        "mkt",
        "multi_city_json",
        "next_page_token",
        "nfpr",
        "no_cache",
        "num",
        "offer_id",
        "offers",
        "on_sale",
        "outbound_date",
        "outbound_time",
        "p",
        "page",
        "page_token",
        "patent_id",
        "patents",
        "period_unit",
        "period_value",
        "photo",
        "place_id",
        "platform",
        "price",
        "product_id",
        "product_token",
        "property_token",
        "property_types",
        "publication_token",
        "q",
        "qft",
        "rating",
        "region",
        "render_js",
        "resolution",
        "return_date",
        "return_json",
        "return_time",
        "reviews",
        "rstr",
        "safe",
        "safeSearch",
        "scholar",
        "scisbd",
        "season_id",
        "section_page_token",
        "section_token",
        "see_more_token",
        "setlang",
        "shoprs",
        "show_hidden",
        "si",
        "small_businesses",
        "so",
        "sort",
        "sort_by",
        "source_site",
        "special_offers",
        "specs",
        "start",
        "start_date",
        "status",
        "stops",
        "store",
        "store_device",
        "story_token",
        "tbm",
        "tbs",
        "text",
        "topic_token",
        "travel_class",
        "trend",
        "type",
        "tz",
        "uds",
        "url",
        "uule",
        "vacation_rentals",
        "view_op",
        "window",
        "within",
        "yandex_domain",
    }
)


@dataclass(frozen=True, slots=True)
class SearchResponse:
    """A parsed ThorData response with optional request metadata."""

    result: Any
    task_id: str | None
    raw: Mapping[str, Any]


class ThorDataClient:
    """Synchronous and asynchronous client for ThorData SERP search."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        api_url: str | None = None,
        timeout: float = 30.0,
        headers: Mapping[str, str] | None = None,
        http_client: httpx.Client | None = None,
        async_http_client: httpx.AsyncClient | None = None,
    ) -> None:
        resolved_key = (
            api_key
            or os.getenv("THORDATA_API_KEY")
            or os.getenv("THORDATA_API_TOKEN")
            or os.getenv("TALORDATA_API_TOKEN")
        )
        if not resolved_key or not resolved_key.strip():
            raise ThorDataConfigurationError(
                "ThorData API key is required; pass api_key or set THORDATA_API_KEY"
            )
        if timeout <= 0:
            raise ThorDataConfigurationError("timeout must be greater than zero")

        self._api_key = resolved_key.strip()
        if not self._api_key.isascii():
            raise ThorDataConfigurationError(
                "ThorData API key must contain only ASCII characters; "
                "check the copied key or placeholder text"
            )
        self.api_url = (api_url or os.getenv("THORDATA_SERP_API_URL") or DEFAULT_API_URL).strip()
        if not self.api_url.startswith(("http://", "https://")):
            raise ThorDataConfigurationError("api_url must use http or https")
        self.timeout = timeout
        self._custom_headers = dict(headers or {})
        self._http_client = http_client
        self._async_http_client = async_http_client
        self._owns_http_client = False
        self._owns_async_http_client = False
        self._async_http_client_loop: asyncio.AbstractEventLoop | None = None
        self._sync_scrape_lock = threading.Lock()

    def __repr__(self) -> str:
        return f"<ThorDataClient api_url={self.api_url!r}>"

    def search(
        self,
        params: Mapping[str, Any] | None = None,
        *,
        engine: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """Run a SERP search and return the search result payload."""

        return self.search_response(params, engine=engine, **kwargs).result

    def search_response(
        self,
        params: Mapping[str, Any] | None = None,
        *,
        engine: str | None = None,
        **kwargs: Any,
    ) -> SearchResponse:
        """Run a search and retain ThorData request metadata when available."""

        payload = self._build_payload(params, engine=engine, keyword_params=kwargs)
        try:
            response = self._get_http_client().post(
                self.api_url,
                data=payload,
                headers=self._headers(),
                timeout=self.timeout,
            )
        except httpx.TimeoutException as exc:
            raise ThorDataTimeoutError("ThorData SERP request timed out") from exc
        except httpx.RequestError as exc:
            raise ThorDataConnectionError("Unable to connect to the ThorData SERP API") from exc
        return self._parse_response(response)

    def raw_search(
        self,
        params: Mapping[str, Any] | None = None,
        *,
        engine: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Run a SERP request and return the unparsed response body."""

        payload = self._build_payload(params, engine=engine, keyword_params=kwargs)
        try:
            response = self._get_http_client().post(
                self.api_url,
                data=payload,
                headers=self._headers(),
                timeout=self.timeout,
            )
        except httpx.TimeoutException as exc:
            raise ThorDataTimeoutError("ThorData SERP request timed out") from exc
        except httpx.RequestError as exc:
            raise ThorDataConnectionError("Unable to connect to the ThorData SERP API") from exc
        if response.status_code < 200 or response.status_code >= 300:
            self._raise_api_error(
                code=response.status_code,
                message=f"ThorData SERP API returned HTTP {response.status_code}",
                status_code=response.status_code,
            )
        return response.text

    async def asearch(
        self,
        params: Mapping[str, Any] | None = None,
        *,
        engine: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """Run a SERP search asynchronously and return the result payload."""

        return (await self.asearch_response(params, engine=engine, **kwargs)).result

    async def asearch_response(
        self,
        params: Mapping[str, Any] | None = None,
        *,
        engine: str | None = None,
        **kwargs: Any,
    ) -> SearchResponse:
        """Run an asynchronous search and retain request metadata."""

        payload = self._build_payload(params, engine=engine, keyword_params=kwargs)
        try:
            async with self._async_client_scope() as client:
                response = await client.post(
                    self.api_url,
                    data=payload,
                    headers=self._headers(),
                    timeout=self.timeout,
                )
        except httpx.TimeoutException as exc:
            raise ThorDataTimeoutError("ThorData SERP request timed out") from exc
        except httpx.RequestError as exc:
            raise ThorDataConnectionError("Unable to connect to the ThorData SERP API") from exc
        return self._parse_response(response)

    def scrape(
        self,
        spider_id: str,
        params: Mapping[str, Any] | None = None,
        *,
        max_wait_seconds: float = DEFAULT_MAX_WAIT_SECONDS,
        include_errors: bool = True,
        file_name: str = "{{TasksID}}",
    ) -> list[dict[str, Any]]:
        """Run a supported Web Scraper and return its final records."""

        return self.scrape_response(
            spider_id,
            params,
            max_wait_seconds=max_wait_seconds,
            include_errors=include_errors,
            file_name=file_name,
        ).result

    def scrape_response(
        self,
        spider_id: str,
        params: Mapping[str, Any] | None = None,
        *,
        max_wait_seconds: float = DEFAULT_MAX_WAIT_SECONDS,
        include_errors: bool = True,
        file_name: str = "{{TasksID}}",
    ) -> WebScraperResponse:
        """Run one synchronous scrape per client and retain task metadata.

        Default transport is owned and cancelled within an operation event loop.
        Injected synchronous transports cannot be forcibly interrupted: after a
        timeout the operation slot stays occupied until they return and close
        their response. No further requests are issued by that operation.
        """

        wait = _validate_max_wait(max_wait_seconds)
        if not self._sync_scrape_lock.acquire(blocking=False):
            raise ThorDataConfigurationError(
                "A synchronous scrape is already active on this client; "
                "a previous scrape may still be finishing after timeout, so wait briefly and retry"
            )
        outcome: Future[WebScraperResponse] = Future()
        progress: dict[str, Any] = {"stage": "submit", "task_id": None}
        cancelled = threading.Event()
        control: dict[str, Any] = {}
        deadline = time.monotonic() + wait

        def on_progress(
            stage: str, task_id: str | None, failure: ThorDataWebScraperError | None = None
        ) -> None:
            progress.update(stage=stage, task_id=task_id)
            if failure is not None:
                progress["failure"] = failure

        options = dict(
            api_key=self._api_key,
            spider_id=spider_id,
            params=params,
            max_wait_seconds=max_wait_seconds,
            include_errors=include_errors,
            file_name=file_name,
            deadline=deadline,
            on_progress=on_progress,
        )

        async def owned_operation() -> WebScraperResponse:
            control.update(loop=asyncio.get_running_loop(), task=asyncio.current_task())
            if cancelled.is_set():
                raise asyncio.CancelledError
            # The synchronous entry point owns this async client for this operation only.
            async with self._async_client_scope(use_injected=False) as client:
                return await _run_web_scraper_async(
                    lambda *args: self._web_scraper_request_async(client, *args), **options
                )

        def run() -> None:
            try:
                if self._http_client is not None and not self._owns_http_client:
                    result = _run_web_scraper_sync(self._web_scraper_request, **options)
                else:
                    result = asyncio.run(owned_operation())
            except BaseException as exc:
                self._sync_scrape_lock.release()
                outcome.set_exception(exc)
            else:
                self._sync_scrape_lock.release()
                outcome.set_result(result)

        threading.Thread(target=run, name="thordata-scrape", daemon=True).start()
        try:
            return outcome.result(timeout=max(0, deadline - time.monotonic()))
        except FutureTimeoutError:
            cancelled.set()
            loop = control.get("loop")
            task = control.get("task")
            if loop is not None and task is not None and not loop.is_closed():
                try:
                    loop.call_soon_threadsafe(task.cancel)
                except RuntimeError:
                    # The loop may close between inspection and scheduling; expose other
                    # scheduling errors.
                    if not loop.is_closed():
                        raise
            if progress.get("failure") is not None:
                raise progress["failure"] from None
            stage, task_id = progress["stage"], progress["task_id"]
            raise ThorDataWebScraperError(
                "submission_unknown" if stage == "submit" and task_id is None else "wait_timeout",
                stage=stage,
                task_id=task_id,
                spider_id=spider_id,
            ) from None

    async def ascrape(
        self,
        spider_id: str,
        params: Mapping[str, Any] | None = None,
        *,
        max_wait_seconds: float = DEFAULT_MAX_WAIT_SECONDS,
        include_errors: bool = True,
        file_name: str = "{{TasksID}}",
    ) -> list[dict[str, Any]]:
        """Run a supported Web Scraper asynchronously and return its records."""

        return (
            await self.ascrape_response(
                spider_id,
                params,
                max_wait_seconds=max_wait_seconds,
                include_errors=include_errors,
                file_name=file_name,
            )
        ).result

    async def ascrape_response(
        self,
        spider_id: str,
        params: Mapping[str, Any] | None = None,
        *,
        max_wait_seconds: float = DEFAULT_MAX_WAIT_SECONDS,
        include_errors: bool = True,
        file_name: str = "{{TasksID}}",
    ) -> WebScraperResponse:
        """Run a supported Web Scraper asynchronously with task metadata."""

        wait = _validate_max_wait(max_wait_seconds)
        deadline = time.monotonic() + wait
        async with self._async_client_scope() as client:
            return await _run_web_scraper_async(
                lambda *args: self._web_scraper_request_async(client, *args),
                api_key=self._api_key,
                spider_id=spider_id,
                params=params,
                max_wait_seconds=max_wait_seconds,
                include_errors=include_errors,
                file_name=file_name,
                deadline=deadline,
            )

    def close(self) -> None:
        """Close the internally managed synchronous connection pool."""

        if self._owns_http_client and self._http_client is not None:
            self._http_client.close()
            self._http_client = None
            self._owns_http_client = False

    async def aclose(self) -> None:
        """Close client-owned synchronous and asynchronous connection pools."""

        self.close()
        if self._owns_async_http_client and self._async_http_client is not None:
            client = self._async_http_client
            self._async_http_client = None
            self._owns_async_http_client = False
            self._async_http_client_loop = None
            # Clear the reference before cross-loop cleanup so cleanup cannot block the caller.
            with suppress(Exception):
                await client.aclose()

    def __enter__(self) -> ThorDataClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    async def __aenter__(self) -> ThorDataClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()

    def _get_http_client(self) -> httpx.Client:
        if self._http_client is None:
            self._http_client = httpx.Client(timeout=self.timeout)
            self._owns_http_client = True
        return self._http_client

    @asynccontextmanager
    async def _async_client_scope(self, *, use_injected: bool = True):
        loop = asyncio.get_running_loop()
        if use_injected and self._async_http_client is not None:
            if (
                self._async_http_client_loop is not None
                and self._async_http_client_loop is not loop
            ):
                if not self._owns_async_http_client:
                    raise ThorDataConfigurationError(
                        "The injected async_http_client belongs to a different event loop"
                    )
                previous_loop = self._async_http_client_loop
                if previous_loop.is_running():
                    raise ThorDataConfigurationError(
                        "The owned async_http_client is active in a different event loop"
                    )
                client = self._async_http_client
                self._async_http_client = None
                self._owns_async_http_client = False
                self._async_http_client_loop = None
                with suppress(Exception):
                    await client.aclose()
            self._async_http_client_loop = loop
            if self._async_http_client is not None:
                yield self._async_http_client
                return
            client = httpx.AsyncClient(timeout=self.timeout)
            self._async_http_client = client
            self._owns_async_http_client = True
            self._async_http_client_loop = loop
            yield client
            return
        if use_injected:
            client = httpx.AsyncClient(timeout=self.timeout)
            self._async_http_client = client
            self._owns_async_http_client = True
            self._async_http_client_loop = loop
            yield client
            return
        client = httpx.AsyncClient(timeout=self.timeout)
        try:
            yield client
        except BaseException as operation_error:
            try:
                await client.aclose()
            except Exception as cleanup_error:
                # Preserve the original timeout or cancellation and expose cleanup
                # failures in the chain.
                raise operation_error from cleanup_error
            raise
        else:
            await client.aclose()

    def _web_scraper_headers(
        self, headers: Mapping[str, str], *, include_custom: bool = True
    ) -> dict[str, str]:
        request_headers = dict(self._custom_headers) if include_custom else {}
        request_headers.update(
            {
                "Accept": "application/json",
                "User-Agent": f"thordata-python/{__version__}",
            }
        )
        request_headers.update(headers)
        return {
            key: value
            for key, value in request_headers.items()
            if key.lower() not in {"api-source", "source_platform"}
            and key.lower()
            not in {
                "api_source",
                "platform",
                "origin",
                "x-thordata-platform",
                "x-thordata-source",
            }
        }

    def _build_web_scraper_request(self, client, method, url, headers, data, timeout):
        if method == "GET":
            # Download requests do not inherit authentication, cookies, custom
            # parameters, or private headers.
            return httpx.Request(
                method,
                url,
                headers=self._web_scraper_headers(headers, include_custom=False),
                extensions={"timeout": httpx.Timeout(min(timeout, self.timeout)).as_dict()},
            )
        request = client.build_request(
            method,
            url,
            data=dict(data),
            headers=self._web_scraper_headers(headers),
            timeout=min(timeout, self.timeout),
        )
        for key in list(request.headers):
            if key.lower() in {
                "api-source",
                "source_platform",
                "authorization",
                "proxy-authorization",
                "sign",
                "api-key",
                "api_key",
                "x-api-key",
                "access_token",
                "cookie",
            }:
                del request.headers[key]
        for key, value in headers.items():
            if key.lower() in {"authorization", "sign"}:
                request.headers[key] = value
        return request

    def _web_scraper_request(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str],
        data: Mapping[str, str],
        timeout: float,
    ) -> httpx.Response:
        deadline = time.monotonic() + min(timeout, self.timeout)
        client = self._get_http_client()
        request = self._build_web_scraper_request(client, method, url, headers, data, timeout)
        response = client.send(request, stream=True, follow_redirects=False, auth=None)
        try:
            chunks = []
            for chunk in response.iter_bytes():
                if time.monotonic() >= deadline:
                    raise httpx.ReadTimeout("Web Scraper deadline exceeded")
                chunks.append(chunk)
            return httpx.Response(
                response.status_code,
                headers={
                    key: value
                    for key, value in response.headers.items()
                    if key.lower() not in {"content-encoding", "content-length"}
                },
                content=b"".join(chunks),
                request=request,
            )
        finally:
            response.close()

    async def _web_scraper_request_async(
        self,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        headers: Mapping[str, str],
        data: Mapping[str, str],
        timeout: float,
    ) -> httpx.Response:
        request = self._build_web_scraper_request(client, method, url, headers, data, timeout)
        return await asyncio.wait_for(
            client.send(request, follow_redirects=False, auth=None), min(timeout, self.timeout)
        )

    def _headers(self) -> dict[str, str]:
        headers = dict(self._custom_headers)
        headers.update(
            {
                "Accept": "application/json",
                "Authorization": f"Bearer {self._api_key}",
                "User-Agent": f"thordata-python/{__version__}",
                "Origin": "Python",
                "platform": "python",
                "api-source": "sdk",
            }
        )
        return headers

    def _build_payload(
        self,
        params: Mapping[str, Any] | None,
        *,
        engine: str | None,
        keyword_params: Mapping[str, Any],
    ) -> dict[str, str]:
        effective_engine = engine or "google_search"
        if not isinstance(effective_engine, str) or not effective_engine.strip():
            raise ThorDataInvalidRequestError("A non-empty SERP engine is required", code=400)
        requested_engine = effective_engine.strip().lower()
        normalized_engine = _ENGINE_ALIASES.get(requested_engine, requested_engine)
        if normalized_engine in _WEB_SCRAPER_ENGINES:
            raise ThorDataInvalidRequestError(
                "Web Scraper engines are not available in the V1 SERP integration",
                code=400,
            )
        if normalized_engine not in _API_ENGINES:
            supported = ", ".join(SUPPORTED_ENGINES)
            raise ThorDataInvalidRequestError(
                f"Unsupported SERP engine {effective_engine!r}; supported engines: {supported}",
                code=400,
            )

        if params is not None and not isinstance(params, Mapping):
            raise ThorDataInvalidRequestError("params must be a mapping", code=400)

        param_engine = params.get("engine") if params is not None else None
        if param_engine is not None and engine is not None:
            param_engine = None
        if param_engine is not None:
            if not isinstance(param_engine, str) or not param_engine.strip():
                raise ThorDataInvalidRequestError("engine must be a non-empty string", code=400)
            requested_engine = param_engine.strip().lower()
            normalized_engine = _ENGINE_ALIASES.get(requested_engine, requested_engine)
            if normalized_engine in _WEB_SCRAPER_ENGINES:
                raise ThorDataInvalidRequestError(
                    "Web Scraper engines are not available in the V1 SERP integration",
                    code=400,
                )
            if normalized_engine not in _API_ENGINES:
                supported = ", ".join(SUPPORTED_ENGINES)
                raise ThorDataInvalidRequestError(
                    f"Unsupported SERP engine {param_engine!r}; supported engines: {supported}",
                    code=400,
                )

        payload: dict[str, str] = {}
        for key, value in (params or {}).items():
            if key == "engine":
                continue
            if not isinstance(key, str) or value is None:
                continue
            api_key = _PARAMETER_ALIASES.get(key, key)
            if api_key not in _REQUEST_PARAMETERS:
                continue
            normalized_value = self._normalize_value(value)
            if normalized_value != "":
                payload[api_key] = normalized_value

        for key, value in keyword_params.items():
            api_key = _PARAMETER_ALIASES.get(key, key)
            if api_key not in _REQUEST_PARAMETERS or value is None:
                continue
            normalized_value = self._normalize_value(value)
            if normalized_value != "":
                payload[api_key] = normalized_value

        if normalized_engine == "yandex":
            if "text" not in payload and "q" in payload:
                payload["text"] = payload["q"]
            payload.pop("q", None)

        payload["engine"] = normalized_engine
        payload.setdefault("json", "1")
        payload["isjson"] = "1"
        return payload

    @staticmethod
    def _normalize_value(value: Any) -> str:
        if isinstance(value, bool):
            return "1" if value else "0"
        if isinstance(value, (Mapping, list, tuple, set, frozenset)):
            try:
                return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            except (TypeError, ValueError) as exc:
                raise ThorDataInvalidRequestError(
                    "SERP parameters must contain JSON-serializable values", code=400
                ) from exc
        return str(value).strip()

    def _parse_response(self, response: httpx.Response) -> SearchResponse:
        if response.status_code < 200 or response.status_code >= 300:
            self._raise_api_error(
                code=response.status_code,
                message=f"ThorData SERP API returned HTTP {response.status_code}",
                status_code=response.status_code,
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise ThorDataAPIError(
                "ThorData SERP API returned invalid JSON",
                status_code=response.status_code,
            ) from exc
        if not isinstance(payload, Mapping):
            raise ThorDataAPIError(
                "ThorData SERP API returned an unexpected response shape",
                status_code=response.status_code,
                response_data=payload,
            )

        code = self._coerce_code(payload.get("code"))
        data = self._decode_json_string(payload.get("data"))
        if code is not None and code != 200:
            message = data if isinstance(data, str) else payload.get("msg")
            self._raise_api_error(
                code=code,
                message=self._redact(str(message or "ThorData rejected the SERP request")),
                status_code=response.status_code,
                response_data=data,
            )

        if code == 200 and isinstance(data, Mapping) and "result" in data:
            task_id = data.get("task_id")
            if not task_id:
                metadata = payload.get("search_metadata")
                task_id = metadata.get("id") if isinstance(metadata, Mapping) else None
            return SearchResponse(
                result=self._decode_json_string(data["result"]),
                task_id=str(task_id) if task_id else None,
                raw=payload,
            )
        result = data if "data" in payload else payload
        metadata = payload.get("search_metadata")
        task_id = metadata.get("id") if isinstance(metadata, Mapping) else None
        return SearchResponse(result=result, task_id=str(task_id) if task_id else None, raw=payload)

    @staticmethod
    def _decode_json_string(value: Any) -> Any:
        if not isinstance(value, str):
            return value
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return value

    @staticmethod
    def _coerce_code(value: Any) -> int | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
        return None

    def _raise_api_error(
        self,
        *,
        code: int,
        message: str,
        status_code: int,
        response_data: Any = None,
    ) -> None:
        error_type: type[ThorDataAPIError]
        if code == 300 or (code == 0 and "collection failed" in message.lower()):
            error_type = ThorDataNotCollectedError
        elif code == 401:
            error_type = ThorDataAuthenticationError
        elif code == 402:
            error_type = ThorDataPermissionError
        elif code == 429:
            error_type = ThorDataRateLimitError
        elif code == 400:
            error_type = ThorDataInvalidRequestError
        else:
            error_type = ThorDataAPIError
        raise error_type(
            self._redact(message),
            code=code,
            status_code=status_code,
            response_data=response_data,
        )

    def _redact(self, value: str) -> str:
        return value.replace(self._api_key, "***")
