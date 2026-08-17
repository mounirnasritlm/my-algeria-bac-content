# Review workflow

`raw → classified → pending_review → approved → canonical → released`

Files that are wrong, corrupted, ambiguous, or incorrectly labelled must remain preserved and be moved only by metadata/mapping into `quarantine` or `pending`.

French content receives an explicit language/subject validation pass because earlier crawls included non-French files under French-labelled categories.