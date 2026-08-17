# AI Teacher Knowledge Model

This layer defines how the static content repository is consumed by a future RAG/teacher engine.

## Resolution order

`3AS → branch → subject → academic year → curriculum variant → project/unit → sequence → lesson → concept/skill → resource`

The teacher must prefer:
- course + summary + teacher/textbook reference for explanation;
- exercises for practice;
- tests/exams for self-assessment;
- BAC history + corrections + curriculum/skills for BAC preparation.

Do not answer from a keyword hit alone. Retrieve by semantic identity and educational relationships.