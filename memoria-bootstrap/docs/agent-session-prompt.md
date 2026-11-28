# Prompt quotidiano Codex — source-first (2026-11-21)

Da Codex aperto nella root con `AGENTS.md`:

```text
Leggi AGENTS.md e memoria-bootstrap/docs/current-focus.md. Esegui
python memoria-bootstrap/planning/current-work-summary.py.

Se c'e' un incremento aperto, riprendilo solo se coerente con la decisione
source-first del 2026-11-21. Se e' completato (snapshot: T84), usa la
sola sezione T85-T89 della roadmap tecnica per la prossima slice.

Priorita': un risultato su fonti/documenti reali o un blocker dimostrato.
Non selezionare micro-test, hardening, CLI o refactor non richiesti da un
blocco nel percorso SourceDocument -> EvidenceClaim -> review -> feedback.
OCR T41, pCloud T27/T28 e una nuova golden run sono esclusi.

Definisci una slice con obiettivo, evidenza documentale attesa, write set
minimo, test piu' mirato e stop condition. Non aprire la successiva alla
chiusura. Usa skill/contratti on-demand; seleziona model/delega secondo
policy v3.2, verificando disponibilita' con /model. Usa il launcher memoria
per i workflow di prodotto.

Non eseguire ricerche live senza autorizzazione esplicita per source_id,
query/attempt; non simulare review ne' modificare profili canonici. Se manca
un prerequisito, riporta il blocker e fermati, senza sostituirlo con fixture.
Concludi con artefatti, fonti, stati di review, test, limiti e prossimo passo.
```

Comando breve riutilizzabile:

```text
Leggi memoria-bootstrap/docs/agent-session-prompt.md ed esegui la procedura.
```

Per dettaglio in base al task: `docs/playbooks/online-source-research-review.md`,
`docs/playbooks/codex-person-profile-feedback-loop-core.md`,
`docs/playbooks/codex-session-contract.md` e skill mirate. Le procedure OCR
sono consultabili solo su richiesta esplicita.
