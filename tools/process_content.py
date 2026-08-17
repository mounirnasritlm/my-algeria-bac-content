#!/usr/bin/env python3
"""Full pipeline: extract → dedup → classify → map → build → validate → reform."""

import hashlib
import json
import os
import re
import shutil
import sys
from collections import defaultdict
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

TAXONOMY_DIR = BASE / "content/taxonomy"
CANONICAL_DIR = BASE / "content/canonical"
BRANCHES_DIR = BASE / "content/branches"
MAPPINGS_DIR = BASE / "content/mappings"
SOURCES_MANIFESTS_DIR = BASE / "content/sources/manifests"


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
    ("sciences_experimentales", ["علوم تجريبية", "علوم طبيعية", "sciences expérimentales", "experimentales"]),
    ("mathematiques", ["رياضيات", "mathématiques", "mathematiques", "maths"]),
    ("techniques_mathematiques", ["تقني رياضي", "math tech", "technique math"]),
    ("gestion_economie", ["تسيير", "اقتصاد", "gestion", "économie", "economie"]),
    ("lettres_philosophie", ["آداب", "فلسفة", "littéraires", "litteraires", "littéraire", "litteraire", "philosophie"]),
    ("langues_etrangeres", ["لغات أجنبية", "لغات", "langues étrangères", "langues etrangeres"]),
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
        if branch in ("lettres_philosophie", "langues_etrangeres"):
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

    text_avail_raw = load_json(BASE / "content/sources/text_availability.json") or {}
    text_entries = text_avail_raw.get("entries", [])
    text_map = {e["sha256"]: e for e in text_entries}

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

        text_info = text_map.get(sha, {}) if sha else {}
        ta = text_info.get("textAvailable", False)
        chars = text_info.get("chars", 0)
        page_count = max(1, chars // 2000) if chars > 0 else 0

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
            "pageCount": page_count,
            "textAvailable": ta,
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


# ── PUBLISH ──────────────────────────────────────────────────────

PUBLISH_DIR = BASE / "content"

def publish(version="1.0.0"):
    release_dir = RELEASES_DIR / version
    app_bundle = release_dir / "app_bundle"
    if not app_bundle.exists():
        print("publish: no app_bundle found")
        return False

    PUBLISH_DIR.mkdir(parents=True, exist_ok=True)

    for fp in app_bundle.iterdir():
        if fp.is_file():
            shutil.copy2(fp, PUBLISH_DIR / fp.name)

    manifest = load_json(PUBLISH_DIR / "manifest.json")
    doc_count = len(load_json(PUBLISH_DIR / "documents.json") or [])
    print(f"publish: {len(manifest.get('files', []))} files, {doc_count} docs -> {PUBLISH_DIR}")
    return True


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


# ── REFORM: RAW ↔ EXTRACTION LINKING ─────────────────────────────

def link_raw():
    """Generate content/sources/manifests/extraction_links.json — maps every PDF to its extracted text/JSON."""
    downloaded = load_json(DOWNLOADED_JSON) or {}
    text_avail_raw = load_json(BASE / "content/sources/text_availability.json") or {}
    text_entries = text_avail_raw.get("entries", [])
    text_map = {e["sha256"]: e for e in text_entries}

    links = []
    for sha, value in downloaded.items():
        pdf_path = f"content/sources/pdf/{sha}.pdf"
        text_info = text_map.get(sha, {})
        text_available = text_info.get("textAvailable", False)
        chars = text_info.get("chars", 0)

        entry = {
            "sha256": sha,
            "pdf_path": pdf_path,
            "pdf_exists": (PDF_DIR / f"{sha}.pdf").exists(),
            "extracted_text_path": f"content/extracted/{sha}.txt" if text_available else None,
            "extracted_json_path": None,
            "extraction_status": "complete" if text_available else "missing",
            "chars": chars,
        }
        links.append(entry)

    save_json(SOURCES_MANIFESTS_DIR / "extraction_links.json", links)
    ok = sum(1 for l in links if l["extraction_status"] == "complete")
    print(f"link_raw: {len(links)} PDFs, {ok} extracted, {len(links) - ok} missing")


# ── REFORM: SKILLS TAGGING ───────────────────────────────────────

SKILL_KEYWORDS = {
    "reading_comprehension": ["lecture", "compréhension", "texte", "lire", "document"],
    "grammar": ["grammaire", "syntaxe", "morphologie", "conjugaison", "nahu"],
    "argumentation": ["argumentation", "argumenter", "convaincre", "persuader", "débat", "thèse"],
    "analysis": ["analyse", "analyser", "commenter", "commentaire", "interpréter"],
    "synthesis": ["synthèse", "synthese", "résumé", "resume", "fiche"],
    "methodology": ["méthodologie", "methodologie", "méthode", "methodes"],
    "exam_strategy": [" stratégies", "technique d'examen", "bilan", "révision", "revision"],
    "recall": ["vocabulaire", "liste", "definitions", "définitions"],
    "application": ["application", "mise en pratique", "exercice d'application"],
    "reasoning": ["raisonnement", "logique", "déduction", "induction"],
    "problem_solving": ["problème", "probleme", "résoudre", "resoudre"],
    "calculation": ["calcul", "calculer", "opération", "operation"],
    "interpretation": ["interprétation", "interpretation", "lire", "graphique"],
    "proof": ["démonstration", "demonstration", "preuve", "prouver"],
}


def tag_skills(doc):
    """Auto-tag a document with skills based on title/category keywords."""
    haystack = f"{doc.get('title', '')} {doc.get('category', '')}".lower()
    skills = []
    for skill_id, keywords in SKILL_KEYWORDS.items():
        if any(k in haystack for k in keywords):
            skills.append(skill_id)
    return skills[:5]


def skills_tag():
    """Tag classified documents with skills and save to mappings/skill_mapping.json."""
    classified = load_json(REVIEW_DIR / "classified_documents.json") or []
    skill_map = []
    for doc in classified:
        doc_id = doc.get("sha256", "unknown")[:12]
        skills = tag_skills(doc)
        skill_map.append({
            "document_id": doc_id,
            "sha256": doc.get("sha256"),
            "skills": skills,
            "confidence": 0.6 if skills else 0.0,
            "evidence": [f"keyword_match:{s}" for s in skills],
        })
    save_json(MAPPINGS_DIR / "skill_mapping.json", skill_map)
    tagged = sum(1 for s in skill_map if s["skills"])
    print(f"skills_tag: {len(skill_map)} documents, {tagged} tagged with skills")


# ── REFORM: RELATIONSHIP LINKING ─────────────────────────────────

def link_relationships():
    """Detect and link corrections (exam→correction, BAC→correction)."""
    classified = load_json(REVIEW_DIR / "classified_documents.json") or []
    docs_by_sha = {d.get("sha256"): d for d in classified if d.get("sha256")}

    corrections = [d for d in classified if "correction" in (d.get("resourceType") or "")]
    non_corrections = [d for d in classified if "correction" not in (d.get("resourceType") or "")]

    relationships = []
    linked_count = 0

    for corr in corrections:
        corr_sha = corr.get("sha256")
        corr_title = (corr.get("title") or "").lower()
        corr_id = corr_sha[:12] if corr_sha else "unknown"

        best_match = None
        best_score = 0
        for doc in non_corrections:
            doc_sha = doc.get("sha256")
            if doc_sha == corr_sha:
                continue
            doc_title = (doc.get("title") or "").lower()
            doc_id = doc_sha[:12] if doc_sha else "unknown"

            score = 0
            if doc.get("year") == corr.get("year"):
                score += 2
            if doc.get("trimester") == corr.get("trimester"):
                score += 1
            if doc.get("branch") == corr.get("branch"):
                score += 1
            doc_words = set(doc_title.split())
            corr_words = set(corr_title.split())
            common = len(doc_words & corr_words)
            score += min(common, 3)

            if score > best_score and score >= 3:
                best_score = score
                best_match = doc

        if best_match:
            best_sha = best_match.get("sha256")
            best_id = best_sha[:12] if best_sha else "unknown"
            relationships.append({
                "type": "correction_of",
                "correction_document_id": corr_id,
                "correction_sha256": corr_sha,
                "source_document_id": best_id,
                "source_sha256": best_sha,
                "confidence": min(best_score / 6.0, 1.0),
                "evidence": [f"title_similarity", f"year_match", f"branch_match"],
            })
            linked_count += 1

    save_json(MAPPINGS_DIR / "document_relationships.json", relationships)
    print(f"relationships: {len(corrections)} corrections, {linked_count} linked to source documents")


# ── REFORM: CANONICAL STRUCTURE BUILDER ──────────────────────────

def build_canonical_structure():
    """Build canonical subject/branch mapping files from classified documents."""
    classified = load_json(REVIEW_DIR / "classified_documents.json") or []

    branch_subject_counts = defaultdict(lambda: defaultdict(int))
    subject_docs = defaultdict(list)
    branch_docs = defaultdict(list)

    for doc in classified:
        branch = doc.get("branch")
        subject = doc.get("subjectId", "french")
        branch_subject_counts[branch or "unclassified"][subject] += 1
        subject_docs[subject].append(doc.get("sha256"))
        if branch:
            branch_docs[branch].append(doc.get("sha256"))

    save_json(MAPPINGS_DIR / "document_subject.json", {
        "subject_documents": {k: v for k, v in subject_docs.items()},
        "total_by_subject": {k: len(v) for k, v in subject_docs.items()},
    })

    save_json(MAPPINGS_DIR / "document_branch.json", {
        "branch_documents": {k: v for k, v in branch_docs.items()},
        "total_by_branch": {k: len(v) for k, v in branch_docs.items()},
    })

    save_json(MAPPINGS_DIR / "document_curriculum.json", {
        "note": "Curriculum mapping is embedded in each document's curriculum field",
        "total_mapped": sum(1 for d in classified if d.get("curriculum", {}).get("projectId")),
        "total_unmapped": sum(1 for d in classified if not d.get("curriculum", {}).get("projectId")),
    })

    print(f"canonical: {len(branch_docs)} branches, {len(subject_docs)} subjects represented")
    for branch, counts in sorted(branch_subject_counts.items()):
        print(f"  {branch}: {dict(counts)}")


# ── REFORM: CONSISTENCY VALIDATION ───────────────────────────────

def validate_reform():
    """Validate the reformed repository structure — no orphans, no broken refs, no invalid IDs."""
    errors = []
    warnings = []

    branches_json = load_json(TAXONOMY_DIR / "branches.json")
    subjects_json = load_json(TAXONOMY_DIR / "subjects.json")
    matrix_json = load_json(TAXONOMY_DIR / "subject_branch_matrix.json")

    if not branches_json:
        errors.append("TAXONOMY_MISSING: branches.json")
    if not subjects_json:
        errors.append("TAXONOMY_MISSING: subjects.json")
    if not matrix_json:
        errors.append("TAXONOMY_MISSING: subject_branch_matrix.json")

    valid_branch_ids = set()
    if branches_json:
        for b in branches_json.get("branches", []):
            valid_branch_ids.add(b["branch_id"])

    valid_subject_ids = set()
    if subjects_json:
        for s in subjects_json.get("subjects", []):
            valid_subject_ids.add(s["subject_id"])

    if matrix_json:
        for entry in matrix_json.get("matrix", []):
            bid = entry.get("branch_id")
            if bid not in valid_branch_ids:
                errors.append(f"INVALID_BRANCH_IN_MATRIX: {bid}")
            for subj in entry.get("subjects", []):
                sid = subj.get("subject_id")
                if sid not in valid_subject_ids:
                    errors.append(f"INVALID_SUBJECT_IN_MATRIX: {sid} (branch: {bid})")

    classified = load_json(REVIEW_DIR / "classified_documents.json") or []
    for doc in classified:
        branch = doc.get("branch")
        if branch and branch not in valid_branch_ids:
            warnings.append(f"UNKNOWN_BRANCH: {doc.get('sha256', '??')[:8]} has branch '{branch}'")

    pdfs_on_disk = set()
    if PDF_DIR.exists():
        pdfs_on_disk = {p.stem for p in PDF_DIR.glob("*.pdf")}

    downloaded = load_json(DOWNLOADED_JSON) or {}
    for sha in downloaded:
        if sha not in pdfs_on_disk:
            warnings.append(f"PDF_NOT_DOWNLOADED: {sha[:16]}...")

    extraction_links = load_json(SOURCES_MANIFESTS_DIR / "extraction_links.json") or []
    missing_extractions = sum(1 for l in extraction_links if l.get("extraction_status") == "missing")
    if missing_extractions:
        warnings.append(f"MISSING_EXTRACTIONS: {missing_extractions} PDFs without extracted text")

    print(f"validate_reform: {len(errors)} errors, {len(warnings)} warnings")
    for e in errors[:15]:
        print(f"  ERROR: {e}")
    for w in warnings[:15]:
        print(f"  WARN:  {w}")

    is_valid = len(errors) == 0
    print(f"  valid: {is_valid}")
    return is_valid


# ── REFORM: MIGRATION REPORT ─────────────────────────────────────

def migration_report():
    """Generate a comprehensive migration report."""
    classified = load_json(REVIEW_DIR / "classified_documents.json") or []
    downloaded = load_json(DOWNLOADED_JSON) or {}

    report = {
        "generated_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "total_documents": len(classified),
        "total_downloaded": len(downloaded),
        "by_resource_type": defaultdict(int),
        "by_branch": defaultdict(int),
        "by_year": defaultdict(int),
        "by_trimester": defaultdict(int),
        "with_correction": 0,
        "without_correction": 0,
        "curriculum_mapped": 0,
        "curriculum_unmapped": 0,
        "text_available": 0,
        "text_unavailable": 0,
    }

    for doc in classified:
        report["by_resource_type"][doc.get("resourceType", "unknown")] += 1
        report["by_branch"][doc.get("branch") or "unclassified"] += 1
        if doc.get("year"):
            report["by_year"][doc["year"]] += 1
        if doc.get("trimester"):
            report["by_trimester"][doc["trimester"]] += 1
        if doc.get("correction"):
            report["with_correction"] += 1
        else:
            report["without_correction"] += 1
        if doc.get("curriculum", {}).get("projectId"):
            report["curriculum_mapped"] += 1
        else:
            report["curriculum_unmapped"] += 1

    text_avail_raw = load_json(BASE / "content/sources/text_availability.json") or {}
    for e in text_avail_raw.get("entries", []):
        if e.get("textAvailable"):
            report["text_available"] += 1
        else:
            report["text_unavailable"] += 1

    report["by_resource_type"] = dict(report["by_resource_type"])
    report["by_branch"] = dict(report["by_branch"])
    report["by_year"] = dict(report["by_year"])
    report["by_trimester"] = dict(report["by_trimester"])

    save_json(REVIEW_DIR / "migration_report.json", report)
    print(f"migration_report: {report['total_documents']} docs")
    print(f"  by_type: {report['by_resource_type']}")
    print(f"  by_branch: {report['by_branch']}")
    print(f"  curriculum: {report['curriculum_mapped']} mapped, {report['curriculum_unmapped']} unmapped")
    print(f"  text: {report['text_available']} available, {report['text_unavailable']} unavailable")


# ── REFORM: MASTER STEP ──────────────────────────────────────────

def reform():
    """Run all reform steps in sequence."""
    MAPPINGS_DIR.mkdir(parents=True, exist_ok=True)
    SOURCES_MANIFESTS_DIR.mkdir(parents=True, exist_ok=True)

    print("\n--- REFORM: Link Raw ↔ Extraction ---")
    link_raw()

    print("\n--- REFORM: Tag Skills ---")
    skills_tag()

    print("\n--- REFORM: Link Relationships ---")
    link_relationships()

    print("\n--- REFORM: Build Canonical Structure ---")
    build_canonical_structure()

    print("\n--- REFORM: Validate Consistency ---")
    validate_reform()

    print("\n--- REFORM: Migration Report ---")
    migration_report()


# ── MAIN ─────────────────────────────────────────────────────────

def main():
    steps = sys.argv[1:] if len(sys.argv) > 1 else ["extract", "dedup", "classify", "map", "build", "publish", "validate", "reform"]
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
        elif step == "publish":
            if not publish():
                sys.exit(1)
        elif step == "validate":
            if not validate():
                sys.exit(1)
        elif step == "reform":
            reform()
        elif step == "link_raw":
            link_raw()
        elif step == "skills_tag":
            skills_tag()
        elif step == "link_relationships":
            link_relationships()
        elif step == "build_canonical":
            build_canonical_structure()
        elif step == "validate_reform":
            validate_reform()
        elif step == "migration_report":
            migration_report()
        else:
            print(f"unknown step: {step}")
    print("\nAll steps complete.")


if __name__ == "__main__":
    main()
