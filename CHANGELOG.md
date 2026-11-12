# Changelog

## 0.1.0

- Added an independent SERP client with synchronous and asynchronous requests.
- Added task creation, polling, downloading, and status results for seven Web Scraper products.
- Fixed SERP parameter normalization, error mapping, and Python typing metadata.
- Fixed Web Scraper contract fixtures and example entry points.
- Added request ID fallback for bare SERP results, parameter precedence, and set-value validation.
- Reused asynchronous connection pools within an event loop and improved synchronous scrape timeout guidance.
- Fixed asynchronous connection leaks when reusing a client across event loops.
