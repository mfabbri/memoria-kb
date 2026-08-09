# T33 Funding Demo Package Entrypoint

Data: 2026-08-09

Stato: entrypoint della golden run tecnica riallineato alla promozione canonica
del 2026-08-09. La demo attiva e' ora
`funding-demo-golden-3cases-v1-pipeline`; resta revisionabile, preview-only e
non pubblicabile.

## Scope

Questo documento definisce la pagina di ingresso del pacchetto finanziatori
collegata alla golden run a tre casi promossa come demo attiva.

Dal 2026-07-18 questa pagina e' l'entrypoint della **golden run tecnica**. Non va
usata come scaletta principale davanti a finanziatori. La presentazione esterna
ha un ingresso separato:

```text
memoria-bootstrap/docs/funding-demo-t33-presentation-entrypoint.md
```

Per sapere rapidamente quale run e' attiva oggi, quali comandi usare per
verificarla e come aprire eventuali nuove run candidate, leggere prima:

```text
memoria-bootstrap/docs/funding-demo-t33-current-state-operator-note.md
```

## Due oggetti, una sola run

| Oggetto | Funzione | Stato |
|---|---|---|
| Golden run tecnica | dimostrare in profondita' provenance, riconciliazione, review, patch preview e feedback loop | attiva come `funding-demo-golden-3cases-v1-pipeline` |
| Presentazione finanziatori | mostrare patrimonio disponibile, coorte pilota, prova del metodo e lavoro ancora necessario | sbloccata per prova narrativa, non ancora approvata come presentazione esterna |

La separazione riguarda pubblico, sequenza e linguaggio. Dopo la promozione,
entrambi gli oggetti devono leggere lo stesso descriptor e lo stesso `run_id`.
La run precedente resta storica; non va usata come seconda demo attiva.

Vincoli rispettati nella fase documentale iniziale:

- nessuna scrittura nel data root esterno;
- nessuna pipeline, OCR o ricerca live;
- nessuna modifica a profili canonici;
- nessuna promozione di claim o verified facts;
- nessuna applicazione di `ProfilePatch`;
- nessuna copia di dati reali nei repository.

Nota storica del 2026-07-16: dopo autorizzazione esplicita alla scrittura nel
data root esterno, erano stati rigenerati solo gli artefatti T33 del pacchetto
finanziatori nella run allora canonica:

```text
P:\Comune\Me.Mo.Ri.a\risultati\runs\prova-preview-profili-5-reviewed-01-pipeline\mvp_funding_dossier.json
P:\Comune\Me.Mo.Ri.a\risultati\runs\prova-preview-profili-5-reviewed-01-pipeline\mvp_funding_dossier.md
P:\Comune\Me.Mo.Ri.a\risultati\runs\prova-preview-profili-5-reviewed-01-pipeline\mvp_go_no_go_checklist.json
P:\Comune\Me.Mo.Ri.a\risultati\runs\prova-preview-profili-5-reviewed-01-pipeline\mvp_go_no_go_checklist.md
P:\Comune\Me.Mo.Ri.a\risultati\runs\prova-preview-profili-5-reviewed-01-pipeline\funding_package_index.md
```

Backup puntuale creato prima della rigenerazione:

```text
P:\Comune\Me.Mo.Ri.a\risultati\runs\prova-preview-profili-5-reviewed-01-pipeline\t33-package-backup-20260716-082335
```

## Golden run

Descrittore:

```text
P:\Comune\Me.Mo.Ri.a\database\memoria_mvp_demo.active.json
```

Run canonica:

```text
funding-demo-golden-3cases-v1-pipeline
```

Caso principale:

```text
person:purocielo:andreoli-dino
```

Caso di contrasto:

```text
person:purocielo:balboni-william
```

Caso complementare:

```text
person:purocielo:bendini-primo
```

Documenti selezionati principali:

| Ruolo | Source document ID | Famiglia |
|---|---|---|
| Fonte locale/tabellare | `legacy_csv:a4ac96061a2381b5` | `legacy_csv` |
| Fonte locale/documentale | `local_docx:4c2ad1d2ab937913` | `local_docx` |
| Fonte online/istituzionale A | `partigiani_italia:b45553cd6b1673d8` | `partigiani_italia` |
| Fonte online/istituzionale B | `partigiani_italia:b6b3c9e526723a27` | `partigiani_italia` |

La run canonica attiva dichiara 5 documenti complessivi; usare `memoria mvp
demo` o la nota operativa corrente per la verifica completa senza copiare dati
reali nei repository.

Stato verificato:

- descriptor valido;
- `ready_for_internal_demo`;
- 3 famiglie fonte coperte;
- 5/5 documenti coperti;
- ledger attivo standard: `mvp_consolidated_review_ledger.json`;
- `publication_ready=false`;
- `preview_only=true`.

## Lettura tecnica consigliata

Questa e' la sequenza da usare per una verifica interna o per rispondere a un
approfondimento tecnico. Non e' la scaletta della presentazione esterna.

1. **Indice pacchetto finanziatori**
   - percorso:
     `P:\Comune\Me.Mo.Ri.a\risultati\runs\funding-demo-golden-3cases-v1-pipeline\funding_package_index.md`
   - scopo: pagina di ingresso operativa generata dal builder T33.

2. **Go/no-go checklist**
   - percorso:
     `P:\Comune\Me.Mo.Ri.a\risultati\runs\funding-demo-golden-3cases-v1-pipeline\mvp_go_no_go_checklist.md`
   - scopo: mostrare `go_with_review_blockers` e il confine preview-only.

3. **Stato demo**
   - comando: `memoria mvp demo --data-root "P:\Comune\Me.Mo.Ri.a"`
   - scopo: mostrare run, profili, documenti, artefatti e safety flag.

4. **Tabella di riconciliazione**
   - percorso:
     `P:\Comune\Me.Mo.Ri.a\risultati\runs\funding-demo-golden-3cases-v1-pipeline\mvp_demo_reconciliation_table.md`
   - scopo: mostrare claim, fonte, compatibilita' o divergenza.

5. **Decisioni storiche**
   - percorso:
     `P:\Comune\Me.Mo.Ri.a\risultati\runs\funding-demo-golden-3cases-v1-pipeline\historian_review\review_decisions.validation.md`
   - scopo: mostrare che lo storico decide e che restano stati non definitivi.

6. **Verified facts preview**
   - percorso:
     `P:\Comune\Me.Mo.Ri.a\risultati\runs\funding-demo-golden-3cases-v1-pipeline\historian_review\verified_facts.preview.md`
   - scopo: mostrare fatti verificati solo come preview.

7. **ProfilePatch preview**
   - percorso:
     `P:\Comune\Me.Mo.Ri.a\risultati\runs\funding-demo-golden-3cases-v1-pipeline\historian_review\profile_patch.preview.md`
   - scopo: mostrare proposta di aggiornamento non applicata.

8. **Feedback loop**
   - percorso:
     `P:\Comune\Me.Mo.Ri.a\risultati\runs\funding-demo-golden-3cases-v1-pipeline\historian_review\feedback_loop_outcome.t31-demo.md`
   - scopo: mostrare richiesta di nuova ricerca ed esito auditabile
     `needs_manual_review`.

9. **Diagramma del percorso**
   - percorso:
     `memoria-bootstrap/docs/funding-demo-t33-evidence-flow-diagram.md`
   - scopo: spiegare il flusso fonti-documenti-evidenze-review-patch-feedback
     senza aprire artefatti tecnici.

10. **Scheda caso demo**
   - percorso:
     `memoria-bootstrap/docs/funding-demo-t33-demo-case-card.md`
   - scopo: raccontare il caso Andreoli/Balboni con provenance leggibile,
     stati preview e feedback loop senza produrre una scheda pubblicabile.

11. **Dossier finanziatori**
   - percorso:
     `P:\Comune\Me.Mo.Ri.a\risultati\runs\funding-demo-golden-3cases-v1-pipeline\mvp_funding_dossier.md`
   - scopo: dossier rigenerato con ledger consolidato e preview facts.

12. **Brief editoriale esterno**
   - percorso:
     `memoria-bootstrap/docs/funding-demo-t33-external-brief.md`
   - scopo: aprire o chiudere la presentazione con un messaggio non tecnico,
     collegato alla golden run e ai guardrail preview-only.

13. **Roadmap uso fondi**
   - percorso:
     `memoria-bootstrap/docs/funding-demo-t33-funding-roadmap.md`
   - scopo: distinguere capacita' attuali, sviluppo finanziato, visione e
     risultati attesi senza promettere pubblicazione automatica.

14. **Checklist readiness esterna**
   - percorso:
     `memoria-bootstrap/docs/funding-demo-t33-external-readiness-checklist.md`
   - scopo: dichiarare cosa e' approvabile per finanziatori e cosa resta
     bloccato per pubblicazione storica.

## Walkthrough tecnico 7-10 minuti

La tabella seguente descrive la demo tecnica attiva a tre casi. Non e' la
scaletta esterna principale: per i finanziatori usare l'entrypoint di
presentazione e mantenere questa pagina come appendice tecnica.

