# Repository Reform Plan

**Repository:** `mounirnasritlm/my-algeria-bac-content`
**Date:** 2026-08-17
**Status:** Active — Phase 0

---

## 1. Reform Goal

Transform this repository from a flat content dump into a hierarchical, AI-teacher-ready knowledge structure. The final system must support a future RAG-based AI Algerian BAC Teacher that can:

1. Explain a lesson
2. Explain a concept simply
3. Give a hint instead of the answer
4. Ask a diagnostic question
5. Generate/retrieve an exercise
6. Correct an exercise
7. Explain why an answer is wrong
8. Detect a skill weakness
9. Recommend a prerequisite lesson
10. Create a revision plan
11. Prepare for BAC
12. Simulate a BAC
13. Analyze historical BAC question patterns
14. Track student mastery

---

## 2. Core Principles

- **Content is data, never hardcoded in widgets** — the app consumes JSON bundles
- **SHA-256 duplicate key** — one canonical document per unique PDF, mirrors preserved as source records
- **No fabricated URLs, years, branches, or corrections** — `verified: false` by default
- **PDFs never ship in APK** — only metadata and extracted text; PDFs are viewed on-demand via `pdfUrl`
- **Source provenance preserved** — every document retains full download/crawl history
- **Confidence scores with evidence** — every classification includes confidence + reasoning
- **Manual validation workflow** — owner validates subject-by-subject; uncertain documents go to review/quarantine
- **No student data in this repository** — student state belongs to the app/backend

---

## 3. Semantic Hierarchy

```
Student
  → 3AS (level)
    → Branch
      → Subject
        → Academic Year
          → Curriculum / Programme
            → Project / Unit
              → Sequence
                → Lesson
                  → Concept / Skill
                    → Resources:
                      - Course
                      - Summary
                      - Textbook
                      - Teacher Book
                      - Exercise
                      - Exercise Correction
                      - Homework
                      - Homework Correction
                      - Test
                      - Test Correction
                      - Exam
                      - Exam Correction
                      - Mock BAC
                      - Mock BAC Correction
                      - Official BAC
                      - Official BAC Correction
```

---

## 4. Target Repository Architecture

```
content/
  taxonomy/
    branches.json                    # 6 standard 3AS branches
    subjects.json                    # canonical subject definitions
    subject_branch_matrix.json       # which subjects belong to which branches
    document_types.json              # document type taxonomy
    academic_periods.json            # trimester/year taxonomy
    bac_types.json                   # BAC classification taxonomy
    skills.json                      # controlled vocabulary of pedagogical skills

  canonical/
    subjects/
      <subject_id>/
        subject.json                 # subject definition, aliases, variants
        curriculum/
          <variant_id>.json          # curriculum mapping per branch variant
        lessons/                     # empty until content arrives
        summaries/
        books/
        teacher_books/
        exercises/
        assessments/
        exams/
          bac/
          corrections/
        relationships.json           # exercise→correction, exam→correction links

  branches/
    <branch_id>/
      branch.json                    # branch definition
      subjects.json                  # subject mappings (points to canonical)

  sources/
    raw/
      pdf/                           # SHA-256-named PDF files
      metadata/                      # crawl metadata per source
    extracted/
      text/                          # extracted plain text
      json/                          # structured extraction output
    inventory/                       # crawl inventory JSONs (existing)
    manifests/
      documents.json                 # full document inventory
      source_files.json              # PDF ↔ extraction linkage
      extraction_links.json          # raw PDF ↔ extracted JSON mapping

  review/
    pending/                         # auto-classified, awaiting manual review
    approved/                        # manually verified, ready for canonical
    rejected/                        # manually rejected
    quarantine/                      # unclassifiable or problematic

  mappings/
    document_subject.json            # document → canonical subject mapping
    document_branch.json             # document → branch mapping
    document_curriculum.json         # document → curriculum variant mapping
    document_relationships.json      # inter-document relationships
    skill_mapping.json               # document → skills mapping

  releases/
    <version>/
      manifest.json                  # release manifest
      curriculum.json                # curriculum data
      content/                       # app-compatible JSON bundles
      mappings/                      # release-specific mappings
```

---

## 5. Taxonomy: Branches

Six standard 3AS branches:

