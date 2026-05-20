"""Live URL tests. Hit the live network, marked `live` so default `pytest`
skips them. Run before every release:

    pytest tests/ -m live

The test exists because v0.1.1 shipped with three hallucinated URLs in
RESOURCE_MAP. This test ensures it cannot happen again silently.
"""

from __future__ import annotations

import pytest

from citable.promo import DEFAULT_RESOURCE, RESOURCE_MAP

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore


@pytest.mark.live
def test_all_resource_map_urls_return_200():
    """Every URL in RESOURCE_MAP must return HTTP 200 or a 3xx that ultimately
    lands on 200. A 404 here means a recommendation in the audit output would
    send users to a broken page.
    """
    assert httpx is not None, "httpx required to run live URL tests"
    failures: list[tuple[str, str, int]] = []
    with httpx.Client(timeout=20.0, follow_redirects=True) as client:
        # Check every per-check URL
        for check_id, (url, _) in RESOURCE_MAP.items():
            try:
                resp = client.get(url, headers={"User-Agent": "citable-test/0.1"})
                if resp.status_code != 200:
                    failures.append((check_id, url, resp.status_code))
            except httpx.HTTPError as e:
                failures.append((check_id, url, -1))
                print(f"  {check_id}: {url} raised {e}")
        # Check the default fallback URL
        default_url = DEFAULT_RESOURCE[0]
        try:
            resp = client.get(default_url, headers={"User-Agent": "citable-test/0.1"})
            if resp.status_code != 200:
                failures.append(("DEFAULT", default_url, resp.status_code))
        except httpx.HTTPError as e:
            failures.append(("DEFAULT", default_url, -1))
            print(f"  DEFAULT: {default_url} raised {e}")

    if failures:
        msg_lines = ["RESOURCE_MAP contains broken URLs:"]
        for check_id, url, status in failures:
            msg_lines.append(f"  {check_id}: {url} returned HTTP {status}")
        msg_lines.append(
            "\nFix: replace each broken URL with a verified live page from "
            "https://work-smart.ai/sitemap.xml and re-run this test."
        )
        pytest.fail("\n".join(msg_lines))


@pytest.mark.live
def test_resource_map_urls_are_work_smart_ai():
    """Guardrail: RESOURCE_MAP entries must point at work-smart.ai. Catches
    accidental copy-paste of a third-party URL."""
    for check_id, (url, _) in RESOURCE_MAP.items():
        assert url.startswith("https://work-smart.ai/"), (
            f"{check_id} points off-site: {url}"
        )
    assert DEFAULT_RESOURCE[0].startswith("https://work-smart.ai/")
