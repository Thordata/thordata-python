# Thordata Python SDK

Python client for the Thordata SERP API and seven verified Web Scraper products. The package is independent of LangChain and uses the real Thordata form endpoints.

> Next-generation Thordata Python SDK for new projects.
> This repository is the future primary Python SDK and is now publicly available on PyPI.

Turn live web data into working applications faster. Thordata Python SDK gives Python teams one interface for SERP search and structured web scraping, so you can power research, monitoring, enrichment, RAG, and AI agent workflows without maintaining a separate scraper for every target.

Use it to track search visibility, enrich business data, monitor products and markets, or bring fresh web data into your own applications and pipelines.

## Why Thordata Python SDK

- **Search and scrape through one client**: Query live search engines and collect structured records through ready-to-use Web Scraper actions.
- **Built for real workflows**: Move from a proof of concept to research, monitoring, enrichment, and AI data pipelines with the same Python interface.
- **Flexible execution**: Use synchronous or asynchronous calls while keeping the request model consistent.
- **Ready for downstream systems**: Send structured results into analytics, RAG, agents, and internal applications.
- **Designed for dependable use**: Benefit from connection reuse, bounded task polling, redacted diagnostics, and predictable response handling.

Create a Thordata account to get started:

- [Get started with Thordata](https://www.thordata.com/?ls=github&lk=thordata)
- [Read the official documentation](https://doc.thordata.com)

## Install

```bash
pip install thordata
```

Set `THORDATA_API_KEY`, `THORDATA_API_TOKEN`, or the compatible `TALORDATA_API_TOKEN` environment variable. An explicit `api_key` argument takes precedence.

## SERP

```python
from thordata import Client

with Client() as client:
    result = client.search(
        {"q": "latest AI agent research", "gl": "us", "hl": "en"},
        engine="google_search",
    )
    print(result)
```

The client submits form data to `https://scraperapi.thordata.com/request` with Bearer authentication. SERP source headers are `Origin: Python`, `platform: python`, and `api-source: sdk`. It supports the verified engines and API-native parameters from the Thordata service. `google_search` maps to `google`, `google_places` maps to `google_local`, and `query`, `country`, and `language` map to `q`, `gl`, and `hl`. Yandex sends `q` as `text`. Boolean values become `1` or `0`, and unknown fields are ignored.

Use `search_response()` when task metadata and the raw response envelope are needed, and `raw_search()` when the unparsed response body is needed. `task_id` is taken from the upstream envelope when present and falls back to `search_metadata.id` for bare SERP results. The raw response keeps the engine-specific shape; Google commonly returns `organic`/`images`/`places`, while other engines may return `organic_results` or similar fields. `raw_search()` returns text without interpreting business error codes. Use `asearch()` and `asearch_response()` for asynchronous calls; one client reuses its async connection pool within the event loop and `aclose()` releases it. The SDK does not expose `search_html()` because the current `/request` endpoint does not guarantee an HTML response.

## Web Scraper

The initial SDK supports these spider IDs:

- `linkedin_company_information_by-url`: `url`
- `linkedin_job_listings_information_by-job-url`: `job_url`
- `youtube_video-post_by-keyword`: `keyword`, optional `num_of_posts`
- `facebook_profile_by-profiles-url`: `url`
- `youtube_video-post_by-explore`: `url`, optional `all_tabs`
- `twitter_profile_by-profileurl`: `url`
- `amazon_product_by-category-url`: `url`, `page_turning`, optional `sort_by`

```python
from thordata import Client

with Client() as client:
    records = client.scrape(
        "linkedin_company_information_by-url",
        {"url": "https://www.linkedin.com/company/microsoft"},
    )
    print(records)
```

`scrape()` submits one task, polls every five seconds, and downloads the final JSON records. Web Scraper source fields are form parameters `api_source=sdk` and `source_platform=python`; they are not request headers. Amazon uses `Best Sellers` when `sort_by` is omitted. A client permits one active synchronous scrape at a time; asynchronous scrapes do not use that synchronous lock. If a synchronous scrape times out, its worker may still be finishing briefly; retry after the reported active-operation message. The total wait is capped at 300 seconds by default. Use `scrape_response()` to receive `task_id`, `spider_id`, `status`, `record_count`, and `error_record_count`. Status is `completed`, `partial`, or `empty`. `ascrape()` and `ascrape_response()` provide asynchronous equivalents.

Web Scraper errors retain their stage and task ID when safe, while API keys and signed URLs are redacted from exception text and returned diagnostic data.

## Local checks

```bash
python -m pytest -q tests
ruff check .
python -m build .
```

The tests use an in-memory HTTP transport and do not consume Thordata credits. See `examples/` for runnable SERP and Web Scraper examples.

## Start Building

Start with one SERP query, add a Web Scraper action when you need structured records, and connect the results to the systems your team already uses. The same workflow can support a quick experiment today and a repeatable data pipeline tomorrow.

[Explore Thordata Web Scraper](https://www.thordata.com/products/web-scraper?op=flora&from=github) | [Explore Thordata SERP API](https://www.thordata.com/products/serp-api?op=flora&from=github)
