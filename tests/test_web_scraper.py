from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest

from thordata import (
    SUPPORTED_WEB_SCRAPERS,
    ThorDataClient,
    ThorDataInvalidRequestError,
    ThorDataWebScraperError,
)
from thordata.web_scraper import validate_web_scraper_params


def _success_transport(
    records: list[dict[str, object]] | None = None,
    download: str = "https://scraperapi.thordata.com/download?task_id=TASK-1&type=json&api_key=server-key",
):
    calls: list[httpx.Request] = []
    records = records or [{"name": "Example", "success": True}]

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.path == "/builder":
            form = parse_qs(request.content.decode())
            assert form["spider_id"] == ["linkedin_company_information_by-url"]
            assert json.loads(form["spider_parameters"][0]) == [
                {"url": "https://www.linkedin.com/company/example"}
            ]
            assert form["spider_errors"] == ["true"]
            assert form["api_source"] == ["sdk"]
            assert "api-source" not in form
            assert form["source_platform"] == ["python"]
            assert request.headers["authorization"] == "Bearer secret-token"
            assert "api-source" not in request.headers
            assert "api_source" not in request.headers
            assert "source_platform" not in request.headers
            assert "platform" not in request.headers
            assert "origin" not in request.headers
            return httpx.Response(200, json={"code": 200, "data": {"task_id": "TASK-1"}})
        if request.url.path.endswith("/tasks-status"):
            assert request.headers["sign"] == "secret-token"
            form = parse_qs(request.content.decode())
            assert form["tasks_ids"] == ["TASK-1"]
            assert form["api_source"] == ["sdk"]
            assert "api-source" not in form
            assert form["source_platform"] == ["python"]
            assert "api-source" not in request.headers
            assert "api_source" not in request.headers
            assert "source_platform" not in request.headers
            assert "platform" not in request.headers
            assert "origin" not in request.headers
            return httpx.Response(
                200,
                json={"code": 200, "data": [{"task_id": "TASK-1", "status": "Ready"}]},
            )
        if request.url.path.endswith("/tasks-download"):
            assert request.headers["sign"] == "secret-token"
            assert parse_qs(request.content.decode())["tasks_id"] == ["TASK-1"]
            form = parse_qs(request.content.decode())
            assert form["api_source"] == ["sdk"]
            assert "api-source" not in form
            assert form["source_platform"] == ["python"]
            assert "api-source" not in request.headers
            assert "api_source" not in request.headers
            assert "source_platform" not in request.headers
            assert "platform" not in request.headers
            assert "origin" not in request.headers
            return httpx.Response(
                200,
                json={"code": 200, "data": {"tasks_ids": "TASK-1", "download": download}},
            )
        assert request.url.path == "/download"
        assert "server-key" in request.url.query.decode()
        return httpx.Response(200, json=records)

    return calls, httpx.Client(transport=httpx.MockTransport(handler))


def test_all_seven_spiders_have_the_expected_parameter_contract() -> None:
    assert len(SUPPORTED_WEB_SCRAPERS) == 7
    values = {
        "linkedin_company_information_by-url": {"url": "https://example.com/company"},
        "linkedin_job_listings_information_by-job-url": {"job_url": "https://example.com/job"},
        "youtube_video-post_by-keyword": {"keyword": "python", "num_of_posts": 3},
        "facebook_profile_by-profiles-url": {"url": "https://example.com/profile"},
        "youtube_video-post_by-explore": {"url": "https://example.com/explore", "all_tabs": False},
        "twitter_profile_by-profileurl": {"url": "https://example.com/profile"},
        "amazon_product_by-category-url": {
            "url": "https://example.com/category",
            "page_turning": 2,
        },
    }

    normalized = {
        spider_id: validate_web_scraper_params(spider_id, params)
        for spider_id, params in values.items()
    }

    assert normalized["youtube_video-post_by-keyword"]["num_of_posts"] == "3"
    assert normalized["youtube_video-post_by-explore"]["all_tabs"] == "flase"
    assert normalized["amazon_product_by-category-url"]["sort_by"] == "Best Sellers"


def test_contract_fixtures_match_the_wire_envelopes() -> None:
    root = Path(__file__).resolve().parents[1] / "contract-fixtures"
    serp = json.loads((root / "serp" / "envelopes.json").read_text(encoding="utf-8"))
    scraper = json.loads(
        (root / "web-scraper" / "lifecycle.json").read_text(encoding="utf-8")
    )

    assert serp["collection_failed"]["code"] == 0
    assert scraper["status"][0]["data"][0]["status"] == "Running"
    assert "download" in scraper["download_address"]["data"]
    assert scraper["records"][0]["success"] is True


@pytest.mark.parametrize(
    ("spider_id", "params"),
    [
        ("unknown", {}),
        ("linkedin_company_information_by-url", {}),
        ("youtube_video-post_by-keyword", {"keyword": "python", "extra": True}),
        ("amazon_product_by-category-url", {"url": "https://example.com", "page_turning": 0}),
    ],
)
def test_invalid_scraper_parameters_are_rejected(spider_id: str, params: dict[str, object]) -> None:
    with pytest.raises(ThorDataInvalidRequestError):
        validate_web_scraper_params(spider_id, params)


def test_scrape_waits_until_ready_downloads_and_returns_metadata() -> None:
    calls, http_client = _success_transport()
    client = ThorDataClient(api_key="secret-token", http_client=http_client)

    response = client.scrape_response(
        "linkedin_company_information_by-url",
        {"url": "https://www.linkedin.com/company/example"},
    )

    assert response.result == [{"name": "Example", "success": True}]
    assert response.task_id == "TASK-1"
    assert response.spider_id == "linkedin_company_information_by-url"
    assert response.status == "completed"
    assert response.record_count == 1
    assert response.error_record_count == 0
    assert [request.url.path for request in calls] == [
        "/builder",
        "/api/web-scraper-api/tasks-status",
        "/api/web-scraper-api/tasks-download",
        "/download",
    ]
    client.close()


def test_scrape_marks_partial_records_and_scrape_returns_records() -> None:
    calls, http_client = _success_transport(
        [{"name": "Example", "success": True}, {"success": False, "error": "blocked"}]
    )
    client = ThorDataClient(api_key="secret-token", http_client=http_client)

    result = client.scrape(
        "linkedin_company_information_by-url",
        {"url": "https://www.linkedin.com/company/example"},
    )

    assert result[0]["name"] == "Example"
    assert len(result) == 2
    client.close()


def test_scrape_rejects_untrusted_download_url() -> None:
    calls, http_client = _success_transport(
        download="https://evil.example/download?task_id=TASK-1&type=json"
    )
    client = ThorDataClient(api_key="secret-token", http_client=http_client)

    with pytest.raises(ThorDataWebScraperError) as raised:
        client.scrape_response(
            "linkedin_company_information_by-url",
            {"url": "https://www.linkedin.com/company/example"},
        )

    assert raised.value.error_code == "download_url_invalid"
    assert raised.value.task_id == "TASK-1"
    assert "secret-token" not in str(raised.value)
    client.close()
