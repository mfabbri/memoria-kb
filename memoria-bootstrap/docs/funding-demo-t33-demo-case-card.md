# T33 Demo Case Card

Data: 2026-07-16

Stato: sotto-incremento T33 completato; scheda caso demo preview-only per
walkthrough finanziatori.

## Scope

Questa scheda rende leggibile il caso demo della golden run senza aprire i JSON
tecnici e senza trasformare gli output in una scheda pubblicabile.

Vincoli rispettati:

- nessuna scrittura nel data root esterno;
- nessuna pipeline, OCR o ricerca live;
- nessuna modifica a profili canonici;
- nessuna promozione di claim o verified facts canonici;
- nessuna applicazione di `ProfilePatch`;
- nessuna copia di documenti reali nei repository.

## Golden run

Descrittore:

```text
P:\Comune\Me.Mo.Ri.a\database\memoria_mvp_demo.active.json
```

Run canonica:

```text
prova-preview-profili-5-reviewed-01-pipeline
```

Ledger attivo:

```text
P:\Comune\Me.Mo.Ri.a\risultati\runs\prova-preview-profili-5-reviewed-01-pipeline\mvp_consolidated_review_ledger.json
```

Stato:

- `ready_for_internal_demo`;
- `preview_only=true`;
- `publication_ready=false`;
- `not_publishable_without_human_review`;
- 3 famiglie fonte coperte;
- 4/4 documenti selezionati coperti;
- 30 righe di riconciliazione.

## Caso

Profilo principale:

```text
person:purocielo:andreoli-dino
```

Profilo di contrasto leggero:

```text
person:purocielo:balboni-william
```

La scheda dimostra un percorso, non una biografia definitiva. Il valore per la
demo e' mostrare che documenti diversi entrano nello stesso profilo di lavoro,
che il sistema conserva la provenance e che lo storico mantiene il controllo su
decisioni, patch e pubblicazione.

## Documenti selezionati

| Ruolo | Documento | Famiglia | Stato nella golden run |
|---|---|---|---|
| Fonte locale/tabellare | `legacy_csv:a4ac96061a2381b5` | `legacy_csv` | coperto dalla riconciliazione |
| Fonte locale/documentale | `local_docx:4c2ad1d2ab937913` | `local_docx` | coperto dalla riconciliazione |
| Fonte online/istituzionale A | `partigiani_italia:b45553cd6b1673d8` | `partigiani_italia` | coperto dalla riconciliazione e da decisioni preview |
| Fonte online/istituzionale B | `partigiani_italia:b6b3c9e526723a27` | `partigiani_italia` | coperto dalla riconciliazione |

## Lettura provenance

| Aspetto | Cosa mostra | Provenance |
|---|---|---|
| Identita' nel perimetro locale | Il caso e' collegato al profilo principale anche da materiale locale/tabellare. | `legacy_csv:a4ac96061a2381b5`, campo `identity.canonical_name`, metodo `ledger_standard_from_candidate_document_person_link`. |
| Contesto documentale locale | Il documento locale contribuisce piste su formazione e collegamenti al profilo, lasciate in stato `unreviewed`. | `local_docx:4c2ad1d2ab937913`, campo `formation.name`, metodo `document_entity_context_rules` con proiezione standard dal documento collegato. |
| Conferma nominativa online | Due record `partigiani_italia` corroborano nome, cognome e nome completo nel ledger di lavoro. | `partigiani_italia:b45553cd6b1673d8` e `partigiani_italia:b6b3c9e526723a27`, compatibilita' `corroborated`. |
| Divergenze da non appiattire | Serie archivistica, commissione, formazione e qualifica mantengono valori divergenti o singola fonte. | `mvp_demo_reconciliation_table.md`, compatibilita' `divergent` e `single_source`. |
| Decisione dello storico | Una parte dei claim e dei link documentali ha decisione `confirm` accettata, con reviewer e data. | `historian_review/review_decisions_summary.md`, 10 decisioni sostanziali nella run. |
| Preview facts | Alcune decisioni alimentano `VerifiedFactPreview`, non fatti canonici. | `historian_review/verified_facts.preview.md`, 8 fatti preview. |
| Patch preview | Le proposte di aggiornamento restano operazioni non applicate. | `historian_review/profile_patch.preview.md`, 2 patch profilo e 8 operazioni preview. |
| Feedback loop | La review produce una ricerca tracciata con esito `needs_manual_review`. | `historian_review/feedback_loop_outcome.t31-demo.md`, action `research-feedback-action:7bdbb2060d955baa`. |

