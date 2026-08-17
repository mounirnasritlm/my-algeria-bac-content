#!/usr/bin/env python3
"""Full pipeline: extract → dedup → classify → map → build → validate."""

import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path

BASE = Path(".")
PDF_DIR = BASE / "content/sources/pdf"
EXTRACTED_DIR = BASE / "content/extracted"
REVIEW_DIR = BASE / "content/review"
RELEASES_DIR = BASE / "content/releases"
INVENTORY_DIR = BASE / "content/sources/inventory"
DOWNLOADED_JSON = BASE / "content/sources/downloaded.json"
CONFIG_DIR = BASE / "tools/config"
ASSETS_DIR = CONFIG_DIR / "assets_content"
CURRICULUM_FILE = CONFIG_DIR / "curriculum_french_3as.json"
CRAWL_CONFIG = CONFIG_DIR / "crawl_sources.json"
GITHUB_OWNER = "mounirnasritlm"
GITHUB_REPO = "my-algeria-bac-content"
GITHUB_BRANCH = "main"


def load_json(path):
    p = Path(path)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return None


def save_json(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


# ── EXTRACT ──────────────────────────────────────────────────────

def extract():
    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
    downloaded = load_json(DOWNLOADED_JSON) or {}
    if not downloaded:
        print("extract: no downloaded.json")
        return

    try:
        from pypdf import PdfReader
        tool = "pypdf"
    except ImportError:
        tool = None

    entries = []
    if not tool:
        print("extract: no PDF tool; textAvailable=false for all")
        for sha in downloaded:
            entries.append({"sha256": sha, "textAvailable": False, "chars": 0})
    else:
        ok = 0
        for i, sha in enumerate(downloaded):
            pdf_path = PDF_DIR / f"{sha}.pdf"
            txt_path = EXTRACTED_DIR / f"{sha}.txt"
            try:
                reader = PdfReader(str(pdf_path))
                parts = [page.extract_text() or "" for page in reader.pages]
                txt_path.write_text("\n".join(parts), encoding="utf-8")
                if txt_path.stat().st_size > 200:
                    ok += 1
                    entries.append({"sha256": sha, "textAvailable": True, "chars": txt_path.stat().st_size})
                else:
                    entries.append({"sha256": sha, "textAvailable": False, "chars": 0})
            except Exception as e:
                entries.append({"sha256": sha, "textAvailable": False, "chars": 0})
            if (i + 1) % 50 == 0:
                print(f"  extract: {i+1}/{len(downloaded)}")
        print(f"extract: {ok}/{len(downloaded)} text extracted using {tool}")

    save_json(BASE / "content/sources/text_availability.json", {"tool": tool, "entries": entries})


# ── DEDUP ────────────────────────────────────────────────────────

def canonical_title(titles):
    unique = list(dict.fromkeys(t for t in titles if t and t.strip()))
    if not unique:
        return None
    for t in unique:
        if re.search(r'[A-Za-z]{3,}', t):
            return t
    return max(unique, key=len)


def dedup():
    downloaded = load_json(DOWNLOADED_JSON) or {}
    canonical = []
    for sha, value in downloaded.items():
        occurrences = value.get("occurrences", [])
        titles = [o.get("title", "").strip() for o in occurrences if o.get("title")]
        title = canonical_title(titles) or "untitled"
        primary = occurrences[0] if occurrences else {}
        mirrors = [{"site": o.get("site"), "sourceUrl": o.get("sourceUrl"), "pdfUrl": o.get("pdfUrl")} for o in occurrences[1:]]
        canonical.append({
            "sha256": value.get("sha256", sha),
            "fileSize": value.get("fileSize"),
            "filePath": f"pdfs/{sha}.pdf",
            "title": title,
            "titles": list(dict.fromkeys(titles)),
            "category": primary.get("category"),
            "branchHint": primary.get("branchHint"),
            "trimesterHint": primary.get("trimesterHint"),
            "typeHint": primary.get("typeHint"),
            "yearHint": primary.get("yearHint"),
            "primary": {
                "site": primary.get("site"),
                "sourceUrl": primary.get("sourceUrl"),
                "pdfUrl": primary.get("pdfUrl"),
            },
            "mirrors": mirrors,
        })
    canonical.sort(key=lambda d: d.get("title", "").lower())
    save_json(REVIEW_DIR / "canonical_documents.json", canonical)
    print(f"dedup: {len(canonical)} canonical from {len(downloaded)} sha keys")


# ── CLASSIFY ─────────────────────────────────────────────────────

def has_any(haystack, keywords):
    return any(k in haystack for k in keywords)


CLASSIFY_TABLE = [
    ("bacSubject", ["بكالوريا", "bac", "sujet de bac"]),
    ("curriculum", ["برنامج", "programme", "curriculum"]),
    ("textbook", ["كتاب", "manuel", "livre", "textbook"]),
    ("test", ["devoir surveillé", "devoir surveille", "اختبار", "امتحان", "examen", "test", "évaluation", "evaluation"]),
    ("homework", ["فرض", "devoir", "homework"]),
    ("summary", ["ملخص", "résumé", "resume", "summary", "fiche de révision"]),
    ("lesson", ["درس", "leçon", "lecon", "cours", "lesson", "course"]),
    ("exercise", ["تمرين", "exercice", "exercise"]),
    ("pedagogicalDocument", ["مذكر", "بيداغوج", "pédagogique", "pedagogique"]),
    ("externalDocument", ["خارج", "externe", "external"]),
]

CORRECTION_KEYWORDS = ["تصحيح", "corrigé", "corrige", "correction", "solution", "الحل", "مع الحل", "نموذجي"]

CORRECTION_MAP = {
    "homework": "homework_correction",
    "test": "test_correction",
    "exam": "exam_correction",
    "bacSubject": "bac_correction",
}

BRANCH_MAP = [
    ("experimental_sciences", ["علوم تجريبية", "علوم طبيعية", "sciences expérimentales", "experimentales"]),
    ("mathematics", ["رياضيات", "mathématiques", "mathematiques", "maths"]),
    ("technical_mathematics", ["تقني رياضي", "math tech", "technique math"]),
    ("management_economics", ["تسيير", "اقتصاد", "gestion", "économie", "economie"]),
    ("literature_philosophy", ["آداب", "فلسفة", "littéraires", "litteraires", "littéraire", "litteraire", "philosophie"]),
    ("foreign_languages", ["لغات أجنبية", "لغات", "langues étrangères", "langues etrangeres"]),
    ("arts", ["فنون", "arts"]),
]

TRIMESTER_MAP = [
    ("1", ["الأول", "الاول", "premier", "1er", "1re", "فصل اول", "الفصل 1"]),
    ("2", ["الثاني", "deuxième", "deuxieme", "2e", "2eme", "فصل ثاني", "الفصل 2"]),
    ("3", ["الثالث", "troisième", "troisieme", "3e", "3eme", "فصل ثالث", "الفصل 3"]),
]

YEAR_RE = re.compile(r'\b(19|20)\d{2}\b')


def year_from(text):
    m = YEAR_RE.search(text)
    return m.group(0) if m else None


def classify_base(haystack):
    for name, keywords in CLASSIFY_TABLE:
        if has_any(haystack, keywords):
            return name
    return "unknown"


def branch_from(haystack):
    for name, keywords in BRANCH_MAP:
        if has_any(haystack, keywords):
            return name
    return None


def trimester_from(haystack):
    for name, keywords in TRIMESTER_MAP:
        if has_any(haystack, keywords):
            return name
    return None


def classify():
    docs = load_json(REVIEW_DIR / "canonical_documents.json") or []
    output = []
    for doc in docs:
        title = (doc.get("title") or "").lower()
        category = (doc.get("category") or "").lower()
        primary = doc.get("primary", {})
        pdf_url = (primary.get("pdfUrl") or "").lower()
        haystack = f"{title} {category} {pdf_url}"
        correction = has_any(haystack, CORRECTION_KEYWORDS)
        base = classify_base(haystack)
        resource_type = CORRECTION_MAP.get(base, base) if correction else base
        output.append({
            **doc,
            "resourceType": resource_type,
            "branch": branch_from(haystack),
            "trimester": trimester_from(haystack),
            "year": year_from(f"{title} {pdf_url}"),
            "correction": correction,
        })
    save_json(REVIEW_DIR / "classified_documents.json", output)
    print(f"classify: {len(output)} documents classified")


# ── MAP ──────────────────────────────────────────────────────────

PROJECT_KEYWORDS = {
    "p1": ["histoire", "historique", "fait d'histoire", "texte historique", "تاريخ"],
    "p2": ["débat", "debat", "dialoguer", "confronter", "points de vue", "convaincre", "persuader", "نقاش", "حوار"],
    "p3": ["appel", "exhortatif", "inciter", "mobiliser", "humanitaire"],
    "p4": ["fantastique", "nouvelle fantastique", "imaginaire", "رعب"],
}

SEQUENCE_KEYWORDS = {
    "p1_s1": ["fait d'histoire", "informer", "exposer"],
    "p1_s2": ["témoignage", "temoin"],
    "p1_s3": ["analyser", "commenter", "analyse"],
    "p2_s1": ["convaincre", "persuader", "inscrire"],
    "p2_s2": ["concéder", "conceder", "réfuter", "refuter", "position"],
    "p3_s1": ["enjeu", "structurer"],
    "p3_s2": ["inciter", "agir"],
    "p4_s1": ["cadre réaliste", "realiste", "introduire"],
    "p4_s2": ["exprimer", "imaginaire"],
    "p4_s3": ["enjeu", "comprendre"],
}


def filiere_group(doc):
    branch = doc.get("branch")
    if branch:
        if branch in ("literature_philosophy", "foreign_languages", "arts"):
            return "lettres_langues_etrangeres"
        return "techniques_sciences"
    hint = doc.get("branchHint")
    if hint == "literary":
        return "lettres_langues_etrangeres"
    if hint == "scientific":
        return "techniques_sciences"
    return "unknown"


def map_docs():
    docs = load_json(REVIEW_DIR / "classified_documents.json") or []
    output = []
    for doc in docs:
        title = (doc.get("title") or "").lower()
        category = (doc.get("category") or "").lower()
        primary = doc.get("primary", {})
        pdf_url = (primary.get("pdfUrl") or "").lower()
        haystack = f"{title} {category} {pdf_url}"

        project_id = None
        sequence_id = None
        best_project = 0
        for pid, kws in PROJECT_KEYWORDS.items():
            score = sum(1 for k in kws if k in haystack)
            if score > best_project:
                best_project = score
                project_id = pid

        evidence = []
        if project_id and best_project > 0:
            evidence.append(f"project_keywords:{project_id}")
            evidence.extend(f"kw:{k}" for k in PROJECT_KEYWORDS[project_id] if k in haystack)
            best_seq = 0
            for sid, kws in SEQUENCE_KEYWORDS.items():
                if not sid.startswith(project_id):
                    continue
                score = sum(1 for k in kws if k in haystack)
                if score > best_seq:
                    best_seq = score
                    sequence_id = sid
            if sequence_id and best_seq > 0:
                evidence.append(f"sequence_keywords:{sequence_id}")
                evidence.extend(f"kw:{k}" for k in SEQUENCE_KEYWORDS[sequence_id] if k in haystack)

        fg = filiere_group(doc)
        if project_id and sequence_id and best_project >= 1:
            status, confidence = "content_supported", 0.9
        elif project_id and best_project >= 1:
            status, confidence = "probable", 0.6
        else:
            status, confidence = "pending_review", 0.0
            project_id = sequence_id = None

        if project_id == "p3" and fg == "techniques_sciences":
            status, confidence = "pending_review", 0.0
            project_id = sequence_id = None

        if fg != "unknown":
            evidence.append(f"filiere:{fg}")

        output.append({
            **doc,
            "curriculum": {
                "projectId": project_id,
                "sequenceId": sequence_id,
                "darsIds": [],
                "status": status,
                "confidence": confidence,
                "evidence": evidence[:8],
            },
        })
    save_json(REVIEW_DIR / "mapped_documents.json", output)
    print(f"map: {len(output)} documents mapped")


# ── BUILD ────────────────────────────────────────────────────────

def build(version="1.0.0"):
    mapped = load_json(REVIEW_DIR / "mapped_documents.json") or []
    downloaded = load_json(DOWNLOADED_JSON) or {}
    crawl_root = load_json(CRAWL_CONFIG)
    curriculum = load_json(CURRICULUM_FILE)

    sources = [{
        "id": "demo_source", "type": "demo", "name": "MY Algeria BAC demo content",
        "author": "MY Algeria BAC", "url": None, "publication": None, "year": "2026", "verified": False,
    }]
    for site in crawl_root.get("sites", []):
        sources.append({
            "id": f"site_{site['id']}", "type": "website", "name": site["name"],
            "author": None, "url": site.get("baseUrl"), "publication": None,
            "year": None, "verified": False,
        })

    raw_base = f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}/{GITHUB_BRANCH}/content/pdfs"

    documents = []
    counter = 0
    for md in mapped:
        counter += 1
        primary = md.get("primary", {})
        sha = md.get("sha256")
        has_file = sha and sha in downloaded and (PDF_DIR / f"{sha}.pdf").exists()
        pdf_url = f"{raw_base}/{sha}.pdf" if has_file else primary.get("pdfUrl")
        mirrors = [m.get("pdfUrl") for m in md.get("mirrors", []) if m.get("pdfUrl")]
        doc_id = f"d_{sha[:8]}" if sha else f"d_{primary.get('site', 'unknown')}_{counter}"
        documents.append({
            "id": doc_id,
            "title": md.get("title"),
            "subjectId": "french",
            "level": "3AS",
            "branch": md.get("branch"),
            "resourceType": md.get("resourceType"),
            "year": md.get("year"),
            "trimester": md.get("trimester"),
            "sourceId": f"site_{primary.get('site', 'unknown')}",
            "sourceUrl": primary.get("sourceUrl"),
            "additionalSourceUrls": mirrors,
            "retrievedAt": (downloaded.get(sha) or {}).get("downloadedAt") if sha else None,
            "sha256": sha if has_file else None,
            "fileSize": md.get("fileSize"),
            "pageCount": 0,
            "textAvailable": False,
            "pdfUrl": pdf_url,
            "curriculum": md.get("curriculum"),
            "relatedDocumentIds": [],
            "verified": False,
        })

    subjects_path = ASSETS_DIR / "subjects.json"
    subjects = load_json(subjects_path) or []
    if not any(s.get("id") == "french" for s in subjects):
        subjects.append({
            "id": "french",
            "names": {"ar": "اللغة الفرنسية", "fr": "Français", "en": "French"},
            "icon": "🗣️", "chapterIds": [], "lessonIds": [], "order": 3,
        })

    release_dir = RELEASES_DIR / version
    app_bundle = release_dir / "app_bundle"
    app_bundle.mkdir(parents=True, exist_ok=True)

    for collection in ["chapters.json", "lessons.json", "concepts.json", "questions.json",
                       "exams.json", "solutions.json", "teachers.json", "videos.json", "worksheets.json"]:
        src = ASSETS_DIR / collection
        if src.exists():
            shutil.copy(src, app_bundle / collection)

    save_json(app_bundle / "subjects.json", subjects)
    save_json(app_bundle / "sources.json", sources)
    save_json(app_bundle / "documents.json", documents)

    manifest_files = []
    for collection in ["subjects.json", "chapters.json", "lessons.json", "concepts.json",
                       "questions.json", "exams.json", "solutions.json", "sources.json",
                       "teachers.json", "videos.json", "worksheets.json", "documents.json"]:
        fp = app_bundle / collection
        if fp.exists():
            data = fp.read_bytes()
            manifest_files.append({"path": collection, "sha256": sha256_bytes(data)})

    save_json(app_bundle / "manifest.json", {
        "schemaVersion": "1.0.0",
        "contentVersion": version,
        "updatedAt": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "files": manifest_files,
    })

    pdf_out = release_dir / "pdfs"
    pdf_out.mkdir(parents=True, exist_ok=True)
    pdf_count = 0
    for md in mapped:
        sha = md.get("sha256")
        if not sha:
            continue
        src = PDF_DIR / f"{sha}.pdf"
        dst = pdf_out / f"{sha}.pdf"
        if src.exists() and not dst.exists():
            shutil.copy(src, dst)
            pdf_count += 1

    if CURRICULUM_FILE.exists():
        shutil.copy(CURRICULUM_FILE, release_dir / "curriculum.json")

    print(f"build: release {version} -> {release_dir}")
    print(f"  documents={len(documents)}, sources={len(sources)}, pdfs={pdf_count}, subjects={len(subjects)}")