| ID | Name (FR) | Name (AR) | Name (EN) |
|---|---|---|---|
| `sciences_experimentales` | Sciences Expérimentales | علوم تجريبية | Experimental Sciences |
| `mathematiques` | Mathématiques | رياضيات | Mathematics |
| `techniques_mathematiques` | Techniques Mathématiques | تقني رياضي | Technical Mathematics |
| `gestion_economie` | Gestion et Économie | تسيير واقتصاد | Management & Economics |
| `lettres_philosophie` | Lettres et Philosophie | آداب وفلسفة | Literature & Philosophy |
| `langues_etrangeres` | Langues Étrangères | لغات أجنبية | Foreign Languages |

**Notes:**
- "Arts" exists in some contexts but is NOT a core branch. Treat as optional/explicitly unsupported unless evidence requires it.
- Techniques Mathématiques has specializations (Génie Mécanique, Électrique, Civil, des Procédés) — model as options under the branch, NOT as separate branches.

---

## 6. Taxonomy: Subjects

### Canonical Subject Model

Each subject has a stable ID independent of branch:

```json
{
  "subject_id": "french",
  "canonical_name": "Français",
  "aliases": ["French", "اللغة الفرنسية"],
  "level": "3AS",
  "variants": [
    {
      "variant_id": "common_or_scientific",
      "description": "Shared curriculum for scientific/math/technical/management branches",
      "branches": [
        "sciences_experimentales",
        "mathematiques",
        "techniques_mathematiques",
        "management_economie"
      ],
      "curriculum_id": "french_common"
    },
    {
      "variant_id": "letters_and_languages",
      "description": "Curriculum for literary and foreign language branches",
      "branches": [
        "lettres_philosophie",
        "langues_etrangeres"
      ],
      "curriculum_id": "french_letters"
    }
  ]
}
```

### Subject Classification Rules

A subject can be:
- **A) Truly shared** — identical content across all branches (e.g., Islamic Education)
- **B) Shared with branch-specific curriculum** — same subject identity, different curriculum/resources per branch (e.g., French, Philosophy, Mathematics)
- **C) Branch-specific** — only taught in specific branches (e.g., Physics in scientific branches only)

### Initial Subject Matrix (to be validated from repository evidence)

**Common / Generally Shared:**
- Arabic
- Islamic Education
- English
- French
- History & Geography

**Branch-Variant Subjects (may share identity, need curriculum variants):**
- Philosophy
- Mathematics
- Arabic
- French
- English
- History & Geography

**Scientific / Technical:**
- Mathematics (scientific/math/technical variant)
- Physics
- Natural Sciences (Sciences Expérimentales primary)
- Technology (Techniques Mathématiques specializations)

**Management:**
- Mathematics (management variant)
- Economics / Management / Law
- Accounting & Financial Management

**Literary / Languages:**
- Arabic (literary variant)
- Philosophy (literary variant)
- History & Geography (literary variant)
- French (literary variant)
- English (literary variant)
- Third foreign language(s): Spanish / German / Italian (Langues Étrangères only)

**IMPORTANT:** Do not invent subject presence. Build the actual matrix from repository evidence and authoritative curriculum documents.

---

## 7. Taxonomy: Document Types

Every document must be classified into one primary type:

| ID | Description |
|---|---|
| `curriculum_programme` | Official curriculum/programme document |
| `course_lesson` | Lesson content / course material |
| `summary` | Lesson summary / revision notes |
| `textbook` | Student textbook |
| `teacher_book` | Teacher's guide/resource book |
| `exercise` | Single exercise or problem |
| `exercise_collection` | Collection of exercises |
| `homework` | Homework / assignment (devoir) |
| `test` | Test / quiz (interro) |
| `exam` | Exam / examination |
| `mock_bac` | Mock BAC exam (bac blanc) |
| `bac` | Official BAC exam |
| `correction` | Correction/answer key (separate resource) |
| `answer_key` | Answer key (may be embedded) |
| `methodology` | Methodology guide |
| `reference` | Reference material |
| `pedagogical_document` | General pedagogical resource |
| `other` | Unclassified |
| `unknown` | Cannot determine type |

A document can also have **secondary tags** (e.g., `["grammar", "argumentation"]`).

---

## 8. Taxonomy: Academic Periods

| ID | Name (FR) | Name (AR) |
|---|---|---|
| `first_term` | Premier trimestre | الفصل الأول |
| `second_term` | Deuxième trimestre | الفصل الثاني |
| `third_term` | Troisième trimestre | الفصل الثالث |
| `full_year` | Année complète | سنوي |
| `unspecified` | Non spécifié | غير محدد |

