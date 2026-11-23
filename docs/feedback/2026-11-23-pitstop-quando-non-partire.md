# Feedback 2026-11-23 · quando pitstop non deve partire

Fonte: risposta Waggle al caso c_67448f93-474b-4488-b30a-27e948691afe (weekly setup review), testo esatto.

> un'altra cosa riguardo pitstop visto che adesso facciamo dei check vorrei che ci assicurassimo che un pitstop non parta se dei sub agents stanno lavorando non so se è successo e se ha avuto problemi magari prova a dare un'occhiata e capire se è successo però in generale dobbiamo stare attenti che pitstop non parta quando non è opportuno magari se c'è una scelta in waggle e poi non la va a riprendere oppure appunto se c'è del lavoro in corso da dei sub-agents o cose di questo tipo cose che magari un pitstop potrebbe rompere. Capiamo se effettivamente questo è il caso e se è il caso cerchiamo di capire come gestirlo al meglio.

| id | punto | stato |
|---|---|---|
| F1 | Verificare se un pitstop è partito mentre dei sub-agenti lavoravano, e se ha causato problemi. | done: 0 casi (vedi S1) |
| F2 | Verificare se un pitstop è partito con una scelta Waggle aperta che poi la sessione ripresa non ha ripreso. | done: 0 scelte perse (vedi S1) |
| F3 | Se succede: capire come gestirlo al meglio, così che pitstop non parta quando può rompere lavoro in corso (sub-agenti, scelte Waggle, simili). | open: solo per F4 |
| F4 | (trovato in S1) Un thread delegato fa pitstop a fine lavoro: il padre riceve come risultato il banner di ripresa più lo stato, non il rapporto. | open |

## S1 · 2026-11-23

Metodo: `s1_scan.py` (scratchpad della sessione ec8ad7dd) su 171 cicli dei bundle `~/.claude/pitstop/reviews/20261116-030554` e `20261123-030147`. Per ogni `pitstop_done` in `~/.claude/pitstop/log.jsonl` legge il transcript fino a quel momento e cerca: `Agent` in background senza `<task-notification>`, `delegate_task` senza "Delegated task … [stato]" o `task_status` finale, `waggle_ask` pending senza `waggle_check` con risposta, `replaces` o `done: true`.

- **F1, sub-agenti:** 0 cicli con un `Agent` o `delegate_task` ancora in corso. 1 delegate (2bca4847a27a, "RuneMD: Tasks (mix)") partito 1 minuto prima: nominato nel checkpoint, risultato letto 1 minuto dopo la ripresa, nessun danno. L'hook salta già la richiesta su Stop quando ci sono task in background (`pitstop/claude/hooks.py:207`) e la skill ha la categoria `background-tasks`.
- **F2, scelte Waggle:** 42 cicli con un caso aperto. Nessuna risposta persa:
  - quasi tutti nominati nel checkpoint, risposta letta entro pochi minuti;
  - quelli non nominati sono stati ripresi lo stesso, perché all'avvio Waggle ricorda i casi aperti ("Your open asks are …"): 27892ccad2a1 +3 min, a1694d28e79c +1, 533e93b67565 +9, 18488bafbe98 +1, 0c36d8ebcdd0 +8 h, 8191d442b3a3 +37 h (Matteo ha risposto il 20/11; il ritardo non dipende da pitstop);
  - c_dc75c433 (staging AI key) aperto da giorni, letto il 20/11 06:17; gli altri "mai chiusi" sono stati sostituiti con `replaces` o chiusi con `done: true`.
- **F4, nuovo:** 24 su 211 risultati di thread delegati (11%, dal 2026-10-06) iniziano con "🔋 **pitstop** · resumed from …". Il figlio fa pitstop a fine lavoro, riparte e risponde con banner e stato. Danno piccolo: il padre a volte rilegge il thread figlio (`t3_thread_read`, es. "RuneMD: traduzione in inglese" 15/11, "Revisione PR 569" 17/11). Nessun risultato perso.

Esito: niente blocco nuovo per sub-agenti o Waggle (F1, F2). F3 resta aperto solo per F4, che va con T3 ("niente pitstop automatico a lavoro finito") nella 0.5.3: un thread delegato con il lavoro finito non fa pitstop, e il suo messaggio di ripresa non apre con il banner.
