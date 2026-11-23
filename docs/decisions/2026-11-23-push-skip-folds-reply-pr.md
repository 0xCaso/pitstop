# Pitstop: push the fix for the folded reply and open a PR?

Decided: 2026-11-23 · Case: c_d087589c-fbca-47ae-b253-164dadc3aeac · Feedback: `docs/feedback/2026-11-23-skip-folds-reply.md`

## Question and choice
1. Push `fix/skip-line-folds-reply` and open a PR as 0xCaso? Chosen: "Push and open PR", with CI only as proof.

## Why
- A lone skip line at the end of a turn made T3 Code fold the reply; `Stop` now asks nothing while background tasks run.
- Matteo's Mac runs main from the checkout, so the merge makes the fix active at once.

## Tasks
1. **PR.** Criteria: branch pushed as 0xCaso, PR open with Conventional Commits title and "CI only" proof. From: Question and choice, item 1.