Do not force a term onto a document if the source does not establish it.

---

## 9. Taxonomy: BAC Types

| ID | Description |
|---|---|
| `bac_blanc` | Mock BAC exam ( blanc) |
| `bac_official` | Official BAC exam |
| `bac_historical` | Historical BAC exam (any year) |
| `bac_proposed` | Proposed/practice BAC exam |
| `bac_subject` | BAC subject/prompt (may be part of a larger exam) |
| `correction` | Correction of a BAC exam |

---

## 10. Taxonomy: Skills

Controlled vocabulary for pedagogical metadata:

| ID | Description |
|---|---|
| `concept_understanding` | Understanding of a concept |
| `recall` | Memorization and recall |
| `application` | Applying knowledge to new situations |
| `reasoning` | Logical reasoning |
| `problem_solving` | Solving problems |
| `reading_comprehension` | Understanding written texts |
| `grammar` | Grammar knowledge and application |
| `argumentation` | Building arguments |
| `analysis` | Analyzing texts/problems |
| `synthesis` | Synthesizing information |
| `calculation` | Mathematical calculation |
| `interpretation` | Interpreting data/texts |
| `proof` | Mathematical proof |
| `methodology` | Methodological approach |
| `exam_strategy` | Exam-taking strategy |

Do not invent arbitrary skills for every file. Prefer this controlled vocabulary and extend only when needed.

---

## 11. Document Schema

### Canonical Document

```json
{
  "document_id": "doc_abc123",
  "title": "Devoir surveillé n°1 - Français - Sciences Expérimentales",
  "subject_id": "french",
  "level": "3AS",
  "branch": "sciences_experimentales",
  "resourceType": "test",
  "academicPeriod": "first_term",
  "year": "2024",
  "curriculum": {
    "variant_id": "common_or_scientific",
    "projectId": "p1",
    "sequenceId": "p1_s1",
    "status": "probable",
    "confidence": 0.6,
    "evidence": ["project_keywords:p1", "kw:histoire"]
  },
  "skills": ["reading_comprehension", "grammar", "argumentation"],
  "has_correction": true,
  "correction_document_id": "doc_def456",
  "verified": false,
  "confidence": 0.85,
  "confidenceEvidence": ["content_language:french", "subject_match:french", "branch_hint:scientific"],
  "source": {
    "site": "eddirasa",
    "sourceUrl": "https://eddirasa.com/...",
    "pdfUrl": "https://eddirasa.com/files/...",
    "originalTitle": "...",
    "retrievedAt": "2026-08-17T00:00:00Z"
  },
  "sha256": "abc123...",
  "fileSize": 123456,
  "pageCount": 4,
  "textAvailable": true,
  "extraction": {
    "extracted_text_path": "sources/extracted/text/abc123.txt",
    "extracted_json_path": "sources/extracted/json/abc123.json",
    "extraction_status": "complete"
  },
  "mirrors": [
    {
      "site": "dzexams",
      "sourceUrl": "https://dzexams.com/...",
      "pdfUrl": "https://dzexams.com/..."
    }
  ],
  "status": "canonical",
  "reviewStatus": "approved"
}
```

### Source File Record

```json
{
  "sha256": "abc123...",
  "pdfPath": "sources/raw/pdf/abc123.pdf",
  "fileSize": 123456,
  "extractedTextPath": "sources/extracted/text/abc123.txt",
  "extractedJsonPath": "sources/extracted/json/abc123.json",
  "extractionStatus": "complete",
  "documentId": "doc_abc123",
  "occurrences": [
    {
      "site": "eddirasa",
      "sourceUrl": "https://eddirasa.com/...",
      "pdfUrl": "https://eddirasa.com/files/...",
      "title": "...",
      "category": "exam_t1_sciences",
      "crawledAt": "2026-08-17T00:00:00Z"
    }
  ]
}
```

---

## 12. Deduplication Rules

1. **SHA-256 is the primary duplicate key** — identical PDFs from different sites are one canonical document with multiple source records (mirrors).
2. **Normalized title + source URL** — for near-duplicates or revised editions.
3. **Do not delete duplicates** — classify them:
   - `exact_duplicate` — identical content, different source
   - `mirrored_source` — same PDF hosted on multiple sites
   - `revised_edition` — updated version of the same document
   - `branch_variant` — same document adapted for a different branch
   - `genuinely_distinct` — different content despite similar titles

