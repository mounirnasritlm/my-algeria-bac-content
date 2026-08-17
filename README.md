# my-algeria-bac-content

MY Algeria BAC - versioned educational content releases (JSON bundle + PDFs) consumed by the Flutter app. Designed to support a future AI Algerian BAC Teacher (RAG engine).

---

## Quick Start

```bash
# Download PDFs from crawled inventory
python tools/download_pdfs.py

# Run full pipeline (extract → dedup → classify → map → build → publish → validate → reform)
python tools/process_content.py

# Run specific steps
python tools/process_content.py extract dedup classify map build publish validate reform
```

---

## Repository Architecture

```
content/
  taxonomy/                    # Branch, subject, document type, skill definitions
  canonical/subjects/<id>/     # Canonical subject definitions + curriculum
  branches/<id>/               # Branch definitions + subject mappings
  sources/
    inventory/                 # Crawl inventory JSONs (911 entries from 3 sites)
    pdf/                       # SHA-256-named PDF files (after download)
    manifests/                 # Raw ↔ extraction linkage
  extracted/                   # Extracted plain text from PDFs
  review/                      # Classified/mapped documents + migration reports
  mappings/                    # Document ↔ subject/branch/curriculum/skill mappings
  releases/<version>/          # Versioned release bundles
```

---

## Taxonomy

- **6 standard 3AS branches**: Sciences Expérimentales, Mathématiques, Techniques Mathématiques, Gestion et Économie, Lettres et Philosophie, Langues Étrangères
- **14 canonical subjects**: French, Arabic, English, Islamic Education, Philosophy, Mathematics, Physics, Natural Sciences, History & Geography, Technology, Economics & Management, Spanish, German, Italian
- **19 document types**: curriculum_programme through unknown
- **15 pedagogical skills**: concept_understanding through exam_strategy
- **5 academic periods**: first_term, second_term, third_term, full_year, unspecified
- **6 BAC types**: bac_blanc, bac_official, bac_historical, bac_proposed, bac_subject, correction

---

## Pipeline Steps

| Step | Description |
|---|---|
| `extract` | Extract text from PDFs using pypdf |
| `dedup` | Deduplicate by SHA-256, identify mirrors |
| `classify` | Classify documents by type, branch, trimester, year |
| `map` | Map documents to curriculum (projects/sequences) |
| `build` | Build release bundle (12 app-compatible JSON collections) |
| `publish` | Copy release to stable content/ root path |
| `validate` | Validate manifest SHA-256 checksums |
| `reform` | Run all reform steps (link_raw, skills, relationships, canonical, validate, report) |

---

## Content Sources

| Source | Items | Status |
|---|---|---|
| dzexams | 300 | Crawled |
| eddirasa | 597 | Crawled |
| bac_algerie | 14 | Crawled |
| bacdz | 0 | Flaky |
| ency_education | 0 | Blocked (Cloudflare) |

---

## AI Teacher Readiness

The repository structure supports future RAG queries by:
- Branch + Subject + Curriculum + Lesson + Skill + Type + Term + Year + Correction availability
- Document relationships (exercise → correction, exam → correction)
- Skills tagging with confidence scores
- Source provenance preserved for every document

See `reform.md` for the complete reform specification.
