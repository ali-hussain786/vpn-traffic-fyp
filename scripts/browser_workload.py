#!/usr/bin/env python3
"""Repeatable browser and public-document download workload."""
import argparse
import hashlib
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

PHASES = [
    ("text_navigation", [
        "https://example.com/",
        "https://www.wikipedia.org/",
        "https://www.python.org/",
    ]),
    ("technical_docs", [
        "https://developer.mozilla.org/en-US/docs/Web/HTTP",
        "https://docs.python.org/3/",
        "https://www.iana.org/",
    ]),
    ("images_media", [
        "https://commons.wikimedia.org/wiki/Main_Page",
        "https://unsplash.com/",
        "https://www.nasa.gov/",
    ]),
    ("technical_reference", [
        "https://www.wireshark.org/docs/",
        "https://fedoraproject.org/",
        "https://www.gnu.org/",
    ]),
    ("public_documents", [
        "https://www.rfc-editor.org/rfc/rfc9293.html",
        "https://www.rfc-editor.org/",
        "https://www.iana.org/domains/reserved",
    ]),
    ("search_navigation", [
        "https://www.wikipedia.org/",
        "https://www.python.org/",
        "https://developer.mozilla.org/",
    ]),
]

DOWNLOADS = [
    "https://www.rfc-editor.org/rfc/rfc9293.pdf",
    "https://www.rfc-editor.org/rfc/rfc9110.pdf",
]

def download_document(url, folder):
    """Download a fixed public PDF, record size/hash, then remove the temporary file."""
    name = url.rsplit("/", 1)[-1]
    path = Path(folder) / name
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "VPN-Traffic-FYP-Research/1.0"}
    )
    try:
        digest = hashlib.sha256()
        total = 0
        with urllib.request.urlopen(request, timeout=30) as response, path.open("wb") as out:
            while True:
                chunk = response.read(64 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                digest.update(chunk)
                total += len(chunk)
        print(
            f"DOWNLOAD_OK url={url} bytes={total} sha256={digest.hexdigest()}",
            flush=True
        )
    except Exception as exc:
        print(f"DOWNLOAD_ERROR url={url} error={type(exc).__name__}: {exc}", flush=True)
    finally:
        path.unlink(missing_ok=True)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=int, default=1800)
    args = parser.parse_args()

    start = time.monotonic()
    end_at = start + args.duration
    phase_len = args.duration / (len(PHASES) + 1)
    print(f"START duration={args.duration}s browser_phases={len(PHASES)} download_phase=1", flush=True)

    with tempfile.TemporaryDirectory(prefix="vpn-fyp-downloads-") as temp_dir:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": 1365, "height": 768},
                locale="en-US",
                timezone_id="UTC",
            )
            context.set_default_navigation_timeout(25000)
            page = context.new_page()
            try:
                for phase_i, (name, urls) in enumerate(PHASES):
                    phase_end = min(end_at, time.monotonic() + phase_len)
                    print(f"PHASE {phase_i + 1}/{len(PHASES) + 1} {name}", flush=True)

                    # Visit each phase URL once, in the same order each session.
                    for url in urls:
                        if time.monotonic() >= phase_end or time.monotonic() >= end_at:
                            break
                        print(f"NAVIGATE {url}", flush=True)
                        try:
                            page.goto(url, wait_until="domcontentloaded", timeout=12000)
                            for y in (0, 450, 900, 450, 0):
                                if time.monotonic() >= phase_end or time.monotonic() >= end_at:
                                    break
                                page.evaluate("(y) => window.scrollTo(0, y)", y)
                                time.sleep(1)
                        except Exception as exc:
                            print(f"BROWSER_ERROR {url}: {type(exc).__name__}: {exc}", flush=True)
                            # Replace a page whose navigation may still be pending.
                            try:
                                page.close()
                            except Exception:
                                pass
                            page = context.new_page()
                            context.set_default_navigation_timeout(25000)

                    # Hold the phase boundary to keep the session schedule repeatable.
                    remaining_phase = min(phase_end, end_at) - time.monotonic()
                    if remaining_phase > 0:
                        time.sleep(remaining_phase)

                if time.monotonic() < end_at:
                    print(f"PHASE {len(PHASES) + 1}/{len(PHASES) + 1} controlled_downloads", flush=True)
                    # Attempt each fixed document once in the download phase.
                    for url in DOWNLOADS:
                        if time.monotonic() >= end_at:
                            break
                        print(f"DOWNLOAD_START {url}", flush=True)
                        download_document(url, temp_dir)

                # Keep total workload duration aligned to the session duration.
                remaining = end_at - time.monotonic()
                if remaining > 0:
                    print(f"FINAL_DWELL seconds={remaining:.1f}", flush=True)
                    time.sleep(remaining)
            finally:
                context.close()
                browser.close()

    print("END workload", flush=True)

if __name__ == "__main__":
    main()