---

## 13. Confidence Scoring

| Range | Label | Action |
|---|---|---|
| 0.95–1.00 | High confidence | Auto-approve (if evidence is strong) |
| 0.80–0.94 | Acceptable | Review recommended but not blocking |
| 0.60–0.79 | Low confidence | Manual review required |
| <0.60 | Very low | Quarantine / unresolved |

Confidence is computed from:
- Language detection (is it actually French?)
- Subject matching (does content match declared subject?)
- Branch matching (does metadata match branch hints?)
- Curriculum alignment (does content match a known curriculum unit?)
- Source reliability (is the source known and trusted?)

---

## 14. Review / Quarantine Workflow

```
RAW (downloaded PDF)
  → AUTO CLASSIFIED (pipeline assigns metadata)
    → PENDING REVIEW (stored in review/pending/)
      → MANUALLY VERIFIED (stored in review/approved/)
        → CANONICAL (stored in canonical/subjects/<id>/)
          → RELEASED (included in release bundle)
```

Quarantine triggers:
- Wrong subject detected
- Wrong branch detected
- Wrong year/grade
- Unreadable / corrupted PDF
- Malformed extraction
- Duplicate with uncertain relationship
- Unknown document type
- Language mismatch (e.g., claimed French but actually Arabic)

---

## 15. Correction Rules

A correction is a **separate resource** when the source is separate:

```json
{
  "exam_document_id": "doc_abc123",
  "correction_document_id": "doc_def456",
  "has_correction": true,
  "correction_source": "separate_file"
}
```

If the correction is embedded in the same document:
```json
{
  "document_id": "doc_abc123",
  "has_correction": true,
  "correction_source": "embedded",
  "correction_pages": [5, 6, 7]
}
```

If no correction exists:
```json
{
  "correction_document_id": null,
  "has_correction": false,
  "correction_source": null
}
```

**NEVER generate a fake correction to fill a field.**

---

## 16. Raw PDF ↔ Extracted JSON Requirement

**Mandatory.** For every raw PDF:

```json
{
  "document_id": "doc_abc123",
  "sha256": "abc123...",
  "pdf_path": "sources/raw/pdf/abc123.pdf",
  "extracted_text_path": "sources/extracted/text/abc123.txt",
  "extracted_json_path": "sources/extracted/json/abc123.json",
  "extraction_status": "complete"
}
```

If a PDF has no extracted JSON yet:
- `extraction_status: "missing"`
- Document goes to `review/pending/` for processing

If a JSON exists but doesn't correspond to the PDF:
- `extraction_status: "unresolved"`
- Do not link based on filename similarity alone

---

## 17. Branch-Subject Deduplication

**Critical:** Do NOT duplicate the same content across branches when the curriculum is identical.

Example — French as a shared subject:
```
canonical/subjects/french/
  subject.json                    # canonical definition
  curriculum/
    common_or_scientific.json     # shared by scientific/math/technical/management
    letters_and_languages.json    # shared by literary/languages

branches/sciences_experimentales/subjects/french.json  → points to canonical, variant: common_or_scientific
branches/mathematiques/subjects/french.json            → points to canonical, variant: common_or_scientific
branches/techniques_mathematiques/subjects/french.json → points to canonical, variant: common_or_scientific
branches/gestion_economie/subjects/french.json         → points to canonical, variant: common_or_scientific
branches/lettres_philosophie/subjects/french.json      → points to canonical, variant: letters_and_languages
branches/langues_etrangeres/subjects/french.json       → points to canonical, variant: letters_and_languages
```

**Exception:** Some subjects that share a name are NOT identical across branches:
- Arabic: different 3AS book/curriculum for scientific vs literary
- Mathematics: scientific/math/technical vs literary/management have different curricula
- Philosophy: multiple curriculum groupings
- Physics: primarily scientific/technical, not literary
- Natural Sciences: primarily Sciences Expérimentales

Use evidence from actual curriculum, books, and repository metadata to decide.

---

## 18. Execution Phases

### Phase 0: Reform Documentation
- Create this `reform.md` document
- **Status: COMPLETE**

