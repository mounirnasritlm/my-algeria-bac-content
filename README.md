# my-algeria-bac-content

Content/knowledge repository for the MY Algeria BAC Flutter app and its future AI Algerian BAC Teacher.

## Current architecture

The repository is now **content-first** and uses a canonical semantic model:

```text
3AS
└── Branch
    └── Canonical Subject
        └── Curriculum Variant
            └── Project / Unit
                └── Sequence
                    └── Lesson
                        └── Concept / Skill
                            └── Resource
```

Resources are organized conceptually as:

```text
Curriculum / Programme
Courses / Lessons
Summaries
Textbooks
Teacher Books
Exercises + optional Corrections
Term 1 Devoirs / Tests + optional Corrections
Term 2 Devoirs / Tests + optional Corrections
Term 3 Devoirs / Tests + optional Corrections
Exams + optional Corrections
BAC Blanc / Mock BAC + optional Corrections
Official / Historical BAC + optional Corrections
Source metadata
PDF ↔ Extracted TXT/JSON linkage
Curriculum mapping
Skill mapping
Semantic relationships
```

## Six core 3AS branches

- Sciences Expérimentales
- Mathématiques
- Techniques Mathématiques
- Gestion et Économie
- Lettres et Philosophie
- Langues Étrangères

Techniques Mathématiques keeps four specializations under the same branch: Génie Mécanique, Génie Électrique, Génie Civil, Génie des Procédés.

## Canonical-subject rule

A subject that is shared by several branches is **stored once**. Branches reference the canonical subject and select the correct curriculum variant.

Examples:

- French: one canonical subject with branch-family variants.
- Arabic: one canonical subject with scientific/technical/management and literary/languages variants.
- English: one shared 3AS subject.
- Islamic Education: one shared 3AS subject unless authoritative evidence establishes a variant.
- Mathematics: separate curriculum variants for scientific/math/technical, management, and literary/languages.
- Philosophy: branch-family variants.
- Physics: scientific/math/technical only.
- Technology: Techniques Mathématiques only and specialization-dependent.
- Spanish/German/Italian: Langues Étrangères only.
- Economics, Law, and Accounting are separate canonical subjects for Gestion et Économie; the old `economics_management` grouping is deprecated.

See:
- `content/taxonomy/branches.json`
- `content/taxonomy/subjects.json`
- `content/taxonomy/subject_branch_matrix.json`
- `content/canonical/resource_layout.json`
- `reform.md`

## Raw source preservation

Raw PDFs and their existing extracted data are preserved. The semantic layer does not require renaming or deleting raw assets.

Every raw PDF must resolve to extracted text and/or extracted JSON through a deterministic manifest. Missing or ambiguous extraction links are explicitly marked instead of guessed.

## Corrections

Corrections are optional. A missing correction is valid and must never be fabricated.

## Review workflow

```text
raw
→ classified
→ pending_review
→ approved
→ canonical
→ released
```

Wrong, corrupt, duplicated-with-uncertain-relationship, or low-confidence documents remain preserved and are flagged for review/quarantine.

French content receives an explicit language/subject validation pass because the historical crawl contained non-French files under French-labelled categories.

## AI Teacher readiness

The semantic model is designed so the future RAG/Teacher engine can retrieve by:

`branch + subject + academic_year + curriculum_variant + lesson + skill + resource_type + term + year + correction_availability`

The teacher should prefer:

- course + summary + teacher/textbook reference for teaching;
- exercises for practice;
- tests/exams for assessment;
- historical/mock/official BAC + corrections + curriculum/skills for BAC preparation.

Student-specific mastery and personal data belong in the app/backend, not this repository.
