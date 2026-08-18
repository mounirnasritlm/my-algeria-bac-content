from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "content" / "3as" / "subjects" / "french" / "variants" / "common_or_scientific"
PDF_ROOT = OUT / "resources"
MANIFEST = OUT / "source_metadata" / "french_scientific_sources.json"

SEEDS = [
    {
        "site": "dzexams",
        "suffix": "dzexams",
        "url": "https://www.dzexams.com/ar/3as/francais/as_d1",
        "default_term": "first_term",
        "root_domain": "dzexams.com",
    },
    {
        "site": "eddirasa",
        "suffix": "eddirasa",
        "url": "https://eddirasa.com/ens-sec/3as/francais/tests-science-term-1/",
        "default_term": "first_term",
        "root_domain": "eddirasa.com",
    },
    {
        "site": "ency_education",
        "suffix": "ency_education",
        "url": "https://3as.ency-education.com/french-sci-exams.html",
        "default_term": None,
        "root_domain": "ency-education.com",
    },
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MY-Algeria-BAC-content-importer/1.1; +https://github.com/mounirnasritlm/my-algeria-bac-content)"
}

TERM_PATTERNS = [
    ("first_term", re.compile(r"premier|1er|term[ei]?-?1|الفصل\s*الأول|الفصل\s*1|1er\s*trimestre", re.I)),
    ("second_term", re.compile(r"deuxi|2[eè]me|term[ei]?-?2|الفصل\s*الثاني|الفصل\s*2|2e\s*trimestre", re.I)),
    ("third_term", re.compile(r"troisi|3[eè]me|term[ei]?-?3|الفصل\s*الثالث|الفصل\s*3|3e\s*trimestre", re.I)),
]

YEAR_RE = re.compile(r"(?:19|20)\d{2}(?:[/-](?:19|20)?\d{2})?")
CORRECTION_RE = re.compile(r"corrig|correction|corrig[eé]|solution|حل|تصحيح", re.I)
LINK_KEYWORDS_RE = re.compile(r"exemple|devoir|test|exam|composition|corrig|correction|sujet|حل|تصحيح", re.I)
PDF_RE = re.compile(r"\.pdf(?:$|[?#])", re.I)

session = requests.Session()
session.headers.update(HEADERS)


def normalize_url(base: str, href: str) -> str:
    url = urljoin(base, href.strip())
    url, _ = urldefrag(url)
    return url


def same_root_domain(url: str, seed: dict) -> bool:
    host = urlparse(url).netloc.lower().split(":")[0]
    return host == seed["root_domain"] or host.endswith("." + seed["root_domain"])


def clean_name(value: str) -> str:
    value = value.strip()
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"[\\/:*?\"<>|]+", "-", value)
    value = re.sub(r"[^\w\- .()\u0600-\u06FF]+", "-", value, flags=re.UNICODE)
    value = re.sub(r"-+", "-", value).strip(" .-")
    return value[:180] or "document"


def infer_year(text: str) -> str | None:
    m = YEAR_RE.search(text)
    return m.group(0) if m else None


def infer_term(text: str, default: str | None) -> str:
    for term, pattern in TERM_PATTERNS:
        if pattern.search(text):
            return term
    return default or "unspecified"


def fetch(url: str) -> tuple[str, str]:
    r = session.get(url, timeout=45, allow_redirects=True)
    r.raise_for_status()
    content_type = (r.headers.get("content-type") or "").lower()
    if "pdf" in content_type:
        raise ValueError("expected HTML page but received PDF")
    r.encoding = r.encoding or "utf-8"
    return r.text, r.url


def candidate_links(seed: dict) -> list[tuple[str, str, str, str | None]]:
    """Return (pdf_url, anchor_text, context_text, page_url)."""
    seen_pages: set[str] = set()
    pdfs: dict[str, tuple[str, str, str | None]] = {}
    queue: list[tuple[str, int]] = [(seed["url"], 0)]

    while queue:
        page_url, depth = queue.pop(0)
        if page_url in seen_pages or depth > 2:
            continue
        seen_pages.add(page_url)
        try:
            html, final_url = fetch(page_url)
        except Exception as exc:
            print(f"WARN page fetch failed: {page_url}: {exc}")
            continue

        soup = BeautifulSoup(html, "html.parser")
        body_text = soup.get_text(" ", strip=True)
        for a in soup.find_all("a", href=True):
            href = normalize_url(final_url, a.get("href", ""))
            if not href or href.startswith(("javascript:", "mailto:", "tel:")):
                continue
            anchor = a.get_text(" ", strip=True)
            parent = a.parent.get_text(" ", strip=True) if a.parent else anchor
            context = " ".join([anchor, parent, body_text[:1600]])

            if PDF_RE.search(href):
                pdfs[href] = (anchor, context, final_url)
                continue

            path = urlparse(href).path.lower()
            likely_document_link = bool(LINK_KEYWORDS_RE.search(" ".join([anchor, context, path])))
            if depth < 2 and (same_root_domain(href, seed) or likely_document_link) and likely_document_link:
                if href not in seen_pages:
                    queue.append((href, depth + 1))

    return [(u, a, c, p) for u, (a, c, p) in pdfs.items()]


