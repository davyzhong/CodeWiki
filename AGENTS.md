# Project workflow

- Project-specific principles: [`rules/principles.md`](rules/principles.md). Read them before any milestone freeze, midterm freeze, or project closure review.

- Work directly on `main` by default.
- Do not create feature branches, development branches, or additional Git worktrees unless the user explicitly requests one.
- Push completed project work to `origin/main` after relevant verification.
- After any major product or architecture design is approved, update the authoritative project documentation and the root `README.md` in the same change. Archive the approved design artifact under `docs/`, update `docs/README.md`, and record durable decisions in `docs/knowledge/product/decision-log.md`. A design is not complete while these surfaces disagree.
