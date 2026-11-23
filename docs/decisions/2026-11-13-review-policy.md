# When do we do the next pitstop review, and when do we stop?

Decided: 2026-11-13 · Case: c_938db22f-ead1-4695-b94c-fcbc926a9f78

## Question and choice
Choose a rule for pitstop reviews, so that reviews do not continue without end. Chosen, with a change: "Next review
when 0.5.2 has about 30 cycles. It only checks the 4 rules of 0.5.2 and W1; it proposes a new rule only for real
harm (lost work, wrong data, owed reply dropped). After that, no fixed reviews: a review starts only when a number
in pitstop report gets worse (gaps, resumed, owed replies). A rule ships only if the twin test does not get worse."
Change: "e poi assieme a quel check farei anche di nuovo un test su 30 cicli di pitstop contro autocompact".

## Why
- Matteo: each review can find some small problem, and past a point the work is endless perfecting that is no
  longer worth it.
- 0.5.0 already resumes 95% of cycles (`pitstop report`) and wins 12 of 15 twin tests (`docs/twin-tests.md`).
- A twin run on 30 cycles at the check gives a larger sample than the 15 sessions published in the README.

## Constraints
- Next review: when 0.5.2 has about 30 cycles in `pitstop report`. Scope: R-MARK, R-LANG, R-CMD, R-GAP and W1
  (`docs/decisions/2026-11-13-review-0-5-1.md`).
- New content rules only for real harm: lost work, wrong data, an owed reply dropped.
- Same time: a twin test pitstop vs native compact on 30 cycles, added to `docs/twin-tests.md` and the README table.
- After that check: no fixed reviews. A review starts only when a `pitstop report` number gets worse (gaps per 100
  resumes, resumed %, owed replies).
- A rule ships only if the twin test does not get worse with it.

## Ruled out
- Full review every ~50 cycles: each review finds something, so the work does not stop.
- Stop reviews now: the 0.5.2 rules would never be checked.

## Comments
- "e poi assieme a quel check farei anche di nuovo un test su 30 cicli di pitstop contro autocompact": added as a
  constraint (twin test on 30 cycles at the same time as the check).

## Threshold for "worse" (set 2026-11-23)
Case c_cebd8baf-109b-4a3a-8950-7c07f5e416cc, chosen "10 punti, max 2 perse" (`2026-11-23-release-0-5-3.md`).
A version is worse when, in a twin test on about 27 cycles:
- P's next-action-yes share falls more than 10 points below the 0.5.2 baseline of 48% (14 of 29 cycles,
  `2026-11-23-check-0-5-2-twin-test.md`), so below 38%; or
- P drops more than 2 owed replies in about 23 cycles that owe one.
Smaller moves are noise: N moved by 3 cycles between two runs of the same version.

## Open questions
—

## Sources
- Case c_938db22f-ead1-4695-b94c-fcbc926a9f78.
- `pitstop report` (0.5.0: 56 cycles, resumed 95%).
- `docs/twin-tests.md`, `docs/decisions/2026-11-13-review-0-5-1.md`.