def source_folder(term: str, is_correction: bool) -> Path:
    if is_correction:
        return PDF_ROOT / "corrections" / term
    return PDF_ROOT / {"first_term": "first_term", "second_term": "second_term", "third_term": "third_term", "unspecified": "unspecified"}.get(term, "unspecified")


def build_filename(url: str, anchor: str, suffix: str, used: set[str]) -> str:
    original = Path(urlparse(url).path).name
    stem = Path(original).stem
    if not stem or len(stem) < 3:
        stem = anchor or "document"
    stem = clean_name(stem)
    base = f"{stem}__{suffix}"
    candidate = base + ".pdf"
    if candidate in used:
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:8]
        candidate = f"{base}__{digest}.pdf"
    used.add(candidate)
    return candidate


def main() -> int:
    records: list[dict] = []
    seen_hashes: dict[str, str] = {}
    used_names: set[str] = set()
    PDF_ROOT.mkdir(parents=True, exist_ok=True)
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)

    for seed in SEEDS:
        print(f"== {seed['site']} ==")
        links = candidate_links(seed)
        print(f"found {len(links)} PDF links")
        for idx, (pdf_url, anchor, context, page_url) in enumerate(links, 1):
            combined = " ".join([anchor, context, page_url])
            term = infer_term(combined, seed["default_term"])
            is_correction = bool(CORRECTION_RE.search(" ".join([anchor, context, pdf_url])))
            folder = source_folder(term, is_correction)
            folder.mkdir(parents=True, exist_ok=True)

            filename = build_filename(pdf_url, anchor, seed["suffix"], used_names)
            destination = folder / filename
            print(f"[{idx}/{len(links)}] {pdf_url} -> {destination}")
            try:
                r = session.get(pdf_url, timeout=90, stream=True, allow_redirects=True)
                r.raise_for_status()
                content_type = (r.headers.get("content-type") or "").lower()
                if "pdf" not in content_type and not PDF_RE.search(r.url):
                    raise ValueError(f"URL did not return PDF content: {content_type} {r.url}")
                sha256 = hashlib.sha256()
                with destination.open("wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            sha256.update(chunk)
                            f.write(chunk)
                digest = sha256.hexdigest()
            except Exception as exc:
                print(f"ERROR download failed: {pdf_url}: {exc}")
                records.append({
                    "status": "failed",
                    "site": seed["site"],
                    "source_url": pdf_url,
                    "index_page": page_url,
                    "anchor": anchor,
                    "term": term,
                    "is_correction": is_correction,
                    "error": str(exc),
                })
                continue

            duplicate_of = seen_hashes.get(digest)
            if duplicate_of:
                status = "duplicate_content"
            else:
                seen_hashes[digest] = str(destination.relative_to(ROOT))
                status = "downloaded"

            records.append({
                "status": status,
                "site": seed["site"],
                "source_suffix": seed["suffix"],
                "source_url": pdf_url,
                "index_page": page_url,
                "original_filename": Path(urlparse(pdf_url).path).name,
                "anchor_text": anchor,
                "academic_year": infer_year(combined),
                "term": term,
                "document_type": "correction" if is_correction else "devoir_or_exam",
                "branch_group": "common_or_scientific",
                "subject": "french",
                "level": "3AS",
                "sha256": digest,
                "local_path": str(destination.relative_to(ROOT)),
                "duplicate_of": duplicate_of,
            })
            time.sleep(0.1)

    MANIFEST.write_text(json.dumps({
        "schema_version": "1.1",
        "subject": "french",
        "level": "3AS",
        "branch_group": "common_or_scientific",
        "generated_by": "tools/import_french_scientific.py",
        "sources": [s["url"] for s in SEEDS],
        "count": len(records),
        "records": records,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Wrote {len(records)} manifest records to {MANIFEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
