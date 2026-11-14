# Prompt quotidiano Codex — post-MVP (2026-11-14)

Da Codex avviato nella **root che contiene `AGENTS.md`**:

```text
Leggi AGENTS.md e memoria-bootstrap/docs/current-focus.md; esegui
python memoria-bootstrap/planning/current-work-summary.py.

Se il planner ha un incremento aperto, verificane validità e riprendilo.
Altrimenti seleziona la prima slice utile T53-T58 dalla roadmap tecnica,
rispettando dipendenze, dati accessibili e decisioni utente. Non selezionare
OCR T41 o pCloud T27/T28 senza una nuova richiesta esplicita.

Definisci obiettivo verificabile, write set, prova/test mirati e stop condition.
Leggi soltanto codice, contratti e skill necessari; esegui la slice fino alla
verifica e aggiorna il planner senza cancellare lo storico. Non delegare per
abitudine. Usa solo CLI installata `memoria` per i workflow di prodotto.

Non avviare ricerche live senza perimetro autorizzato, né applicare modifiche
canoniche o decisioni storiche. Non simulare dati o review umana.
Concludi con file modificati, risultati, test, limiti e prossimo candidato.
```

Per processi dettagliati, caricare **solo quando pertinenti**:

- `docs/playbooks/online-source-research-review.md`: CLI e dati reali;
- `docs/playbooks/codex-person-profile-feedback-loop-core.md`: claim/review;
- `docs/playbooks/codex-session-contract.md`: applicazione canonica;
- `docs/playbooks/codex-document-analysis-core.md`: OCR, sospeso;
- `.agents/skills/memoria-planner/SKILL.md`: scritture robuste del planner.

L'entrypoint operativo rimane anche il comando breve:

```text
Leggi memoria-bootstrap/docs/agent-session-prompt.md ed esegui la procedura.
```
