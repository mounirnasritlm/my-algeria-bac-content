#!/usr/bin/env python3
"""Download PDFs from inventory JSONs, compute SHA-256, commit results."""

import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PDF_DIR = Path("content/sources/pdf")
INV_DIR = Path("content/sources/inventory")
DOWNLOADED_JSON = Path("content/sources/downloaded.json")
URL_INDEX_JSON = Path("content/sources/url_index.json")
FAILED_JSON = Path("content/sources/failed_downloads.json")
USER_AGENT = "MY-Algeria-BAC-content-pipeline/1.0 (educational archive)"
MAX_RETRIES = 3
DELAY_BETWEEN = 0.3
MAX_BYTES = 50 * 1024 * 1024  # 50 MB


def load_json(path):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def download_url(url, retries=MAX_RETRIES):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=60) as resp:
                if resp.status != 200:
                    return None, resp.status, None
                data = resp.read()
                if len(data) > MAX_BYTES:
                    return None, None, f"too_large:{len(data)}"
                return data, 200, None
        except urllib.error.HTTPError as e:
            if e.code in (403, 404, 410):
                return None, e.code, None
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            return None, getattr(e, "code", None), str(e)
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            return None, None, str(e)
    return None, None, "max_retries"


def extract_tasks():
    """Extract unique pdfUrls from all inventory JSONs."""
    tasks = []
    seen = set()
    for jf in sorted(INV_DIR.glob("*.json")):
        if jf.name.startswith("_") or jf.name.endswith("_errors.json"):
            continue
        items = load_json(jf)
        if not isinstance(items, list):
            continue
        site_id = jf.stem
        for item in items:
            url = item.get("pdfUrl") or item.get("sourceUrl")
            if not url or url in seen:
                continue
            seen.add(url)
            tasks.append({
                "site": site_id,
                "url": url,
                "title": item.get("title"),
                "sourceUrl": item.get("sourceUrl"),
                "category": item.get("category"),
                "branch": item.get("branchHint"),
                "trimester": item.get("trimesterHint"),
                "type": item.get("typeHint"),
                "year": item.get("yearHint"),
            })
    return tasks


def main():
    PDF_DIR.mkdir(parents=True, exist_ok=True)

    downloaded = load_json(DOWNLOADED_JSON)
    url_index = load_json(URL_INDEX_JSON)
    failed = []

    tasks = extract_tasks()
    print(f"Found {len(tasks)} unique URLs to download")

    new_files = 0
    skipped = 0
    for i, task in enumerate(tasks):
        url = task["url"]
        if url in url_index:
            skipped += 1
            continue

        data, status, error = download_url(url)
        if data is None:
            entry = {"url": url, "site": task["site"], "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
            if status:
                entry["status"] = status
            if error:
                entry["error"] = error
            failed.append(entry)
            print(f"  [{i+1}/{len(tasks)}] FAIL {status or error} {url[:80]}")
            continue

        sha = sha256_bytes(data)
        (PDF_DIR / f"{sha}.pdf").write_bytes(data)
        url_index[url] = sha

        occurrence = {k: v for k, v in task.items() if v is not None}
        if sha in downloaded:
            downloaded[sha]["occurrences"].append(occurrence)
        else:
            downloaded[sha] = {
                "sha256": sha,
                "fileSize": len(data),
                "occurrences": [occurrence],
                "downloadedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
        new_files += 1
        print(f"  [{i+1}/{len(tasks)}] OK {sha[:12]}  {url[:70]}")

        # save checkpoints every 50 files
        if new_files % 50 == 0:
            save_json(DOWNLOADED_JSON, downloaded)
            save_json(URL_INDEX_JSON, url_index)

        time.sleep(DELAY_BETWEEN)

    save_json(DOWNLOADED_JSON, downloaded)
    save_json(URL_INDEX_JSON, url_index)
    save_json(FAILED_JSON, failed)

    print(f"\nDone: {new_files} new, {skipped} cached, {len(failed)} failed, {len(downloaded)} total unique")
    return 0


if __name__ == "__main__":
    sys.exit(main())
