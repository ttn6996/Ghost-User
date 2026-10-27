"""Tests for the autonomous WebCrawler and discovery engine."""

import pytest
from apps.worker.runner.crawler import WebCrawler
from tests.fixtures.server import start_fixture_server_in_background
from packages.shared.schemas import TestDefinition


def test_crawler_discovers_pages_and_forms():
    """Verifies that crawler systematically traverses pages, finds forms, and auto-generates test cases."""
    server = start_fixture_server_in_background(port=0)
    actual_port = server.server_port
    base_url = f"http://127.0.0.1:{actual_port}"

    try:
        crawler = WebCrawler(
            base_url=base_url,
            max_pages=5,
            max_depth=2,
            allow_local=True,
        )
        results = crawler.crawl()

        # Check pages found
        assert results["pages_count"] >= 2
        paths_found = [p["path"] for p in results["pages"]]
        assert "/" in paths_found
        assert "/search" in paths_found or "/login" in paths_found

        # Check forms discovered
        assert results["forms_count"] >= 1
        form_types = [f["form_type"] for f in results["forms"]]
        assert "Search Form" in form_types or "General Form" in form_types

        # Check auto-generated test cases
        assert len(results["suggested_tests"]) >= 1
        smoke_test = next(
            (t for t in results["suggested_tests"] if "Smoke Test" in t["name"]),
            None,
        )
        assert smoke_test is not None
        assert len(smoke_test["steps"]) >= 2

        # Validate that all suggested tests strictly conform to TestDefinition schema
        for test_def in results["suggested_tests"]:
            validated = TestDefinition.model_validate(test_def)
            assert len(validated.steps) > 0
    finally:
        server.shutdown()
        server.server_close()


def test_crawler_security_blocks_external_navigation():
    """Verifies that crawler does not traverse outside the authorized base origin."""
    server = start_fixture_server_in_background(port=0)
    actual_port = server.server_port
    base_url = f"http://127.0.0.1:{actual_port}"

    try:
        crawler = WebCrawler(
            base_url=base_url,
            max_pages=3,
            max_depth=1,
            allow_local=True,
        )
        results = crawler.crawl()

        # Ensure all discovered and crawled URLs strictly belong to the base origin
        for page in results["pages"]:
            assert page["url"].startswith(base_url)
    finally:
        server.shutdown()
        server.server_close()
