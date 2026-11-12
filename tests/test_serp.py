from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from thordata import (
    ThorDataClient,
    ThorDataConfigurationError,
    ThorDataInvalidRequestError,
    ThorDataNotCollectedError,
)


def _form(request: httpx.Request) -> dict[str, str]:
    return dict(httpx.QueryParams(request.content.decode("utf-8")))


def test_search_response_normalizes_aliases_and_returns_metadata() -> None:
    seen: list[tuple[str, dict[str, str], dict[str, str]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((str(request.url), _form(request), dict(request.headers)))
        return httpx.Response(
            200,
            json={
                "code": 200,
                "data": {
                    "result": {"search_information": {"query_displayed": "pizza"}},
                    "task_id": "task-serp-1",
                },
            },
            request=request,
        )

    client = ThorDataClient(
        api_key="test-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    response = client.search_response(
        {"engine": "google_search", "query": "pizza", "country": "us", "language": "en"},
    )

    assert seen[0][0] == "https://scraperapi.thordata.com/request"
    assert seen[0][1] == {
        "engine": "google",
        "q": "pizza",
        "gl": "us",
        "hl": "en",
        "json": "1",
        "isjson": "1",
    }
    assert seen[0][2]["origin"] == "Python"
    assert seen[0][2]["platform"] == "python"
    assert seen[0][2]["api-source"] == "sdk"
    assert response.result["search_information"]["query_displayed"] == "pizza"
    assert response.task_id == "task-serp-1"
    assert response.raw["code"] == 200


def test_basic_serp_fixture_matches_normalized_form() -> None:
    fixture = json.loads(
        (Path(__file__).resolve().parents[2] / "contract-fixtures" / "serp" / "basic-request.json")
        .read_text(encoding="utf-8")
    )

    assert fixture["form"]["engine"] == "google"
    assert "integration_platform" not in fixture["form"]
    assert "integration_source" not in fixture["form"]


def test_search_normalizes_boolean_values_yandex_and_ignores_unknown_fields() -> None:
    seen: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(_form(request))
        return httpx.Response(200, json={"code": 200, "data": {"result": []}}, request=request)

    client = ThorDataClient(
        api_key="test-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = client.search(
        {"q": "weather", "safe": False, "unknown": "drop"},
        engine="yandex",
    )

    assert result == []
    assert seen == [
        {
            "engine": "yandex",
            "text": "weather",
            "safe": "0",
            "json": "1",
            "isjson": "1",
        }
    ]


def test_engine_in_params_is_honored() -> None:
    seen: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(_form(request))
        return httpx.Response(200, json={"code": 200, "data": {"result": []}}, request=request)

    client = ThorDataClient(
        api_key="test-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    client.search({"engine": "bing", "q": "news"})

    assert seen[0]["engine"] == "bing"


def test_explicit_engine_keyword_takes_precedence() -> None:
    seen: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(_form(request))
        return httpx.Response(200, json={"code": 200, "data": {"result": []}}, request=request)

    client = ThorDataClient(
        api_key="test-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    client.search({"engine": "google_news", "q": "news"}, engine="bing")

    assert seen[0]["engine"] == "bing"


def test_explicit_google_search_keyword_takes_precedence_over_params() -> None:
    seen: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(_form(request))
        return httpx.Response(200, json={"code": 200, "data": {"result": []}}, request=request)

    client = ThorDataClient(
        api_key="test-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    client.search({"engine": "bing", "q": "news"}, engine="google_search")

    assert seen[0]["engine"] == "google"


def test_params_web_scraper_engine_uses_the_web_scraper_error() -> None:
    client = ThorDataClient(api_key="test-key")

    with pytest.raises(ThorDataInvalidRequestError, match="Web Scraper engines"):
        client.search({"engine": "google_webpage", "q": "page"})


def test_mapping_values_are_serialized_as_json() -> None:
    seen: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(_form(request))
        return httpx.Response(200, json={"code": 200, "data": {"result": []}}, request=request)

    client = ThorDataClient(
        api_key="test-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    client.search({"filters": {"price_min": 10}})

    assert seen[0]["filters"] == '{"price_min":10}'


def test_set_values_are_rejected_instead_of_using_python_repr() -> None:
    client = ThorDataClient(api_key="test-key")

    with pytest.raises(ThorDataInvalidRequestError, match="JSON-serializable"):
        client.search({"filters": {"a", "b"}})


def test_invalid_params_type_is_rejected() -> None:
    client = ThorDataClient(api_key="test-key")

    with pytest.raises(ThorDataInvalidRequestError, match="params must be a mapping"):
        client.search(["q", "value"])  # type: ignore[arg-type]


def test_non_ascii_api_key_is_rejected_at_construction() -> None:
    with pytest.raises(ThorDataConfigurationError, match="ASCII"):
        ThorDataClient(api_key="api-key-\u00e9")


def test_collection_failed_code_zero_is_not_collected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"code": 0, "data": "error, Collection failed"},
            request=request,
        )

    client = ThorDataClient(
        api_key="test-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(ThorDataNotCollectedError) as raised:
        client.search({"q": "one"})

    assert raised.value.code == 0


def test_bare_serp_results_use_search_metadata_id_as_task_id() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"code": 200, "organic": [], "search_metadata": {"id": "request-1"}},
            request=request,
        )

    client = ThorDataClient(
        api_key="test-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    response = client.search_response({"q": "one"})

    assert response.task_id == "request-1"
    assert response.raw["search_metadata"]["id"] == "request-1"


def test_search_accepts_nested_json_string_data() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        nested = json.dumps({"result": {"organic_results": [{"title": "one"}]}})
        return httpx.Response(200, json={"code": 200, "data": nested}, request=request)

    client = ThorDataClient(
        api_key="test-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert client.search({"q": "one"}) == {"organic_results": [{"title": "one"}]}


def test_search_raises_typed_error_for_not_collected_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": 300, "data": "not collected"}, request=request)

    client = ThorDataClient(
        api_key="test-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(ThorDataNotCollectedError) as raised:
        client.search({"q": "one"})

    assert raised.value.code == 300
    assert "test-key" not in str(raised.value)


def test_raw_search_returns_the_unparsed_response_body() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="raw-response", request=request)

    client = ThorDataClient(
        api_key="test-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert client.raw_search({"q": "one"}) == "raw-response"


def test_client_accepts_the_legacy_talordata_token_environment_variable(monkeypatch) -> None:
    monkeypatch.delenv("THORDATA_API_KEY", raising=False)
    monkeypatch.delenv("THORDATA_API_TOKEN", raising=False)
    monkeypatch.setenv("TALORDATA_API_TOKEN", "legacy-token")

    client = ThorDataClient()

    assert client._api_key == "legacy-token"
    client.close()


@pytest.mark.asyncio
async def test_asearch_uses_async_http_client() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"code": 200, "data": {"result": {"ok": True}}},
            request=request,
        )

    client = ThorDataClient(
        api_key="test-key",
        async_http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    assert await client.asearch({"q": "async"}) == {"ok": True}
    await client.aclose()
