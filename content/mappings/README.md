# Semantic mappings

Mappings connect raw documents to canonical educational entities without duplicating shared subjects.

Required mappings:
- document → subject
- document → branch
- document → curriculum variant
- document → lesson/project/sequence when evidence exists
- document → skills
- document → correction
- PDF → extracted text/JSON

Uncertain mappings stay `pending_review` or `quarantine`; they are not forced into canonical content.