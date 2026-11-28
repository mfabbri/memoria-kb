# Codex context budget — euristiche v3.2

**Obiettivo: costo totale per ciclo storico completato**, non il minor numero
di token in una singola risposta. Non imporre quote arbitrarie di file/tokens.

1. Avvio: `AGENTS.md`, focus e summary planner (non JSON storico).
2. Ricerca: `rg --files`, `rg -n 'simbolo|heading'` e righe pertinenti; no dump.
3. Solo se cambia comportamento: modulo target + contratto + test prossimo.
4. Solo se necessario: playbook verticale specifico. Non aprire OCR, roadmap
   da 160 KB, decision log intero o 12 MB di planner per un task ordinario.
5. Delega una sola review indipendente per rischio; no parallelismo rituale.
6. Stop al rework: se due iterazioni non aumentano evidenza o non sbloccano
   il caso, documenta blocker; non generare il terzo micro-test automaticamente.
7. Checkpoint prima di compaction: obiettivo, artifact, decisioni, file, test,
   stato. Le evidenze restano persistenti fuori dal contesto del modello.
8. Misura su task omogenei: input/cached/output/reasoning se disponibili,
   retry, subagent, tempo e gate superati. Non assumere riduzioni percentuali.

Codex `/model` non implica accesso all'API con lo stesso slug; non confondere
prompt cache API e cache client. Vedi `../model-routing-policy.md`.
