#!/usr/bin/env python3
"""Headless UI smoke-test for Streamlit dashboard.

Usage:
    python scripts/ui_smoke.py

Requires `playwright` (added to environment.yml).  The script:
1. Launches Streamlit on a free port.
2. Navigates through each sidebar page (Documentation, Experiments Overview, Top 5, Sweep Analysis, Experiment Analysis).
3. Checks for error boxes (`.stException`) or the word "Traceback" in page content.
4. Prints a concise report and exits with status 0 on success, 1 on failure.

It is intentionally light—no screenshots are saved; the goal is to fail fast in CI / dev_watch.
"""
from __future__ import annotations

import asyncio
import os
import random
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import List

from playwright.async_api import async_playwright, TimeoutError as PWTimeout

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PAGES_TO_TEST = [
    "Home",  # landing page
    "Documentation",
    "Experiments Overview",
    "Top 5",
    "Sweep Analysis",
    "Experiment Analysis",
]

ERROR_INDICATORS = [
    "Traceback",
    "StreamlitDuplicateElementKey",
    ".stException",
    "Could not load detail packet",
    "Malformed detail packet",
    "Could not process run",
    "Skipping",
    "Error",
]


async def assert_no_exceptions(page) -> List[str]:
    """Return list of error strings found in the current DOM."""
    errors: List[str] = []
    body_txt = await page.inner_text("body")

    for indicator in ERROR_INDICATORS:
        if indicator.startswith("."):  # CSS selector
            exc_elems = await page.query_selector_all(indicator)
    for elem in exc_elems:
        text = (await elem.inner_text()).strip()
        if text:
                    errors.append(f"Found element '{indicator}': {text[:200]}")
        else:  # Text search
            if indicator in body_txt:
                errors.append(f"Found error string: '{indicator}'")
    
    # Remove duplicates
    return sorted(list(set(errors)))


async def run_smoke(base_url: str) -> None:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        context = await browser.new_context()
        page = await context.new_page()

        for page_name in PAGES_TO_TEST:
            url = base_url
            await page.goto(url, wait_until="networkidle")
            # click sidebar item except for Home which is default
            if page_name != "Home":
                try:
                    await page.click(f"text={page_name}")
                    await page.wait_for_load_state("networkidle", timeout=10_000)
                except PWTimeout:
                    print(f"❌ Timeout loading page {page_name}")
                    await browser.close()
                    sys.exit(1)

            errors = await assert_no_exceptions(page)
            if errors:
                print(f"❌ UI errors on page '{page_name}':\n  - " + "\n  - ".join(errors))
                await browser.close()
                sys.exit(1)
            print(f"✅ {page_name} OK")

        await browser.close()


def main() -> None:
    port = random.randint(9100, 9200)
    env = os.environ.copy()
    env.setdefault("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")

    cmd = [
        "streamlit",
        "run",
        "dashboard/Home.py",
        "--server.headless",
        "true",
        "--server.port",
        str(port),
    ]

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)

    try:
        # Small delay to allow server start
        asyncio.run(asyncio.sleep(4))
        base_url = f"http://localhost:{port}"
        asyncio.run(run_smoke(base_url))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    print("🎉 UI smoke-test passed.")


if __name__ == "__main__":
    main() 