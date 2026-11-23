# Feedback 2026-11-23: a skipped pitstop folds the reply in T3 Code

Source: a scrawl capture (T3 Code, an offer at 187K with background tasks running). The capture is kept outside the
repo (`docs/decisions/2026-11-23-history-rewrite-privacy.md`).

| id | status | feedback (word for word) |
|---|---|---|
| F1 | done | «Molto spesso, usando pitstop, come vedi qua, che è partito il pitstop, però dice skipped, mi comprime la chat, anche se avevo un po' di roba che magari aveva senso leggere, perché ad esempio questa parte qui, se non erro, è della skill. che mi dice cosa è successo, e questa parte qui è un riassunto dell'esecuzione, quindi vorrei, non so, in qualche modo poter controllare questa cosa, e non far comprimere a T3 Code questo blocco, visto che pitstop è stato schippato e c'era qualcosa di interessante da leggere.» |

Fix: branch `fix/skip-line-folds-reply`. `Stop` asks nothing while background tasks run (they were the cause in the capture); for other skips at the end of a turn the skill repeats the closing status under the skip line.