## Snodo multi-fonte

La demo non dice che tutte le fonti concordano. Dice qualcosa di piu' utile per
la ricerca storica:

- `legacy_csv` e `local_docx` portano segnali locali nel perimetro del profilo;
- `partigiani_italia` porta record strutturati online;
- i campi nominativi sono corroborati da record indipendenti;
- altri campi restano divergenti o a fonte singola;
- la divergenza resta visibile nella tabella di riconciliazione invece di
  essere risolta automaticamente.

Distribuzione delle righe nel descriptor attivo:

| Compatibilita' | Righe |
|---|---:|
| `corroborated` | 6 |
| `divergent` | 20 |
| `single_source` | 4 |

## Decisione e patch

La catena da mostrare nel walkthrough e':

```text
claim candidato
  -> documento sorgente
  -> decisione storica accettata
  -> verified fact preview
  -> ProfilePatch preview
  -> nessuna applicazione automatica
```

Esempio di lettura, senza promozione canonica:

| Passaggio | Artefatto |
|---|---|
| Decisione storica | `historian_review/review_decisions_summary.md` |
| Fatti preview | `historian_review/verified_facts.preview.md` |
| Patch proposta | `historian_review/profile_patch.preview.md` |
| Safety flag | `memoria_mvp_demo.active.json` |

Le operazioni patch sono proposte tecniche: non modificano profili JSON-LD, non
scrivono nello evidence store e non rendono pubblicabile la scheda.

## Feedback loop

Il feedback loop T31 chiude la parte metodologica che interessa ai finanziatori:
la review non produce solo una lista di query, ma un esito auditabile.

| Campo | Valore |
|---|---|
| Action | `research-feedback-action:7bdbb2060d955baa` |
| Piano | `feedback-search-plan:a19b13e6e3cd8b0d` |
| Profilo | `person:purocielo:andreoli-dino` |
| Fonte/sessione | `storia_memoria_bo` |
| Esito | `needs_manual_review` |
| Effetto | aggiorna la memoria di ricerca preview, senza promuovere claim |

Questo esito non dimostra l'assenza o la presenza di un fatto storico. Dimostra
che la ricerca successiva e' tracciata e non viene ripetuta come se nulla fosse
accaduto.

## Uso nel walkthrough

Questa scheda soddisfa il criterio T33:

```text
scheda del caso demo con provenance leggibile
```

Ordine consigliato:

1. aprire `funding-demo-t33-package-entrypoint.md`;
2. mostrare questa scheda per raccontare il caso;
3. aprire `mvp_demo_reconciliation_table.md` per le righe di provenance;
4. aprire `verified_facts.preview.md` e `profile_patch.preview.md` per la
   decisione preview;
5. chiudere con `feedback_loop_outcome.t31-demo.md`.

## Guardrail

- Non presentare questa scheda come pubblicabile.
- Non leggere i valori `unreviewed` come decisioni storiche.
- Non applicare le patch preview.
- Non trasformare `needs_manual_review` in prova storica.
- Non separare la scheda dal descriptor della golden run.

## Validazione

Validazione read-only eseguita:

```powershell
cd memoria-engine
.\.venv\Scripts\memoria.exe mvp demo --data-root "P:\Comune\Me.Mo.Ri.a"
```

Esito atteso:

- descriptor presente e JSON valido;
- status `ready_for_internal_demo`;
- 3 famiglie fonte coperte;
- 4/4 documenti coperti;
- safety flag preview-only confermate.