### Phase 1: Taxonomy & Schema Files
Create `content/taxonomy/` with 7 JSON files:
- `branches.json` — 6 standard 3AS branches
- `subjects.json` — canonical subject definitions (French full, others stubs)
- `subject_branch_matrix.json` — subject × branch mapping
- `document_types.json` — document type taxonomy
- `academic_periods.json` — trimester/year taxonomy
- `bac_types.json` — BAC classification taxonomy
- `skills.json` — controlled vocabulary of pedagogical skills

### Phase 2: Canonical Subject Structure
Create `content/canonical/subjects/french/`:
- `subject.json` — full subject definition with variants
- `curriculum/common_or_scientific.json` — P1-P4 for scientific branches
- `curriculum/letters_and_languages.json` — P1-P4 for literary/languages
- Empty subdirectories for lessons, summaries, exercises, exams, bac, corrections
- `relationships.json` — empty initially

### Phase 3: Branch Structure
Create `content/branches/` with 6 branch directories:
- `branch.json` — branch definition (ID, names, description)
- `subjects.json` — subject mappings pointing to canonical

### Phase 4: Pipeline Refactor
Refactor `tools/process_content.py`:
- Output to new directory structure
- Generate raw↔extraction linkage
- Add skills tagging
- Add relationship linking (corrections)
- Add subject deduplication
- Add consistency validation

### Phase 5: Migration & Validation
- Run refactored pipeline on 911 inventory entries
- Generate migration report
- Validate consistency
- Produce human-readable summary

### Phase 6: Build Compatibility Layer
- Transform rich structure into 12 app-compatible JSON collections
- Ensure Flutter app continues to work without changes
- Generate release manifest

### Phase 7: Documentation
- Update README.md
- Document architecture, taxonomy, workflow
- Document AI Teacher data requirements

---

## 19. App Compatibility Notes

The Flutter app currently expects 12 JSON collections:
- `subjects`, `chapters`, `lessons`, `concepts`, `questions`, `exams`, `solutions`, `sources`, `teachers`, `videos`, `worksheets`, `documents`

The build compatibility layer (Phase 6) will transform the rich canonical structure into these 12 collections. Future app changes (not in this reform) may consume the richer structure directly.

Key app model fields that must be preserved:
- `Document.id`, `title`, `subjectId`, `branch`, `resourceType`, `year`, `trimester`
- `Document.sha256`, `pdfUrl`, `textAvailable`, `pageCount`
- `Document.curriculum` (projectId, sequenceId, darsIds, status, confidence, evidence)
- `Document.verified`, `relatedDocumentIds`

---

## 20. Validation Checklist

Before considering the migration complete:

- [ ] No raw educational source is lost
- [ ] Every PDF has a deterministic extraction relationship or explicit "missing" status
- [ ] Shared subjects are not duplicated unnecessarily
- [ ] Branch-specific curricula can coexist without duplicating canonical subjects
- [ ] Misclassified files can be identified and manually corrected
- [ ] Corrections remain optional (no fabricated corrections)
- [ ] Source provenance is preserved
- [ ] Curriculum mapping is explicit and reviewable
- [ ] The resulting structure supports a future AI Teacher/RAG system
- [ ] The app can query content by: branch, subject, curriculum, lesson, skill, type, term, year, correction availability
- [ ] No student-specific data is stored in the content repository
- [ ] Machine-readable inventory/report generated covering:
  - Branches, subjects, shared subjects, branch-specific subjects
  - Curriculum variants
  - Document counts by type, term, BAC distribution
  - Documents with/without corrections
  - PDFs without extracted JSON
  - Extracted JSON without PDF
  - Unresolved classifications
  - Low-confidence mappings
  - Duplicates
  - Quarantined files

---

## 21. Current Inventory

| Source | Items | Status |
|---|---|---|
| dzexams | 300 | Crawled |
| eddirasa | 597 | Crawled |
| bac_algerie | 14 | Crawled |
| bacdz | 0 | Flaky (errors) |
| ency_education | 0 | Blocked (Cloudflare 403) |
| **Total** | **911** | **Inventory only** |

Pipeline has NOT been run. No PDFs downloaded, no extractions, no releases.

---

## 22. Pipeline Bug Fixes Applied

1. `download_pdfs.py` returns exit code 0 always (failures are non-fatal, logged to `failed_downloads.json`)
2. `process_content.py build` reads `text_availability.json` for `textAvailable` and `pageCount`
3. `process_content.py publish` step copies release to stable `content/` root path
4. CI workflow uses `if: success() || failure()` and `if: always()` for commit step
