# T33 Evidence Flow Diagram

Data: 2026-07-16

Stato: sotto-incremento T33 completato; T33 resta aperto solo per eventuale
approvazione umana della presentazione esterna.

## Scope

Questo sotto-incremento produce il diagramma metodologico del percorso:

```text
fonti -> documenti -> evidenze -> review -> patch preview -> feedback outcome
```

Vincoli rispettati:

- nessuna scrittura nel data root esterno;
- nessuna pipeline, OCR o ricerca live;
- nessuna modifica a profili canonici;
- nessuna promozione di claim o verified facts canonici;
- nessuna applicazione di `ProfilePatch`;
- nessuna copia di documenti reali nei repository.

## Diagramma sintetico

```text
FONTI / FAMIGLIE
  legacy_csv
  local_docx
  partigiani_italia
        |
        v
DOCUMENTI SELEZIONATI
  legacy_csv:a4ac96061a2381b5
  local_docx:4c2ad1d2ab937913
  partigiani_italia:b45553cd6b1673d8
  partigiani_italia:b6b3c9e526723a27
        |
        v
CLAIM / EVIDENZE PREVIEW
  mvp_consolidated_review_ledger.json
  mvp_demo_reconciliation_table.md
        |
        v
RICONCILIAZIONE MULTI-FONTE
  3 famiglie coperte
  4/4 documenti coperti
  compatibilita': corroborated / divergent / single_source
        |
        v
REVISIONE STORICA
  review_queue.json
  review_decisions_summary.json
  10 decisioni storiche sostanziali
        |
        v
OUTPUT PREVIEW, NON CANONICI
  verified_facts.preview.json
  profile_patch.preview.json
  publication_ready=false
        |
        v
FEEDBACK LOOP T31
  research-feedback-action:7bdbb2060d955baa
  feedback-search-plan:a19b13e6e3cd8b0d
  feedback_loop_outcome.t31-demo.json
  outcome=needs_manual_review
        |
        v
PACCHETTO FINANZIATORI T33
  funding-demo-t33-package-entrypoint.md
  funding-demo-t33-demo-case-card.md
  funding-demo-t33-funding-roadmap.md
  funding-demo-t33-external-readiness-checklist.md
  funding-demo-t33-external-brief.md
```

## Mappa per il walkthrough

| Passaggio | Cosa dimostra | Artefatto o comando |
|---|---|---|
| Descriptor demo | Una sola golden run dichiarata | `memoria mvp demo --data-root "P:\Comune\Me.Mo.Ri.a"` |
| Fonti eterogenee | Il caso usa famiglie documentali diverse | `legacy_csv`, `local_docx`, `partigiani_italia` |
| Documenti identificati | Ogni evidenza torna a un documento selezionato | `source_document_ids` nel descrittore demo |
| Ledger standard | I claim sono nel flusso standard T32, non nel sidecar T30 | `mvp_consolidated_review_ledger.json` |
| Riconciliazione | Contributi convergenti o divergenti restano visibili | `mvp_demo_reconciliation_table.md` |
| Review | Lo storico decide o lascia aperto | `historian_review/review_decisions_summary.json` |
| Verified facts preview | Fatti verificati restano preview-only | `historian_review/verified_facts.preview.json` |
| ProfilePatch preview | La modifica e' proposta ma non applicata | `historian_review/profile_patch.preview.json` |
| Feedback loop | La review produce nuova ricerca o esito tracciato | `historian_review/feedback_loop_outcome.t31-demo.json` |
| Pacchetto T33 | I materiali vengono letti in ordine controllato | `funding-demo-t33-package-entrypoint.md` |

## Messaggio per finanziatori

Me.Mo.Ri.A non presenta una biografia generata automaticamente. Presenta una
catena auditabile:

1. fonti diverse entrano nello stesso caso;
2. ogni claim conserva documento e famiglia fonte;
3. la riconciliazione non cancella divergenze;
4. lo storico decide prima di ogni uso forte;
5. verified facts e patch restano preview;
6. una lacuna genera un feedback loop tracciato;
7. il finanziamento serve a scalare questo metodo senza perdere provenance.

## Safety e pubblicazione

Il diagramma deve essere mostrato insieme a questi guardrail:

- `preview_only=true`;
- `publication_ready=false`;
- `applies_profile_patch=false`;
- `creates_canonical_verified_facts=false`;
- `modifies_canonical_profiles=false`.

Questi flag non sono dettagli tecnici: sono parte del valore metodologico della
demo, perche' separano proposta automatica, decisione storica e pubblicazione.

## Uso nel pacchetto T33

Questo documento soddisfa il criterio T33:

```text
diagramma del percorso fonti-documenti-evidenze-review-feedback
```

Restano aperti:

- approvazione umana della presentazione esterna, senza rimuovere i blocker
  storici.

## Validazione

Validazione read-only eseguita:

```powershell
cd memoria-engine
.\.venv\Scripts\memoria.exe mvp demo --data-root "P:\Comune\Me.Mo.Ri.a"
```

Esito:

- descriptor presente e JSON valido;
- status `ready_for_internal_demo`;
- artefatti T30/T31/T32 presenti;
- safety flag preview-only confermate;
- nessun file del data root esterno modificato.