# ── VALIDATE ─────────────────────────────────────────────────────

def validate(version="1.0.0"):
    release_dir = RELEASES_DIR / version
    app_bundle = release_dir / "app_bundle"
    if not app_bundle.exists():
        print("validate: no app_bundle found")
        return False

    manifest = load_json(app_bundle / "manifest.json")
    if not manifest:
        print("validate: manifest.json missing")
        return False

    documents = load_json(app_bundle / "documents.json") or []
    sources = load_json(app_bundle / "sources.json") or []
    errors = []
    warnings = []

    for f in manifest.get("files", []):
        fp = app_bundle / f["path"]
        if not fp.exists():
            errors.append(f"MANIFEST_FILE_MISSING: {f['path']}")
            continue
        actual = sha256_bytes(fp.read_bytes())
        if actual != f["sha256"]:
            errors.append(f"MANIFEST_SHA_MISMATCH: {f['path']}")

    for doc in documents:
        if not doc.get("title"):
            warnings.append(f"NO_TITLE: {doc.get('id')}")
        if not doc.get("sourceUrl") and not doc.get("pdfUrl"):
            warnings.append(f"NO_SOURCE: {doc.get('id')}")

    missing_pdfs = 0
    for doc in documents:
        sha = doc.get("sha256")
        if sha and not (release_dir / "pdfs" / f"{sha}.pdf").exists():
            missing_pdfs += 1

    total = len(errors) + len(warnings)
    print(f"validate: {len(documents)} docs, {len(sources)} sources, {len(manifest.get('files', []))} bundle files")
    print(f"  errors={len(errors)} warnings={len(warnings)} missing_pdfs={missing_pdfs}")
    for e in errors[:10]:
        print(f"  ERROR: {e}")
    for w in warnings[:10]:
        print(f"  WARN:  {w}")

    is_valid = len(errors) == 0 and missing_pdfs == 0
    print(f"  valid: {is_valid}")
    return is_valid


# ── MAIN ─────────────────────────────────────────────────────────

def main():
    steps = sys.argv[1:] if len(sys.argv) > 1 else ["extract", "dedup", "classify", "map", "build", "validate"]
    for step in steps:
        print(f"\n{'='*60}\n  {step.upper()}\n{'='*60}")
        if step == "extract":
            extract()
        elif step == "dedup":
            dedup()
        elif step == "classify":
            classify()
        elif step == "map":
            map_docs()
        elif step == "build":
            build()
        elif step == "validate":
            if not validate():
                sys.exit(1)
        else:
            print(f"unknown step: {step}")
    print("\nAll steps complete.")


if __name__ == "__main__":
    main()
