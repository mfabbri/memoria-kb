# Prompt quotidiano Codex — post-MVP (2026-11-14)

Da Codex avviato nella **root che contiene `AGENTS.md`**:

```text
Leggi AGENTS.md e memoria-bootstrap/docs/current-focus.md; esegui
python memoria-bootstrap/planning/current-work-summary.py.

Se il planner ha un incremento aperto, verificane validità e riprendilo.
Altrimenti seleziona la prima slice utile dalla roadmap tecnica e dal gap
misurato piu' recente (attualmente T53-T59c),
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

## Note operative emerse dalle sessioni T55/T59

- Se l'utente indica una directory locale e autorizza una scansione ricorsiva,
  limita l'inventario a quella radice e includi le sottodirectory. Non trattare
  una lista superficiale della cartella radice come scansione completa; riporta
  copertura, file pertinenti e limiti incontrati. Non estendere la scansione ad
  altre radici senza perimetro esplicito.
- Se servono dati o una decisione dell'utente, formula la richiesta indicando
  esattamente il campo/elemento mancante e il passaggio che sblocca. Raccogli le
  decisioni una per volta quando riguardano claim distinti; `accept_candidate`
  mantiene una candidatura e non promuove un fatto.
- Per claim con `evidence_span`, verifica la citazione esatta nel testo acquisito
  identificato dal `source_document_id`. Un mismatch è diagnostico: non
  correggere automaticamente il claim o la receipt umana; conserva la decisione
  precedente e richiedi una nuova review se la correzione è necessaria.
- Per copie locali con `original_source_document_id`, conserva il riferimento
  nel sidecar e valuta il legame tramite preview esplicita di SourceDocument.
  Membership del catalogo non prova equivalenza; preview e memory view non
  fondono documenti, fonti indipendenti o record canonici.

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