| Minuti | Schermata/materiale | Messaggio |
|---|---|---|
| 0:00-1:00 | `memoria mvp demo` | Una sola golden run, preview-only, non pubblicabile. |
| 1:00-2:00 | Tre casi selezionati | Perimetro piccolo: 3 profili, 5 documenti, 3 famiglie fonte. |
| 2:00-3:30 | Riconciliazione | Le fonti convergono o divergono senza perdere provenance. |
| 3:30-4:30 | Decisioni review | Lo storico conferma, lascia incerto o chiede verifica. |
| 4:30-5:30 | Verified facts preview | Le decisioni possono generare fatti preview, non canonici. |
| 5:30-6:30 | ProfilePatch preview | Il sistema propone modifiche, ma non le applica. |
| 6:30-8:00 | Feedback loop T31 | Una richiesta di nuova ricerca produce un esito tracciato. |
| 8:00-10:00 | Cosa finanziare | Scalare il metodo mantenendo provenance, revisione e audit trail. |

## Comandi fallback

Da `memoria-engine`:

```powershell
.\.venv\Scripts\memoria.exe mvp demo --data-root "P:\Comune\Me.Mo.Ri.a"
.\.venv\Scripts\memoria.exe mvp status --data-root "P:\Comune\Me.Mo.Ri.a"
.\.venv\Scripts\memoria.exe review decisions --data-root "P:\Comune\Me.Mo.Ri.a"
.\.venv\Scripts\memoria.exe consolidate status --data-root "P:\Comune\Me.Mo.Ri.a"
```

## Guardrail editoriali

- Non presentare alcun output come scheda pubblicabile.
- Non dire che `no_results` o `needs_manual_review` dimostrano assenza di un
  fatto storico.
- Non applicare `ProfilePatch`.
- Non modificare profili canonici.
- Non presentare i claim `unreviewed` come decisioni storiche.
- Non usare un archivio repository che ignori `.gitattributes`.

## Checklist T33

| Criterio T33 | Stato | Evidenza o azione |
|---|---|---|
| Dossier finanziatori breve collegato alla golden run | completato per preview | `mvp_funding_dossier.md` rigenerato nella run canonica. |
| Brief editoriale esterno | completato per preview | `funding-demo-t33-external-brief.md`. |
| Script walkthrough e fallback | completato per ingresso | Questa pagina definisce scaletta e comandi fallback. |
| Diagramma fonti-documenti-evidenze-review-feedback | completato | `funding-demo-t33-evidence-flow-diagram.md`. |
| Scheda caso demo con provenance leggibile | completato per preview | `funding-demo-t33-demo-case-card.md`. |
| Roadmap uso fondi | completato per preview | `funding-demo-t33-funding-roadmap.md`. |
| Distinzione attuale/sviluppo finanziato/visione | completato per preview | `funding-demo-t33-funding-roadmap.md`. |
| Separazione golden run/presentazione | completata in bozza, da provare narrativamente | `funding-demo-t33-presentation-entrypoint.md`. |
| Readiness presentazione esterna | demo tecnica promossa; racconto esterno ancora da provare | La presentazione deve restare meno tecnica e basata su coorte pilota, tre casi e guardrail preview-only; `mvp_go_no_go_checklist.md` resta `go_with_review_blockers`. |

## Validazione

Comandi da usare per validare lo stato attivo senza modifiche:

```powershell
cd memoria-engine
.\.venv\Scripts\memoria.exe mvp demo --data-root "P:\Comune\Me.Mo.Ri.a"
.\.venv\Scripts\memoria.exe mvp status --data-root "P:\Comune\Me.Mo.Ri.a"
```

La rigenerazione del pacchetto va eseguita solo in un incremento dedicato con
scrittura autorizzata nel data root esterno.

Revalidazione read-only del 2026-07-17:

```powershell
cd memoria-engine
.\.venv\Scripts\memoria.exe mvp demo --data-root "P:\Comune\Me.Mo.Ri.a"
```

Esito atteso e osservato:

- status `ready_for_internal_demo`;
- ledger standard presente;
- `reconciliation_table`, `review_decisions_summary`,
  `verified_facts_preview`, `profile_patch_preview` e `readiness_report`
  presenti;
- safety flag preview-only confermate;
- package index e checklist generati con esito `go_with_review_blockers`;
- nessuna modifica a profili canonici, nessuna patch applicata, nessun
  verified fact canonico creato.

## Prossimo sotto-incremento T33

T33 deve ora provare la presentazione in sei schermate sulla run canonica
promossa, senza impaginare una domanda di finanziamento e senza scegliere bando,
importo o finanziatore. La prossima revisione umana deve valutare il racconto e
la prova. Mantenere `go_with_review_blockers` finche' restano decisioni storiche
pending.
