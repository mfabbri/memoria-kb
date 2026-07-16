# Current Next Increment

Data: 2026-07-16

## Incremento corrente

T33 - Pacchetto finanziatori.

## Stato

**Aperto e prioritario.**

T32 e' chiuso: la golden run e' pronta per demo interna, usa il ledger standard
`mvp_consolidated_review_ledger.json`, non dipende piu' dal sidecar T30 come
ledger attivo, e il rischio del pacchetto repository distribuibile e' trattato
da esclusioni `export-ignore` testate.

Avanzamento T33 del 2026-07-16: creato l'entrypoint documentale del pacchetto
finanziatori in
`memoria-bootstrap/docs/funding-demo-t33-package-entrypoint.md`. L'artefatto
definisce golden run, reading order, walkthrough 7-10 minuti, comandi fallback,
guardrail editoriali e checklist T33, senza copiare dati reali e senza scrivere
nel data root esterno. La verifica read-only `memoria mvp demo --data-root
"P:\Comune\Me.Mo.Ri.a"` conferma `ready_for_internal_demo` e safety flag
preview-only.

Avanzamento T33 del 2026-07-16: creato il diagramma documentale
`memoria-bootstrap/docs/funding-demo-t33-evidence-flow-diagram.md`, collegato
all'entrypoint T33. Il diagramma mostra il percorso
`fonti -> documenti -> evidenze -> riconciliazione -> review -> verified facts
preview -> ProfilePatch preview -> feedback outcome -> pacchetto finanziatori`
usando solo ID e riferimenti ad artefatti, senza copiare dati reali e senza
scrivere nel data root esterno.

Avanzamento operativo T33 del 2026-07-16: autorizzata la scrittura nel data root
esterno per il solo pacchetto finanziatori. Rigenerati nella run canonica
`mvp_funding_dossier.json`, `mvp_funding_dossier.md`,
`mvp_go_no_go_checklist.json`, `mvp_go_no_go_checklist.md` e
`funding_package_index.md`. Il builder del pacchetto e' ora descriptor-aware:
quando riceve `memoria_mvp_demo.active.json` usa il perimetro T33 reale
1 profilo primario, 4 documenti e 3 famiglie fonte, e non i vecchi criteri del
pilota a 3-5 schede. Esito checklist: `go_with_review_blockers`, quindi
finanziabile come demo revisionabile ma non pubblicabile.

Avanzamento T33 del 2026-07-16: creata la scheda caso demo
`memoria-bootstrap/docs/funding-demo-t33-demo-case-card.md` e collegata
all'entrypoint T33. La scheda rende leggibile il caso Andreoli/Balboni con
provenance, 3 famiglie fonte, 4/4 documenti coperti, stati di riconciliazione,
decisione storica, verified facts preview, ProfilePatch preview e feedback
outcome T31, senza scrivere nel data root esterno e senza presentare alcun
output come pubblicabile.

Descrittore:

```text
P:\Comune\Me.Mo.Ri.a\database\memoria_mvp_demo.active.json
```

Run canonica:

```text
prova-preview-profili-5-reviewed-01-pipeline
```

Chiusura T32 del 2026-07-16:

- `memoria mvp demo` conferma `ready_for_internal_demo`, artefatti T30/T31
  presenti e safety flag preview-only;
- il walkthrough asciutto e' documentato in
  `memoria-bootstrap/docs/funding-demo-t32-walkthrough-dry-run.md`;
- il trattamento sidecar e' chiuso in
  `memoria-bootstrap/docs/funding-demo-t32-sidecar-treatment.md`;
- il rischio distribuibile e' chiuso con `.gitattributes`, che esclude dagli
  archivi `memoria-engine/ricerche/person_profiles/**`,
  `memoria-engine/ricerche/caduti_purocielo.csv` e
  `memoria-engine/ricerche/mvp/**`;
- `tests.test_packaging` verifica che queste esclusioni restino presenti;
- nessun profilo canonico e' stato modificato, nessuna patch e' stata
  applicata, nessun verified fact canonico e' stato creato.

## Motivazione

T33 deve trasformare la golden run pronta per demo interna in un pacchetto breve
e presentabile a finanziatori, senza presentare output preview come schede
pubblicabili e senza allargare il perimetro storico.

```text
fonti eterogenee
  -> evidenze tracciabili
  -> riconciliazione multi-fonte
  -> decisione dello storico
  -> verified fact e patch preview
  -> feedback per nuova ricerca
  -> esito tracciato
```

I gap metodologici obbligatori sono coperti in modalita' preview-only:

- **merge multi-fonte**, con provenance e divergenze visibili;
- **feedback loop chiuso**, non limitato alla generazione di query candidate;
- **rientro dell'esito nella memoria di ricerca**, senza promozione automatica
  a fatto storico.

## Scope T33

T33 deve:

- preparare un dossier finanziatori breve collegato alla golden run;
- preparare script del walkthrough e comandi di fallback;
- produrre un diagramma del percorso fonti-documenti-evidenze-review-feedback;
- preparare una scheda del caso demo con provenance leggibile e stato preview;
- dichiarare limiti, capacita' attuali, sviluppo finanziato e visione;
- mantenere esplicita la distinzione fra preview, decisione e pubblicazione.

## Fuori scope T33

- nessun OCR o scansione massiva;
- nessuna chiamata live a fonti non controllata;
- nessuna rigenerazione massiva di pipeline;
- nessuna patch applicata ai profili canonici;
- nessun driver pCloud;
- nessun Q2 salvo blocco diretto del pacchetto finanziatori;
- nessuna espansione oltre il perimetro demo.

## Criteri di uscita

- dossier finanziatori breve collegato alla golden run: **prodotto, da rifinire
  per uso esterno**;
- script del walkthrough e comandi di fallback disponibili: **completato**;
- diagramma del percorso fonti-documenti-evidenze-review-feedback:
  **completato**;
- scheda del caso demo con provenance leggibile: **completata per preview**;
- roadmap dell'uso dei fondi e risultati attesi;
- distinzione esplicita fra capacita' attuali, sviluppo finanziato e visione;
- checklist di readiness approvata per presentazione esterna: **generata come
  `go_with_review_blockers`, non ancora approvata per esterno**;
- nessuna affermazione storica non supportata o output preview presentato come
  pubblicabile.

## Priorita' degli incrementi successivi

Da T33:

1. T26-T28 cloud solo se richiesti o se diventano necessari per la fase
   successiva.
2. Q2 solo come micro-refactor behavior-preserving con rischio concreto.

T26-T28 cloud restano in hold fino alla chiusura del pacchetto finanziatori.

## Documenti autorevoli

- `roadmap/00-roadmap-master.md`;
- `roadmap/01-mvp-roadmap.md`;
- `roadmap/02-technical-roadmap.md`;
- `funding-demo-golden-path.md`;
- `decision-log.md`.

## Evidenza di chiusura

Avanzamento T30:

- autorizzato ed eseguito incremento operativo T30 con scrittura limitata nel
  data root esterno ai soli artefatti preview della golden run;
- aggiunto a `memoria mvp demo-build` il supporto a
  `--output-aligned-ledger`, che crea un sidecar preview del ledger consolidato
  riallineato al perimetro T30 senza modificare il ledger originale, profili
  canonici, raw documenti, OCR o fonti originali;
- nota metodologica vincolante: `--output-aligned-ledger` e' una variazione
  temporanea T30 per sbloccare la demo interna, non il flusso ordinario di
  arricchimento schede; T32 non puo' avanzare finche' lo stesso risultato non
  viene rigenerato dal percorso standard
  `documenti/CSV/DOCX -> person linking -> candidate_evidence_claims ->
  evidence store -> consolidated ledger`;
- creato il sidecar autorizzato:
  `P:\Comune\Me.Mo.Ri.a\risultati\runs\prova-preview-profili-5-reviewed-01-pipeline\mvp_consolidated_review_ledger.t30-preview.json`;
- il sidecar aggiunge 2 claim candidati `unreviewed` e marcati
  `t30_preview_candidate`: uno da `legacy_csv:a4ac96061a2381b5` tramite
  `t30_preview_alignment_from_candidate_document_person_link`, uno da
  `local_docx:4c2ad1d2ab937913` tramite
  `t30_preview_alignment_from_existing_claim`;
- creati/aggiornati gli artefatti autorizzati:
  `P:\Comune\Me.Mo.Ri.a\database\memoria_mvp_demo.active.json` e
  `P:\Comune\Me.Mo.Ri.a\risultati\runs\prova-preview-profili-5-reviewed-01-pipeline\mvp_demo_reconciliation_table.md`;
- `memoria mvp demo-build` sulla run canonica con sidecar T30 conferma
  `Readiness: ready_for_internal_demo`, `Readiness errors: 0`,
  `Readiness warnings: 0`, famiglie coperte
  `legacy_csv`, `local_docx`, `partigiani_italia` e documenti coperti `4/4`;
- `memoria mvp demo` legge ora il descrittore attivo con
  `Status: ready_for_internal_demo`, artefatti presenti e safety flag:
  `preview_only=true`, `applies_profile_patch=false`,
  `creates_canonical_verified_facts=false`,
  `modifies_canonical_profiles=false`;
- la tabella di riconciliazione preview contiene 22 righe, mantiene le
  divergenze visibili e mostra contributi da `legacy_csv`, `local_docx` e
  `partigiani_italia`;
- test mirati passanti:
  `.\.venv\Scripts\python.exe -m unittest tests.test_mvp_demo_descriptor tests.test_memoria_diagnostic_cli`
  (`38 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- aggiunto alla readiness T30 di `memoria mvp demo-build` il campo
  `alignment_plan`, derivato dalla diagnostica per-documento e limitato a passi
  preview-only verso il ledger consolidato;
- il piano distingue ora i prossimi riallineamenti operativi senza applicarli:
  `produce_candidate_claims`, `attach_existing_claims_to_demo_profile`,
  `attach_document_to_demo_profile` e fallback `add_reconciliation_row`;
- `memoria mvp demo-build` stampa righe `ALIGNMENT_STEP`, e la tabella
  Markdown di riconciliazione preview include la sezione
  `Piano riallineamento preview`;
- prova read-only reale sulla run candidata conferma due passi T30:
  `ALIGNMENT_STEP 1` produce claim candidati per
  `legacy_csv:a4ac96061a2381b5`; `ALIGNMENT_STEP 2` riconduce al profilo demo i
  claim esistenti per `local_docx:4c2ad1d2ab937913`;
- test mirati passanti:
  `.\.venv\Scripts\python.exe -m unittest tests.test_mvp_demo_descriptor tests.test_memoria_diagnostic_cli`
  (`37 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- verificato in sola lettura che restano assenti
  `P:\Comune\Me.Mo.Ri.a\database\memoria_mvp_demo.active.json` e
  `P:\Comune\Me.Mo.Ri.a\risultati\runs\prova-preview-profili-5-reviewed-01-pipeline\mvp_demo_reconciliation_table.md`;
- aggiunta alla diagnostica T30 di `memoria mvp demo-build` la causa sintetica
  `blocking_reason` per ciascun documento e ciascuna famiglia fonte T29;
- `FAMILY_STATUS` e `DOCUMENT_STATUS` mostrano ora `blocked_by`, distinguendo
  blocchi operativi diversi senza dover aprire il JSON: claim candidati
  mancanti, claim esistenti fuori perimetro demo, documenti fuori perimetro o
  righe di riconciliazione mancanti;
- la tabella Markdown di riconciliazione preview include la colonna `Blocco`
  nelle sezioni `Famiglie T29` e `Documenti T29`;
- prova read-only reale sulla run candidata conferma il blocco T30 attuale:
  `legacy_csv` e' `blocked_by=candidate_claims_missing`,
  `local_docx` e' `blocked_by=claims_outside_demo_scope`,
  `partigiani_italia` e' `blocked_by=covered`;
- test mirati passanti:
  `.\.venv\Scripts\python.exe -m unittest tests.test_mvp_demo_descriptor tests.test_memoria_diagnostic_cli`
  (`37 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- verificato in sola lettura che restano assenti
  `P:\Comune\Me.Mo.Ri.a\database\memoria_mvp_demo.active.json` e
  `P:\Comune\Me.Mo.Ri.a\risultati\runs\prova-preview-profili-5-reviewed-01-pipeline\mvp_demo_reconciliation_table.md`;
- aggiunta al payload T30 di `memoria mvp demo-build` la diagnostica
  `source_family_diagnostics`, che riepiloga per ciascuna famiglia T29 lo stato
  di copertura, il numero di documenti selezionati, coperti e mancanti;
- `memoria mvp demo-build` stampa ora righe `FAMILY_STATUS` prima delle righe
  `DOCUMENT_STATUS`, rendendo immediato il blocco di merge multi-fonte senza
  dover leggere tutto il JSON;
- la tabella Markdown di riconciliazione preview include ora anche la sezione
  `Famiglie T29`; corretto il rendering Markdown delle celle numeriche per
  preservare il valore `0` invece di mostrarlo come cella vuota;
- prova read-only reale sulla run candidata conferma il quadro per famiglia:
  `legacy_csv` e `local_docx` sono `coverage=missing_reconciliation` con un
  documento selezionato e zero documenti coperti ciascuna; `partigiani_italia`
  e' `coverage=covered` con due documenti selezionati e due coperti;
- test mirati passanti:
  `.\.venv\Scripts\python.exe -m unittest tests.test_mvp_demo_descriptor tests.test_memoria_diagnostic_cli`
  (`37 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- verificato in sola lettura che restano assenti
  `P:\Comune\Me.Mo.Ri.a\database\memoria_mvp_demo.active.json` e
  `P:\Comune\Me.Mo.Ri.a\risultati\runs\prova-preview-profili-5-reviewed-01-pipeline\mvp_demo_reconciliation_table.md`;
- aggiunta al payload T30 di `memoria mvp demo-build` la diagnostica
  per-documento `document_diagnostics`, con famiglia fonte, stato di
  riconciliazione, presenza nel perimetro profili demo e stato dei claim
  candidati;
- `memoria mvp demo-build` stampa ora righe `DOCUMENT_STATUS` per ciascun
  documento T29, evitando di incrociare manualmente le liste di documenti
  coperti, mancanti, senza claim o con claim fuori perimetro;
- la tabella Markdown di riconciliazione preview include la sezione
  `Documenti T29` quando la readiness espone errori o warning;
- prova read-only reale sulla run candidata conferma il quadro operativo T30:
  `legacy_csv:a4ac96061a2381b5` ha
  `reconciliation=missing_reconciliation_row`, e'
  `present_in_selected_profiles` ma ha `claims=no_candidate_claims`;
  `local_docx:4c2ad1d2ab937913` ha
  `reconciliation=missing_reconciliation_row`, e'
  `present_in_selected_profiles` ma ha
  `claims=claims_outside_selected_profiles`; i due documenti
  `partigiani_italia` sono `covered` con claim nel perimetro selezionato;
- test mirati passanti:
  `.\.venv\Scripts\python.exe -m unittest tests.test_mvp_demo_descriptor tests.test_memoria_diagnostic_cli`
  (`37 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- verificato in sola lettura che restano assenti
  `P:\Comune\Me.Mo.Ri.a\database\memoria_mvp_demo.active.json` e
  `P:\Comune\Me.Mo.Ri.a\risultati\runs\prova-preview-profili-5-reviewed-01-pipeline\mvp_demo_reconciliation_table.md`;
- arricchita la readiness T30 di `memoria mvp demo-build` con
  `next_actions` diagnostiche calcolate dal blocco corrente, esposte nel
  payload del descrittore preview, nella tabella Markdown di riconciliazione e
  nell'output CLI;
- le azioni distinguono ora il prossimo riallineamento operativo: aggiungere
  claim dalle famiglie fonte mancanti, produrre claim per documenti selezionati
  senza claim, ricondurre al profilo demo claim gia' presenti fuori perimetro,
  oppure collegare documenti T29 assenti dal perimetro;
- prova read-only reale sulla run candidata conferma `Readiness:
  blocked_for_internal_demo` e suggerisce esplicitamente: aggiungere claim da
  `legacy_csv` e `local_docx`, produrre claim per
  `legacy_csv:a4ac96061a2381b5`, ricondurre al profilo demo i claim gia'
  presenti fuori perimetro per `local_docx:4c2ad1d2ab937913`;
- test mirati passanti:
  `.\.venv\Scripts\python.exe -m unittest tests.test_mvp_demo_descriptor tests.test_memoria_diagnostic_cli`
  (`37 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- nessun output scritto nel data root esterno; `memoria mvp demo-build` e'
  stato eseguito senza `--output-descriptor` e senza
  `--output-reconciliation`;
- arricchita la diagnostica T30 di `memoria mvp demo-build` distinguendo i
  documenti selezionati mancanti dalla riconciliazione in:
  presenti nei profili demo selezionati, assenti dai profili demo selezionati,
  senza claim candidati nel ledger, oppure con claim solo fuori dai profili demo;
- la prova read-only reale sulla run candidata conferma il blocco operativo:
  `legacy_csv:a4ac96061a2381b5` e' presente nei profili demo selezionati ma
  non ha claim candidati nel ledger, mentre `local_docx:4c2ad1d2ab937913` e'
  presente nei profili demo selezionati ma i claim candidati esistenti sono
  fuori dal perimetro Andreoli/Balboni;
- la stessa prova reale resta correttamente bloccata con
  `Readiness: blocked_for_internal_demo`, copertura documenti `2/4`, famiglie
  coperte `partigiani_italia` e famiglie mancanti `legacy_csv`, `local_docx`;
- test mirati passanti:
  `.\.venv\Scripts\python.exe -m unittest tests.test_mvp_demo_descriptor tests.test_memoria_diagnostic_cli`
  (`37 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- verificato in sola lettura che restano assenti
  `P:\Comune\Me.Mo.Ri.a\database\memoria_mvp_demo.active.json` e
  `P:\Comune\Me.Mo.Ri.a\risultati\runs\prova-preview-profili-5-reviewed-01-pipeline\mvp_demo_reconciliation_table.md`;
- reso simmetrico l'output di `memoria mvp demo-build`: oltre ai
  `MISSING_DOCUMENT`, ora stampa anche i `COVERED_DOCUMENT`;
- la prova read-only reale mostra ora esplicitamente che i due documenti coperti
  sono `partigiani_italia:b45553cd6b1673d8` e
  `partigiani_italia:b6b3c9e526723a27`, mentre restano mancanti
  `legacy_csv:a4ac96061a2381b5` e `local_docx:4c2ad1d2ab937913`;
- test CLI passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_memoria_diagnostic_cli`
  (`32 tests`, `OK`);
- test builder passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_mvp_demo_descriptor`
  (`4 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- corretto `memoria mvp demo-build`: una run con readiness
  `blocked_for_internal_demo` ora termina con exit code `1`;
- il comando valuta la readiness prima di scrivere e non crea
  `--output-descriptor` o `--output-reconciliation` quando il gate e' bloccato;
- rinominata nell'output CLI la voce ambigua `Famiglie fonte` in
  `Famiglie coperte nel descriptor`, per distinguere copertura reale e
  perimetro selezionato;
- aggiunto test CLI che passa output espliciti a una run bloccata e verifica
  che nessun file venga scritto;
- test CLI passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_memoria_diagnostic_cli`
  (`32 tests`, `OK`);
- test builder passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_mvp_demo_descriptor`
  (`4 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- prova read-only reale ripetuta: `memoria mvp demo-build` sulla run candidata
  ora esce con codice `1`, stampa `Readiness: blocked_for_internal_demo` e
  conferma `nessun output e' stato scritto`;
- verificato in sola lettura che restano assenti
  `P:\Comune\Me.Mo.Ri.a\database\memoria_mvp_demo.active.json` e
  `P:\Comune\Me.Mo.Ri.a\risultati\runs\prova-preview-profili-5-reviewed-01-pipeline\mvp_demo_reconciliation_table.md`;
- arricchito il gate `readiness` con famiglie fonte selezionate, famiglie
  coperte, famiglie mancanti, documenti sorgente coperti e documenti sorgente
  mancanti;
- `memoria mvp demo-build` stampa ora gli ID mancanti utili a riallineare la
  run canonica senza aprire il JSON;
- test builder passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_mvp_demo_descriptor`
  (`4 tests`, `OK`);
- test CLI passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_memoria_diagnostic_cli`
  (`31 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- prova read-only reale ripetuta:
  `.\.venv\Scripts\memoria.exe mvp demo-build --data-root "P:\Comune\Me.Mo.Ri.a" --run-id "prova-preview-profili-5-reviewed-01-pipeline"`;
- risultato della prova reale dettagliato: famiglie selezionate
  `legacy_csv`, `local_docx`, `partigiani_italia`; famiglie coperte
  `partigiani_italia`; famiglie mancanti `legacy_csv`, `local_docx`;
- documenti T29 mancanti nella riconciliazione della run candidata:
  `legacy_csv:a4ac96061a2381b5` e `local_docx:4c2ad1d2ab937913`;
- documenti T29 coperti nella riconciliazione della run candidata: `2/4`;
- verificato in sola lettura che il dry-run non ha creato
  `P:\Comune\Me.Mo.Ri.a\database\memoria_mvp_demo.active.json` ne'
  `P:\Comune\Me.Mo.Ri.a\risultati\runs\prova-preview-profili-5-reviewed-01-pipeline\mvp_demo_reconciliation_table.md`;
- aggiunto gate `readiness` al builder `mvp_demo_descriptor`;
- il descriptor ora distingue una run `ready_for_internal_demo` da una
  `blocked_for_internal_demo` in base ai criteri minimi T30 osservabili nella
  riconciliazione;
- errori bloccanti rilevati: nessuna riga di riconciliazione nel perimetro,
  meno di due famiglie fonte riconciliate, profilo principale senza righe;
- warning rilevati: documenti selezionati T29 senza righe di riconciliazione;
- `memoria mvp demo-build` stampa `Readiness`, errori e warning nel dry-run;
- test builder passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_mvp_demo_descriptor`
  (`4 tests`, `OK`);
- test CLI passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_memoria_diagnostic_cli`
  (`31 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- prova read-only reale ripetuta:
  `.\.venv\Scripts\memoria.exe mvp demo-build --data-root "P:\Comune\Me.Mo.Ri.a" --run-id "prova-preview-profili-5-reviewed-01-pipeline"`;
- risultato della prova reale aggiornato: `Readiness:
  blocked_for_internal_demo`, errore
  `multi_source_reconciliation_requires_at_least_two_source_families`, warning
  `selected_documents_without_reconciliation_rows`;
- verificato in sola lettura che il dry-run non ha creato
  `P:\Comune\Me.Mo.Ri.a\database\memoria_mvp_demo.active.json` ne'
  `P:\Comune\Me.Mo.Ri.a\risultati\runs\prova-preview-profili-5-reviewed-01-pipeline\mvp_demo_reconciliation_table.md`;
- aggiunto comando CLI preview-only `memoria mvp demo-build`;
- `demo-build` legge una run esistente e prepara il payload del descrittore
  demo e la sintesi di riconciliazione usando il builder
  `mvp_demo_descriptor`, ma non scrive nulla se non sono passati
  `--output-descriptor` e/o `--output-reconciliation`;
- `memoria mvp status` include ora il dry-run `memoria mvp demo-build` nel
  walkthrough operativo;
- test mirato CLI passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_memoria_diagnostic_cli`
  (`31 tests`, `OK`);
- test builder passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_mvp_demo_descriptor`
  (`3 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- prova help installabile passante:
  `.\.venv\Scripts\memoria.exe mvp demo-build --help`;
- prova read-only sul data root esterno eseguita senza output path:
  `.\.venv\Scripts\memoria.exe mvp demo-build --data-root "P:\Comune\Me.Mo.Ri.a" --run-id "prova-preview-profili-5-reviewed-01-pipeline"`;
- risultato della prova reale: `20` righe di riconciliazione, `10` decisioni
  sostanziali, `8` verified facts preview e `2` ProfilePatch preview letti
  dalla run candidata;
- la stessa prova evidenzia il blocco T30 ancora aperto: con il perimetro
  documentale T29, la run candidata espone solo `partigiani_italia` come
  famiglia fonte nella riconciliazione, quindi il merge multi-fonte
  `legacy_csv`/`local_docx`/`partigiani_italia` non e' ancora soddisfatto;
- verificato in sola lettura che
  `P:\Comune\Me.Mo.Ri.a\database\memoria_mvp_demo.active.json` e
  `P:\Comune\Me.Mo.Ri.a\risultati\runs\prova-preview-profili-5-reviewed-01-pipeline\mvp_demo_reconciliation_table.md`
  non sono stati creati da questo dry-run;
- aggiunto builder preview-only
  `caduti_fonti_report.document_analysis.mvp_demo_descriptor`;
- il builder prepara `MemoriaMvpDemoDescriptor` e
  `mvp_demo_reconciliation_table.md` da una sola run canonica gia' esistente,
  leggendo il ledger consolidato e gli artefatti `historian_review`;
- il builder seleziona il perimetro T29/T30:
  `person:purocielo:andreoli-dino`, contrasto
  `person:purocielo:balboni-william`, e i quattro documenti candidati;
- la tabella di riconciliazione espone `claim`, `fonte`, `metodo`,
  `review_status` e compatibilita' (`corroborated`, `divergent`,
  `single_source`);
- il payload mantiene safety flags espliciti:
  `preview_only=true`, nessuna decisione applicata, nessun verified fact
  canonico creato, nessuna ProfilePatch applicata e nessuna modifica ai
  profili canonici;
- se non vengono passati output path, il builder restituisce solo il payload e
  non crea `memoria_mvp_demo.active.json` ne' la tabella markdown;
- test mirato passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_mvp_demo_descriptor`
  (`3 tests`, `OK`);
- regressione diagnostica passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_memoria_diagnostic_cli`
  (`30 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- nessuna scrittura nel data root esterno eseguita in questo incremento;
- `memoria mvp demo` disponibile nella CLI Python installabile;
- il comando legge in sola lettura il descrittore
  `<data-root>/database/memoria_mvp_demo.active.json`;
- se il descrittore manca, il comando segnala il path atteso senza crearlo;
- se il descrittore esiste, mostra `contract_version`, `status`,
  `preview_only`, `publication_status`, `run_id`, `run_dir`, profili,
  documenti, famiglie fonte, artefatti e safety flags;
- `memoria mvp status` include `memoria mvp demo` nel walkthrough read-only;
- test mirati passanti:
  `.\.venv\Scripts\python.exe -m unittest tests.test_memoria_diagnostic_cli`
  (`30 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- prova read-only sul data root esterno eseguita:
  `.\.venv\Scripts\memoria.exe mvp demo`;
- risultato della prova reale: descrittore non ancora presente in
  `P:\Comune\Me.Mo.Ri.a\database\memoria_mvp_demo.active.json`, nessun file
  creato o modificato;
- T30 resta aperto: mancano ancora creazione/riallineamento della run canonica,
  descrittore reale nel data root e tabella di riconciliazione multi-fonte.

Evidenza T29:

- `funding-demo-t29-contract.md` presente;
- caso principale selezionato: `person:purocielo:andreoli-dino`;
- caso di contrasto leggero selezionato: `person:purocielo:balboni-william`;
- documenti candidati identificati per ID senza copiarli nei repository:
  `legacy_csv:a4ac96061a2381b5`, `local_docx:4c2ad1d2ab937913`,
  `partigiani_italia:b45553cd6b1673d8`,
  `partigiani_italia:b6b3c9e526723a27`;
- famiglie fonte selezionate: `legacy_csv`, `local_docx`,
  `partigiani_italia`;
- criterio di riconciliazione multi-fonte definito;
- contratto del descrittore
  `<data-root>/database/memoria_mvp_demo.active.json` definito;
- artifact map e walkthrough 7-10 minuti definiti;
- feedback trigger candidato identificato per T31;
- gap tecnici puntuali T30-T32 elencati;
- validazioni read-only T29 eseguite:
  `memoria mvp status`, `memoria review status`,
  `memoria review decisions`, `memoria review work`,
  `memoria consolidate status`;
- nessuna pipeline, OCR, ricerca live o scrittura nel data root eseguita.

Evidenze baseline gia' disponibili:

- `memoria data-root` funziona;
- `memoria inventory` funziona senza opzioni;
- `memoria doctor` conferma data root e repository sibling;
- `memoria inventory --section risultati` produce un riepilogo leggero;
- `memoria inventory --section documenti_processati` produce un riepilogo
  leggero;
- `memoria inventory --section all` produce riepilogo delle sezioni supportate;
- `memoria inventory --output markdown` produce markdown leggibile;
- `pytest` passa nelle validazioni precedenti;
- il data root esterno resta esterno:

```text
P:\Comune\Me.Mo.Ri.a
```

- nessun dato reale e' stato copiato nei repository Git.

Evidenza T4:

- `daily-agent-procedure.md` presente;
- `agent-session-prompt.md` presente;
- `current-next-increment.md` trasformato in documento operativo;
- `02-technical-roadmap.md` con milestone ID, dipendenze, criteri di ingresso e
  criteri di uscita.

Evidenza T5:

- `mvp-demo-scoping-read-only.md` presente;
- perimetro demo MVP read-only descritto;
- criteri di selezione di un set piccolo e controllato definiti;
- decisione metodologica registrata nel decision log.

Evidenza T6:

- `memoria-sources/registry/camalanca_fonti.yaml` presente;
- `memoria-sources/source_profiles/` presente;
- `memoria-sources/source_strategies/` presente;
- `memoria-sources/source_result_logic/` presente;
- `memoria-sources/source_detail_logic/` presente;
- `memoria-engine` risolve il catalogo fonti da `../memoria-sources` come
  posizione primaria;
- fallback legacy su `memoria-engine/ricerche` mantenuto;
- piano residui post-migrazione documentato.

Evidenza T7:

- wrapper PowerShell principali puntano a
  `..\memoria-sources\registry\camalanca_fonti.yaml`;
- `scripts/memoria.ps1` cerca `memoria-sources` prima dei fallback legacy;
- registry e strategie in `memoria-sources` usano path relativi al nuovo
  catalogo;
- `memoria-engine/ricerche/SOURCE_CATALOG_LEGACY.md` marca i duplicati
  `source_*` come fallback transitorio;
- documentazione operativa aggiornata sui path source;
- test mirati e validazioni registry passano.

Evidenza T8:

- `memoria-engine/ricerche/source_profiles` rimosso;
- `memoria-engine/ricerche/source_strategies` rimosso;
- `memoria-engine/ricerche/source_result_logic` rimosso;
- `memoria-engine/ricerche/source_detail_logic` rimosso;
- test e loader aggiornati per usare `memoria-sources`;
- `SOURCE_CATALOG_LEGACY.md` aggiornato come marker di rimozione;
- scansione `ricerche/source_*` senza risultati;
- suite estesa T8 passante.

Evidenza T9:

- `knowledge-residuals-classification.md` presente;
- `places/` classificato come knowledge di dominio versionabile;
- `military_glossaries/` classificato come glossario di dominio versionabile;
- destinazioni `memoria-knowledge/places/` e
  `memoria-knowledge/glossary/military/` confermate;
- loader, wrapper e test da aggiornare identificati;
- decisione di ownership registrata nel decision log.

Evidenza T10:

- `memoria-knowledge/places/places.index.jsonld` presente;
- `memoria-knowledge/places/ca-di-malanca.jsonld` presente;
- `memoria-knowledge/places/purocielo.jsonld` presente;
- `memoria-knowledge/glossary/military/de.basic.jsonld` presente;
- `memoria-engine` risolve i default knowledge per luoghi e glossari militari
  da `../memoria-knowledge`;
- wrapper diretti aggiornati sui default knowledge;
- fallback legacy mantenuto solo fino alla rimozione T11;
- test mirati T10 passanti.

Evidenza T11:

- `memoria-engine/ricerche/places` rimosso;
- `memoria-engine/ricerche/military_glossaries` rimosso;
- `memoria-engine/ricerche` non contiene piu' i residui knowledge migrati;
- riferimenti runtime legacy a `ricerche/places` e
  `ricerche/military_glossaries` assenti;
- documentazione operativa aggiornata: i cataloghi vivono in
  `memoria-knowledge`;
- test mirati T11 passanti.

Evidenza T12:

- `person-profile-seed-audit.md` presente;
- `person_profiles/` classificato come profili reali/preview, non fixture
  sintetica e non knowledge generica;
- `caduti_purocielo.csv` classificato come seed legacy reale, dismesso per
  nuovi profili operativi;
- `mvp/` classificato come perimetro MVP preview-only: metodo in bootstrap,
  artefatti operativi nel data root esterno;
- riferimenti runtime e documentali da aggiornare identificati;
- decisione di ownership registrata nel decision log;
- nessuna migrazione fisica dei file eseguita in T12.

Evidenza T13:

- `profile-seed-default-hardening.md` presente;
- CLI Python principali richiedono `--csv` o `--profiles-index` espliciti;
- `person_profiles.py` richiede `--output-dir` esplicito;
- wrapper PowerShell principali richiedono `-ProfilesIndex` esplicito;
- `run_caduti_fonti_report.ps1` richiede `-Csv` esplicito;
- `scripts/memoria.ps1` non ricade piu' su
  `memoria-engine\ricerche\person_profiles`;
- scansioni mirate senza default runtime legacy residui;
- test mirati T13 passanti: `46 tests`, `OK`.

Evidenza T13b:

- `memoria profiles status` disponibile nella CLI Python diagnostica;
- il comando risolve l'indice profili ordinario da
  `<data-root>\ricerche\person_profiles\purocielo.index.jsonld`;
- nessun fallback verso `memoria-engine\ricerche\person_profiles`;
- output con path risolto, conteggi profili, file mancanti e distribuzione di
  `profile_status`, `review_status`, `publication_status`;
- `profile-status-cli.md` presente;
- `cli-discovery-report.md` aggiornato;
- verifica read-only sul data root esterno passante:
  `57` profili indicizzati, `57` caricati, `0` file mancanti;
- suite mirata CLI/profili passante: `64 tests`, `OK`;
- suite completa `pytest` passante: `649 passed`.

Evidenza T14:

- `llm-prompts-classification.md` presente;
- `llm_prompts/` classificato come contratti e regole operative LLM
  preview-only;
- ownership primaria proposta: `memoria-rules`;
- destinazione proposta:
  `memoria-rules/llm_prompts/chunk_classification/`;
- riferimenti runtime, test, wrapper e documentazione da aggiornare identificati;
- decisione metodologica registrata nel decision log;
- nessuna migrazione fisica eseguita in T14;
- nessun dato reale copiato nei repository;
- nessun OCR, extraction, JSON-LD o pipeline lanciato.

Evidenza T15:

- `memoria-rules/llm_prompts/chunk_classification/README.md` presente;
- `memoria-rules/llm_prompts/chunk_classification/chunk_classification.gemma3-4b.prompt.md`
  presente;
- `memoria-rules/llm_prompts/chunk_classification/chunk_classification.schema.json`
  presente;
- `memoria-engine` espone un resolver per contratti LLM chunk classification che
  preferisce `../memoria-rules`;
- fallback legacy verso `memoria-engine\ricerche\llm_prompts` mantenuto solo per
  la transizione e rimosso in T16;
- `tests.test_llm_chunk_classifier` aggiornato sul resolver e passante:
  `15 tests`, `OK`;
- nessun dato reale copiato nei repository;
- nessun OCR, extraction, JSON-LD o pipeline lanciato.

Evidenza T16:

- `memoria-engine/ricerche/llm_prompts` rimosso;
- `llm_chunk_classifier.py` risolve i contratti LLM solo da
  `../memoria-rules/llm_prompts/chunk_classification/`;
- `tests.test_llm_chunk_classifier` verifica che lo schema non provenga da
  `ricerche`;
- riferimenti runtime/documentali al path legacy assenti o esplicitamente
  storici;
- test mirati LLM chunk classifier passanti: `15 tests`, `OK`;
- nessun dato reale copiato nei repository;
- nessun OCR, extraction, JSON-LD o pipeline lanciato.

Evidenza T17:

- `profile-editorial-status-contract.md` presente;
- collocazione canonica dei campi decisa: `metadata.profile_status`,
  `metadata.review_status`, `metadata.publication_status`;
- distinzione tra stato scheda/profilo e `search_hints[].review_status`
  documentata;
- valori iniziali per profili seed/preview non revisionati definiti;
- T18 preparato come dry-run read-only prima di qualunque scrittura sui profili
  reali;
- nessun profilo reale modificato;
- nessun OCR, extraction, JSON-LD o pipeline lanciato.

Evidenza T18:

- `profile-editorial-status-dry-run.md` presente;
- dry-run read-only sui profili canonici completato tramite
  `memoria profiles status`;
- indice profili canonico risolto da
  `<data-root>\ricerche\person_profiles\purocielo.index.jsonld`;
- profili indicizzati: `57`;
- profili caricati: `57`;
- file profilo mancanti: `0`;
- profili privi di `metadata.profile_status`: `57`;
- profili privi di `metadata.review_status`: `57`;
- profili privi di `metadata.publication_status`: `57`;
- profili privi di tutti e tre i campi editoriali canonici: `57`;
- oggetto `metadata` presente in tutti i profili caricati;
- campi `search_hints[].review_status` osservati: `279`, documentati come
  fuori dal piano di patch;
- piano di patch limitato a `metadata` documentato;
- strategia di backup e rollback per eventuale incremento applicativo
  successivo documentata;
- test CLI da aggiornare o aggiungere elencati;
- nessun profilo reale modificato;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Evidenza Q1:

- `memoria-engine-modularity-audit.md` presente;
- moduli Python piu' grandi elencati per righe;
- peso per area documentato:
  `document_analysis` `25455` righe, root package `12008` righe,
  `connectors` `7414` righe;
- responsabilita' principali dei moduli critici documentate;
- rischi principali dei moduli critici documentati;
- candidati micro-refactor ordinati per rischio e valore;
- test minimi identificati per ogni candidato;
- primo Q2 consigliato: estrarre parser Markdown table/card da
  `document_analysis/mvp_review_focus_table.py`;
- nessun codice spostato;
- nessun comportamento esterno modificato;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Evidenza Q2 `mvp_review_focus_table`:

- helper interno `mvp_review_markdown.py` creato;
- parsing Markdown table/card isolato fuori da
  `document_analysis/mvp_review_focus_table.py`;
- `mvp_review_focus_table.py` mantiene funzioni pubbliche e CLI invariate;
- output Markdown e conversione decisioni preservati dai test mirati;
- test baseline pre-refactor passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_mvp_review_focus_table`;
- test post-refactor passanti:
  `.\.venv\Scripts\python.exe -m unittest tests.test_mvp_review_focus_table`
  (`11 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Evidenza Q2 `mvp_pilot_summary` rendering diagnostico:

- helper interno `mvp_pilot_summary_markdown.py` creato;
- rendering di scorecard pacchetto MVP, stato ingest documentale e diagnostica
  segnale MVP isolato fuori da
  `document_analysis/mvp_pilot_summary.py`;
- `mvp_pilot_summary.py` mantiene payload `MvpPilotSummary`, funzione pubblica
  `render_mvp_pilot_summary_markdown`, builder e CLI invariati;
- test mirato nuovo `tests.test_mvp_pilot_summary_rendering` aggiunto per
  proteggere i blocchi diagnostici renderizzati;
- test baseline pre-refactor passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_document_research_pipeline`
  (`11 tests`, `OK`);
- test post-refactor passanti:
  `.\.venv\Scripts\python.exe -m unittest tests.test_mvp_pilot_summary_rendering tests.test_document_research_pipeline`
  (`12 tests`, `OK`);
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Evidenza Q2 `local_processing_runner` manifest/log:

- helper interno `local_processing_manifest.py` creato;
- costruzione dei record step manifest, record skipped, rendering
  `run_summary.md` e calcolo durata isolati fuori da
  `document_analysis/local_processing_runner.py`;
- `local_processing_runner.py` mantiene API pubblica, sequenza step, nomi step,
  stati, path manifest/log e righe log osservabili invariati;
- test mirato nuovo `tests.test_local_processing_manifest` aggiunto per
  proteggere shape dei record manifest e linee summary osservabili;
- test baseline pre-refactor passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_local_document_processing_runner`
  (`16 tests`, `OK`);
- test post-refactor passanti:
  `.\.venv\Scripts\python.exe -m unittest tests.test_local_processing_manifest tests.test_local_document_processing_runner`
  (`19 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Evidenza Q2 `export_obsidian_vault` rendering MVP vault:

- helper interno `export_obsidian_vault_markdown.py` creato;
- rendering Markdown del vault MVP pilota isolato fuori da
  `caduti_fonti_report.export_obsidian_vault`;
- `export_obsidian_vault.py` mantiene CLI, API pubbliche, selezione profili,
  scrittura file, preservazione note editoriali e shape del vault invariati;
- test mirato nuovo `tests.test_export_obsidian_vault_markdown` aggiunto per
  proteggere shape Markdown osservabile del renderer MVP documenti;
- test baseline pre-refactor passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_export_obsidian_vault`
  (`8 tests`, `OK`);
- test post-refactor passanti:
  `.\.venv\Scripts\python.exe -m unittest tests.test_export_obsidian_vault_markdown tests.test_export_obsidian_vault`
  (`9 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- suite completa passante:
  `.\.venv\Scripts\python.exe -m pytest`
  (`654 passed`);
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Evidenza Q2 `bundesarchiv_invenio_executor` parser PrimeFaces/tree:

- helper interno `bundesarchiv_invenio_parsing.py` creato;
- dataclass `InvenioCandidate`, parsing JSF update, parsing nodi
  PrimeFaces/tree, fallback pannelli Treffer e deduplica semantica isolati fuori
  da `connectors/bundesarchiv_invenio_executor.py`;
- `bundesarchiv_invenio_executor.py` mantiene API pubblica, wrapper
  `_extract_tree_node_candidates`, wrapper `_extract_panel_hit_candidates`,
  raccolta response da page/debug, scrittura diagnostica, selettori, timing e
  richieste Ajax invariati;
- test mirato esteso `tests.test_bundesarchiv_invenio_executor` per proteggere
  il helper di parsing senza Playwright;
- test baseline pre-refactor passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_bundesarchiv_invenio_executor`
  (`2 tests`, `OK`);
- test post-refactor passanti:
  `.\.venv\Scripts\python.exe -m unittest tests.test_bundesarchiv_invenio_executor`
  (`3 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- suite completa passante:
  `.\.venv\Scripts\python.exe -m pytest`
  (`655 passed`);
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Evidenza T19:

- `cli-operativa-cross-platform-plan.md` presente;
- CLI Python `memoria` confermata come superficie canonica futura
  cross-platform;
- `scripts/memoria.ps1` classificato come wrapper compat/Windows e superficie
  pratica per l'MVP finanziatori, non come destinazione architetturale
  definitiva;
- futuro wrapper Linux classificato come facciata sottile, senza duplicazione
  della logica operativa;
- confine dei wrapper sottili documentato;
- priorita' dei primi workflow da portare o esporre via bridge Python
  documentata: review read-only, review decisioni preview, consolidamento
  preview, sources online/offline, wrapper MVP workspace;
- criteri di compatibilita' definiti per output, selezione run, file sessione,
  data-root, flag operativi ed exit code;
- contratti di sessione da preservare documentati:
  `memoria_review_session.active.json`,
  `memoria_consolidate_session.active.json` e
  `memoria_sources_online_session.active.json`;
- nessuna migrazione funzionale richiesta per l'MVP finanziatori;
- `cli-discovery-report.md` aggiornato con rimando al piano T19;
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Evidenza Q2 `candidate_claims` diagnostica/skipped claim:

- helper interno `candidate_claim_diagnostics.py` creato;
- diagnostica funnel claim isolata fuori da
  `document_analysis/candidate_claims.py`;
- `candidate_claims.py` mantiene API pubbliche, CLI, costruzione claim,
  skipped claim, deduplica e rendering Markdown invariati;
- test mirato nuovo aggiunto in `tests.test_document_candidate_claims` per
  proteggere conteggi di contesto, motivi skip, azioni consigliate e stati
  editoriali della diagnostica;
- test baseline pre-refactor passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_document_candidate_claims`
  (`11 tests`, `OK`);
- test post-refactor passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_document_candidate_claims`
  (`12 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- suite completa passante:
  `.\.venv\Scripts\python.exe -m pytest`
  (`656 passed`);
- nessun cambio a `claim_id`, `review_status`, motivi di skip o payload
  diagnostici;
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Evidenza Q2 `candidate_claims` skipped claim helper:

- helper interno `candidate_claim_skips.py` creato;
- costruzione degli skipped claim e degli skipped structured document isolata
  fuori da `document_analysis/candidate_claims.py`;
- selezione dei candidate link per skipped entity e raccomandazione next action
  isolate nello stesso helper puro;
- `candidate_claims.py` mantiene API pubbliche, CLI, costruzione claim,
  deduplica, diagnostica funnel e rendering Markdown invariati;
- test mirato nuovo aggiunto in `tests.test_document_candidate_claims` per
  proteggere candidate profile ids, candidate link ids, identificativi skipped,
  azioni consigliate e stati editoriali;
- test baseline pre-refactor passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_document_candidate_claims`
  (`12 tests`, `OK`);
- test post-refactor passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_document_candidate_claims`
  (`13 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- suite completa passante:
  `.\.venv\Scripts\python.exe -m pytest`
  (`657 passed`);
- nessun cambio a motivi di skip, candidate profile ids, candidate link ids,
  `review_status`, `publication_status` o identificativi skipped;
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Evidenza Q2 `german_docs_downloader` rendering manifest:

- helper interno `german_docs_manifest.py` creato;
- rendering Markdown del manifest German Docs isolato fuori da
  `document_analysis/german_docs_downloader.py`;
- `german_docs_downloader.py` mantiene download, Playwright, registrazione
  sidecar, manifest JSON, CLI e path output invariati;
- test mirato nuovo aggiunto in `tests.test_german_docs_downloader` per
  proteggere rendering del contesto archivistico, nodi Delo, documenti ed
  excerpt lunghi;
- test baseline pre-refactor passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_german_docs_downloader`
  (`7 tests`, `OK`);
- test post-refactor passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_german_docs_downloader`
  (`8 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- suite completa passante:
  `.\.venv\Scripts\python.exe -m pytest`
  (`658 passed`);
- nessun cambio a download, Playwright, registrazione sidecar, manifest JSON,
  CLI, path output o output Markdown osservabile;
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Evidenza Q2 `mvp_consolidated_review_ledger` rendering Markdown:

- helper interno `mvp_consolidated_review_ledger_markdown.py` creato;
- rendering Markdown del Consolidated Review Ledger MVP isolato fuori da
  `document_analysis/mvp_consolidated_review_ledger.py`;
- `mvp_consolidated_review_ledger.py` mantiene consolidamento summary,
  lettura evidence store, scrittura JSON/Markdown, CLI e path output invariati;
- test mirato nuovo aggiunto in `tests.test_mvp_consolidated_review_ledger`
  per proteggere front matter, sezioni vuote e warning del renderer;
- test baseline pre-refactor passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_mvp_consolidated_review_ledger`
  (`8 tests`, `OK`);
- test post-refactor passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_mvp_consolidated_review_ledger`
  (`9 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- suite completa passante:
  `.\.venv\Scripts\python.exe -m pytest`
  (`659 passed`);
- nessun cambio a consolidamento ledger, evidence store, CLI, path output,
  JSON prodotto o output Markdown osservabile;
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Evidenza Q2 `mvp_review_dashboard` rendering Markdown:

- helper interno `mvp_review_dashboard_markdown.py` creato;
- rendering Markdown della Review Dashboard MVP isolato fuori da
  `document_analysis/mvp_review_dashboard.py`;
- `mvp_review_dashboard.py` mantiene build dashboard, caricamento input,
  sintesi verified facts/profile patch/sandbox, scrittura JSON/Markdown, CLI e
  path output invariati;
- test mirato nuovo aggiunto in `tests.test_mvp_review_dashboard` per
  proteggere front matter, file di lavoro, conteggi oggetti e warning del
  renderer;
- test baseline pre-refactor passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_mvp_review_dashboard`
  (`5 tests`, `OK`);
- test post-refactor passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_mvp_review_dashboard`
  (`6 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- suite completa passante:
  `.\.venv\Scripts\python.exe -m pytest`
  (`660 passed`);
- nessun cambio a build dashboard, sintesi preview, CLI, path output, JSON
  prodotto o output Markdown osservabile;
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Evidenza Q2 `mvp_historical_review_targets` rendering Markdown:

- helper interno `mvp_historical_review_targets_markdown.py` creato;
- rendering Markdown dei Target storici revisionabili MVP isolato fuori da
  `document_analysis/mvp_historical_review_targets.py`;
- `mvp_historical_review_targets.py` mantiene selezione target da review queue,
  lettura evidence store read-only, match decisioni storiche, scrittura
  JSON/Markdown, CLI e path output invariati;
- test mirato nuovo aggiunto in `tests.test_mvp_historical_review_targets` per
  proteggere front matter, run store, azioni ammesse, contesto, provenance e
  stato vuoto del renderer;
- test baseline pre-refactor passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_mvp_historical_review_targets`
  (`4 tests`, `OK`);
- test post-refactor passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_mvp_historical_review_targets`
  (`5 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- suite completa passante:
  `.\.venv\Scripts\python.exe -m pytest`
  (`661 passed`);
- nessun cambio a selezione target, evidence store read-only, decision matching,
  CLI, path output, JSON prodotto o output Markdown osservabile;
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Evidenza Q2 `mvp_review_session` rendering Markdown:

- helper interno `mvp_review_session_markdown.py` creato;
- rendering Markdown della Sessione revisione MVP isolato fuori da
  `document_analysis/mvp_review_session.py`;
- `mvp_review_session.py` mantiene build sessione, calcolo stati profilo,
  focus review, template decisioni, copertura ledger/evidence store, scrittura
  JSON/Markdown, CLI e path output invariati;
- test mirato nuovo aggiunto in `tests.test_mvp_review_session` per proteggere
  front matter, warning, stato vuoto e copertura ledger del renderer;
- test baseline pre-refactor passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_mvp_review_session`
  (`5 tests`, `OK`);
- test post-refactor passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_mvp_review_session`
  (`6 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- suite completa passante:
  `.\.venv\Scripts\python.exe -m pytest`
  (`662 passed`);
- nessun cambio a build sessione, focus review, template decisioni, copertura
  ledger/evidence store, CLI, path output, JSON prodotto o output Markdown
  osservabile;
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Evidenza Q2 `mvp_review_decisions` rendering Markdown:

- helper interno `mvp_review_decisions_markdown.py` creato;
- rendering Markdown del riepilogo Decisioni review queue MVP isolato fuori da
  `document_analysis/mvp_review_decisions.py`;
- `mvp_review_decisions.py` mantiene validazione decisioni, copertura file
  decisioni, sintesi sessione storici, conteggi, scrittura JSON/Markdown, CLI e
  path output invariati;
- test mirato nuovo aggiunto in `tests.test_mvp_review_decisions` per
  proteggere copertura file decisioni, candidate, contesto, vincoli e stati
  vuoti del renderer;
- test baseline pre-refactor passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_mvp_review_decisions`
  (`5 tests`, `OK`);
- test post-refactor passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_mvp_review_decisions`
  (`6 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- suite completa passante:
  `.\.venv\Scripts\python.exe -m pytest`
  (`663 passed`);
- nessun cambio a validazione decisioni, copertura file decisioni, sintesi
  sessione storici, CLI, path output, JSON prodotto o output Markdown
  osservabile;
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Evidenza Q2 `mvp_review_queue` rendering Markdown:

- helper interno `mvp_review_queue_markdown.py` creato;
- rendering Markdown della Review queue MVP isolato fuori da
  `document_analysis/mvp_review_queue.py`;
- `mvp_review_queue.py` mantiene build queue, template decisioni, scrittura
  JSON/Markdown, CLI e path output invariati;
- test mirato nuovo aggiunto in `tests.test_mvp_review_queue` per proteggere
  dettagli documento, contesto, motivi, vincoli e stati vuoti del renderer;
- test baseline pre-refactor passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_mvp_review_queue`
  (`2 tests`, `OK`);
- test post-refactor passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_mvp_review_queue`
  (`3 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- suite completa passante:
  `.\.venv\Scripts\python.exe -m pytest`
  (`664 passed`);
- nessun cambio a build queue, template decisioni, CLI, path output, JSON
  prodotto o output Markdown osservabile;
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Evidenza T20:

- `memoria review discover` disponibile nella CLI Python installabile;
- `memoria review status` disponibile nella CLI Python installabile;
- `memoria review work` disponibile nella CLI Python installabile;
- i tre comandi sono read-only: non creano sessioni, non applicano decisioni,
  non creano `verified_facts` e non modificano profili JSON-LD;
- `review discover` legge superficialmente `<data-root>\risultati\runs` e
  seleziona le run candidate usando artefatti review gia' esistenti;
- `review status` mostra la sessione attiva se
  `<data-root>\database\memoria_review_session.active.json` esiste, altrimenti
  ricade su discovery read-only;
- `review work` mostra la worklist della sessione attiva esistente e rimanda ai
  comandi PowerShell per le decisioni preview;
- test mirati CLI passanti:
  `.\.venv\Scripts\python.exe -m unittest tests.test_memoria_diagnostic_cli`
  (`21 tests`, `OK`);
- help CLI verificato:
  `.\.venv\Scripts\memoria.exe review --help`;
- help comando verificato:
  `.\.venv\Scripts\memoria.exe review discover --help`;
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- suite completa passante:
  `.\.venv\Scripts\python.exe -m pytest`
  (`667 passed`);
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Evidenza T21:

- `memoria consolidate discover` disponibile nella CLI Python installabile;
- `memoria consolidate status` disponibile nella CLI Python installabile;
- i due comandi sono read-only: non creano sessioni consolidate, non rigenerano
  ledger, non scrivono nello store, non creano `verified_facts` e non modificano
  profili JSON-LD;
- `consolidate discover` legge superficialmente `<data-root>\risultati\runs` e
  seleziona le run consolidabili usando artefatti preview gia' esistenti;
- `consolidate status` mostra la sessione attiva se
  `<data-root>\database\memoria_consolidate_session.active.json` esiste,
  altrimenti ricade su discovery read-only;
- test mirati CLI passanti:
  `.\.venv\Scripts\python.exe -m unittest tests.test_memoria_diagnostic_cli`
  (`24 tests`, `OK`);
- help CLI verificato:
  `.\.venv\Scripts\memoria.exe consolidate --help`;
- help comando verificato:
  `.\.venv\Scripts\memoria.exe consolidate discover --help`;
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- suite completa passante:
  `.\.venv\Scripts\python.exe -m pytest`
  (`670 passed`);
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Evidenza T22:

- `memoria sources online discover` disponibile nella CLI Python installabile;
- `memoria sources online status` disponibile nella CLI Python installabile;
- `memoria sources offline discover` disponibile nella CLI Python installabile;
- `memoria sources offline status` disponibile nella CLI Python installabile;
- i quattro comandi sono read-only: non creano sessioni sources, cartelle
  intake, run, download, store, OCR, pipeline o modifiche ai profili JSON-LD;
- `sources online discover` legge superficialmente il registry fonti da
  `memoria-sources` con fallback compatibili, l'indice profili pilota dal data
  root e mostra fonti candidate;
- `sources online status` mostra la sessione attiva se
  `<data-root>\database\memoria_sources_online_session.active.json` esiste,
  altrimenti ricade su discovery read-only;
- `sources offline discover/status` mostrano un riepilogo superficiale di
  `documenti_da_processare` e `documenti_processati` senza scansione profonda;
- test mirati CLI passanti:
  `.\.venv\Scripts\python.exe -m unittest tests.test_memoria_diagnostic_cli`
  (`27 tests`, `OK`);
- help CLI verificato:
  `.\.venv\Scripts\memoria.exe sources --help`;
- help comandi verificati:
  `.\.venv\Scripts\memoria.exe sources online discover --help` e
  `.\.venv\Scripts\memoria.exe sources offline discover --help`;
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- suite completa passante:
  `.\.venv\Scripts\python.exe -m pytest`
  (`673 passed`);
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Evidenza T23:

- `scelta-architetturale-cloud-workspace.md` allineato alla roadmap tecnica;
- roadmap master aggiornata: il workspace operativo resta fuori dai repository
  Git, ma il path `P:\Comune\Me.Mo.Ri.a` e' ora backend locale compatibile, non
  vincolo architetturale unico;
- roadmap MVP aggiornata: il backend puo' essere locale o cloud purche' i dati
  reali restino fuori da Git;
- roadmap tecnica aggiornata con sequenza T23-T28:
  decisione cloud workspace pluggable, `WorkspaceStorage` locale, manifest
  provider-aware, pCloud read-only, pCloud write diagnostico e cache;
- decision log aggiornato con la scelta `WorkspaceStorage` pluggable;
- pCloud classificato come primo backend cloud candidato;
- la prima verifica pCloud prevista e' read-only via REST su cartelle esistenti,
  usando `listfolder` e salvando `folderid` dove utile;
- nessun driver cloud implementato;
- nessuna chiamata reale a pCloud eseguita;
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Evidenza T24:

- `memoria-engine/code/caduti_fonti_report/workspace_storage.py` presente;
- interfaccia Python `WorkspaceStorage` disponibile;
- `LocalWorkspaceStorage` implementa `exists`, `list_dir`, `read_bytes`,
  `write_bytes`, `mkdir` e `stat`;
- `memoria doctor` usa `LocalWorkspaceStorage` per verificare data root,
  cartelle richieste e repository sibling senza cambiare output osservabile;
- test unitari offline del driver local presenti in
  `memoria-engine/tests/test_workspace_storage.py`;
- test CLI mirati confermano `doctor` e i comandi diagnostici esistenti;
- test mirati passanti:
  `.\.venv\Scripts\python.exe -m unittest tests.test_workspace_storage tests.test_memoria_diagnostic_cli`
  (`31 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- suite completa passante:
  `.\.venv\Scripts\python.exe -m pytest`
  (`677 passed`);
- nessun driver pCloud implementato;
- nessuna chiamata cloud eseguita;
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Evidenza T25:

- `memoria-workspace/manifest.yml` supporta `workspace.provider`;
- il provider attivo e' `local`, con `workspace.root` sul backend locale
  compatibile `P:\Comune\Me.Mo.Ri.a`;
- il manifest descrive `providers.pcloud` come candidato read-only bloccato da
  supporto API, usando `credentials_ref` e senza salvare segreti;
- `resolve_data_root` legge il nuovo formato provider-aware;
- `--data-root` e `MEMORIA_DATA_ROOT` restano prioritari;
- il fallback legacy `data_root.windows_path` resta supportato;
- `memoria-workspace/EXTERNAL_DATA_ROOT.md` documenta il nuovo ordine di
  risoluzione;
- test mirati passanti:
  `.\.venv\Scripts\python.exe -m unittest tests.test_memoria_diagnostic_cli`
  (`30 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- verifica read-only del resolver passante:
  `.\.venv\Scripts\memoria.exe data-root`;
- suite completa passante:
  `.\.venv\Scripts\python.exe -m pytest`
  (`679 passed`);
- nessun driver pCloud implementato;
- nessuna chiamata cloud eseguita;
- nessun segreto salvato nel manifest;
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Evidenza T26a:

- `memoria review decisions` disponibile nella CLI Python installabile;
- il comando e' read-only: non crea sessioni, non registra decisioni, non
  modifica profili, `verified_facts`, store o artefatti canonici;
- se esiste una sessione review attiva, legge il summary decisioni collegato
  alla sessione;
- se non esiste una sessione attiva, usa la run candidata consigliata dalla
  discovery review read-only;
- output sintetico con run, path del summary decisioni, conteggio decisioni,
  decisioni storiche sostanziali e distribuzioni per `selected_action`,
  `decision_status` e `subject_kind`;
- help comando verificato:
  `.\.venv\Scripts\memoria.exe review decisions --help`;
- test mirati CLI passanti:
  `.\.venv\Scripts\python.exe -m unittest tests.test_memoria_diagnostic_cli`
  (`27 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- suite completa passante:
  `.\.venv\Scripts\python.exe -m pytest`
  (`684 passed`);
- nessun driver pCloud implementato;
- nessuna chiamata cloud eseguita;
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Evidenza T26b:

- `memoria mvp status` disponibile nella CLI Python installabile;
- il comando compone una vista read-only del walkthrough MVP demo locale;
- output sintetico con stato profili, review, decisioni review,
  consolidamento, registry fonti e intake offline;
- output con i comandi read-only gia' disponibili:
  `profiles status`, `review discover/status/work/decisions`,
  `consolidate status`, `sources online/offline status`;
- il comando non genera report, non crea run, non crea sessioni, non registra
  decisioni, non avvia OCR/pipeline e non modifica il data root;
- help comando verificato:
  `.\.venv\Scripts\memoria.exe mvp status --help`;
- test mirati CLI passanti:
  `.\.venv\Scripts\python.exe -m unittest tests.test_memoria_diagnostic_cli`
  (`28 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- suite completa passante:
  `.\.venv\Scripts\python.exe -m pytest`
  (`685 passed`);
- nessun driver pCloud implementato;
- nessuna chiamata cloud eseguita;
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Evidenza Q2 `memoria_cli` resolver data-root/manifest:

- helper interno `memoria-engine/code/caduti_fonti_report/workspace_resolver.py`
  creato;
- `DataRootResolution`, `DataRootResolutionError` e `resolve_data_root` isolati
  fuori da `memoria_cli.py`;
- `memoria_cli.py` mantiene re-export/import compatibile di `resolve_data_root`
  per i test e gli usi esistenti;
- risoluzione `--data-root`, `MEMORIA_DATA_ROOT`, manifest provider-aware e
  fallback legacy preservata;
- nessun cambio a comandi, output CLI, exit code, schema o workflow;
- test mirati passanti:
  `.\.venv\Scripts\python.exe -m unittest tests.test_memoria_diagnostic_cli`
  (`30 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- suite completa passante:
  `.\.venv\Scripts\python.exe -m pytest`
  (`679 passed`);
- nessun driver pCloud implementato;
- nessuna chiamata cloud eseguita;
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Evidenza Q2 `workspace_resolver` test dedicati:

- `memoria-engine/tests/test_workspace_resolver.py` creato;
- i test diretti di `resolve_data_root` sono stati spostati fuori da
  `tests.test_memoria_diagnostic_cli`;
- `tests.test_memoria_diagnostic_cli` resta focalizzato sui comandi CLI e sui
  bridge read-only;
- nessun codice runtime modificato;
- nessun cambio a comandi, output CLI, exit code, schema o workflow;
- test mirati passanti:
  `.\.venv\Scripts\python.exe -m unittest tests.test_workspace_resolver tests.test_memoria_diagnostic_cli`
  (`30 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- suite completa passante:
  `.\.venv\Scripts\python.exe -m pytest`
  (`679 passed`);
- nessun driver pCloud implementato;
- nessuna chiamata cloud eseguita;
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Evidenza Q2 `LocalWorkspaceStorage` path boundary:

- `memoria-engine/tests/test_workspace_storage.py` esteso con copertura sui
  path assoluti;
- path assoluti interni al workspace root accettati e normalizzati;
- path assoluti esterni al workspace root rigettati senza scritture;
- nessun codice runtime modificato;
- nessun cambio a comandi, output CLI, exit code, schema o workflow;
- test mirato passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_workspace_storage`
  (`5 tests`, `OK`);
- test mirati di contorno passanti:
  `.\.venv\Scripts\python.exe -m unittest tests.test_workspace_storage tests.test_workspace_resolver tests.test_memoria_diagnostic_cli`
  (`35 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- suite completa passante:
  `.\.venv\Scripts\python.exe -m pytest`
  (`681 passed`);
- nessun driver pCloud implementato;
- nessuna chiamata cloud eseguita;
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Evidenza Q2 `LocalWorkspaceStorage` directory entries:

- `memoria-engine/tests/test_workspace_storage.py` esteso con copertura sugli
  entry directory restituiti da `list_dir`;
- verificati path logico, flag `is_dir`/`is_file` e `size` assente per le
  cartelle;
- nessun codice runtime modificato;
- nessun cambio a comandi, output CLI, exit code, schema o workflow;
- test mirato passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_workspace_storage`
  (`6 tests`, `OK`);
- test mirati di contorno passanti:
  `.\.venv\Scripts\python.exe -m unittest tests.test_workspace_storage tests.test_workspace_resolver tests.test_memoria_diagnostic_cli`
  (`36 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- suite completa passante:
  `.\.venv\Scripts\python.exe -m pytest`
  (`682 passed`);
- nessun driver pCloud implementato;
- nessuna chiamata cloud eseguita;
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

## Prossimo incremento candidato

T33 - Pacchetto finanziatori, ora avviato come incremento corrente dopo la
chiusura di T32.

Possibili candidati successivi, da non avviare in questa sessione:

- T26-T28 cloud solo dopo T33 o su richiesta esplicita/blocco diretto della
  golden run;
- Q2 solo se rimuove un blocco diretto e documentato della golden run.

## Traccia parallela qualita'

La roadmap tecnica ora include la traccia Q - Qualita' e refactor continuo.

Questa traccia puo' procedere in parallelo agli incrementi T solo per audit
modulari o micro-refactor behavior-preserving, con test mirati e stop condition
esplicita. Non autorizza refactor ampi o cambi di CLI, schemi, workflow o
pipeline senza decisione dedicata.

Prossimo candidato tecnico: da definire.

## Evidenza T31

Preflight read-only del 2026-07-14:

- azione candidata selezionata per la demo:
  `research-feedback-action:7bdbb2060d955baa`;
- profilo collegato dal piano:
  `person:purocielo:andreoli-dino`;
- documento trigger:
  `legacy_csv:a4ac96061a2381b5`;
- valore/trigger:
  `ANDREOLI DINO`, da `intestazione_pdf`, con indizi collegati a nome,
  formazione, luoghi e date;
- fonti suggerite dall'azione:
  `storia_memoria_bo`, `partigiani_italia`;
- piano fonte-specifico gia' presente nel summary preview:
  `feedback-search-plan:a19b13e6e3cd8b0d`;
- stato del piano:
  `ready_for_review`, `execution_allowed=false`,
  `online_search_started=false`, `manual_review_required=true`;
- tentativi pianificati:
  `storia_memoria_bo` con `nome-cognome` e
  `testo-libero-nome-completo`; `partigiani_italia` con
  `cognome-nome-contains` e `solo-cognome-contains`;
- triage feedback attuale:
  `856` azioni pending, `0` accettate, quindi questa azione non e' ancora una
  decisione storica approvata;
- nessun outcome T31 trovato nella run canonica:
  restano presenti solo `research_feedback_actions_review_table` e
  `research_feedback_actions_review_summary`;
- nessun file del data root esterno modificato e nessuna ricerca avviata.

Avanzamento T31 repository-only del 2026-07-15:

- aggiunto in `memoria-engine` il builder preview-only
  `caduti_fonti_report.document_analysis.feedback_loop_outcome`;
- il builder registra un `FeedbackLoopOutcome` auditabile a partire da
  `FeedbackSearchPlan` e summary di triage storico, con stati ammessi
  `candidate_results`, `no_results`, `needs_manual_review` e
  `blocked_or_dynamic`;
- il loop viene marcato `closed_with_auditable_outcome` solo se l'azione
  risulta approvata per la demo da una decisione di triage `BUONA` o `DUBBIA`
  e l'esito e' registrabile; senza approvazione resta
  `pending_historian_approval`;
- l'artefatto produce una `search_memory_update_preview` collegata a profilo,
  action, piano, fonte, query/esito e run, ma mantiene
  `profile_write_allowed=false`, `claim_promotion_allowed=false`,
  `creates_verified_facts=false` e `applies_profile_patch=false`;
- coperti i casi sintetici `no_results`, mancanza di approvazione storica e
  `candidate_results` senza documento candidato;
- test mirati passanti:
  `.\.venv\Scripts\python.exe -m unittest tests.test_feedback_loop_outcome tests.test_feedback_search_plan tests.test_research_feedback_triage`
  (`13 tests`, `OK`);
- nessun file del data root esterno modificato, nessuna ricerca avviata,
  nessun nuovo claim promosso e nessuna patch applicata.

Chiusura T31 operativa del 2026-07-15:

- aggiunto il tool ripetibile
  `memoria-engine/tools/register_t31_demo_feedback_loop.py`;
- eseguito il tool sul data root autorizzato
  `P:\Comune\Me.Mo.Ri.a`, limitando le scritture agli artefatti preview/audit
  della run canonica;
- creata una tabella triage T31 ridotta alla singola azione
  `research-feedback-action:7bdbb2060d955baa`, marcata `BUONA` per la demo e
  audit-only;
- creato il piano fonte-specifico T31:
  `P:\Comune\Me.Mo.Ri.a\risultati\runs\prova-preview-profili-5-reviewed-01-pipeline\document_analysis\feedback_search_plan.t31-demo.json`;
- registrato l'esito:
  `P:\Comune\Me.Mo.Ri.a\risultati\runs\prova-preview-profili-5-reviewed-01-pipeline\historian_review\feedback_loop_outcome.t31-demo.json`;
- stato esito: `closed_with_auditable_outcome`;
- outcome: `needs_manual_review`, con `execution_mode=manual_review_session`;
- query/sessione: `nome-cognome; nom="Dino"; cog="Andreoli"` e
  `testo-libero-nome-completo; s="Dino Andreoli"`;
- il descrittore attivo
  `P:\Comune\Me.Mo.Ri.a\database\memoria_mvp_demo.active.json` punta ora agli
  artefatti T31 e contiene `t31_feedback_loop`;
- backup descrittore creato:
  `P:\Comune\Me.Mo.Ri.a\database\memoria_mvp_demo.active.before-t31-feedback-loop.json`;
- verifica read-only `memoria mvp demo --data-root "P:\Comune\Me.Mo.Ri.a"`
  conferma la presenza degli artefatti T31 e le safety flag:
  `applies_profile_patch=false`, `creates_canonical_verified_facts=false`,
  `modifies_canonical_profiles=false`;
- nessun claim promosso, nessuna patch applicata, nessun profilo canonico
  modificato, nessun dato reale copiato nei repository Git.

Nota storica: dopo T31 il prossimo passo era T32. T32 e' ora chiuso; T33 e'
l'incremento corrente.

## Motivazione rispetto alla roadmap

T12 ha seguito:

- roadmap master: stabilizzare la baseline post-migrazione prima di nuovi task
  funzionali;
- roadmap MVP: preparare una demo minima tracciabile senza trasformarla in
  pipeline massiva;
- roadmap tecnica: audit dei residui persona/seed prima di qualunque migrazione
  fisica o cambio runtime.

T13 ha ridotto il rischio residuo sui default legacy verso profili e CSV reali,
ma l'esperienza utente non deve regredire verso wrapper con path espliciti. Il
recupero T13b ristabilisce l'intento della CLI `memoria`: risolvere il data root
e offrire controlli read-only semplici. T14 ha proseguito la rimozione
controllata dei residui in `memoria-engine/ricerche` classificando
`llm_prompts`. T15 sposta i contratti LLM versionabili in `memoria-rules`
mantenendo comportamento invariato e fallback legacy controllato. T16 puo'
chiudere il ciclo rimuovendo o rendendo non operativo il residuo legacy
`llm_prompts`. I test CLI hanno poi evidenziato un gap: la CLI puo' mostrare lo
stato editoriale quando presente, ma i profili canonici attuali non espongono
ancora campi di stato scheda/profilo. T17 colma questo gap di contratto prima di
qualunque modifica ai dati reali. T18 ha completato il dry-run di
inizializzazione senza scrivere nel data root. Q1 ha individuato i moduli piu'
grandi e ha raccomandato un primo Q2 circoscritto sui parser Markdown di
`mvp_review_focus_table`, completato con comportamento invariato. I Q2
successivi hanno isolato il rendering diagnostico di `mvp_pilot_summary`, i
record manifest/log di `local_processing_runner`, il rendering MVP vault di
`export_obsidian_vault` e i parser PrimeFaces/tree di
`bundesarchiv_invenio_executor`, sempre con helper interni e test mirati. T19 ha
chiuso la pianificazione cross-platform: la direzione e' `memoria` Python come
superficie canonica futura, con PowerShell mantenuto per l'MVP finanziatori e
wrapper Linux futuro come facciata sottile. In assenza di una nuova decisione
funzionale esplicita, questa sessione prosegue con la traccia Q2 gia'
autorizzata, scegliendo un micro-refactor behavior-preserving su
`candidate_claims.py`, ultimo candidato rilevante rimasto dall'audit Q1. Il
micro-refactor ha isolato la diagnostica funnel claim in un helper puro,
mantenendo invariati output e workflow. Questa sessione completa lo stesso
confine Q2 su `candidate_claims.py` isolando la costruzione degli skipped claim,
seconda responsabilita' pura indicata dall'audit Q1.
Questa sessione prosegue la traccia Q2 con un micro-refactor altrettanto
limitato su `german_docs_downloader.py`, isolando solo il rendering Markdown del
manifest, gia' coperto dai test del downloader.
Questa sessione prosegue la stessa traccia Q2 su
`mvp_consolidated_review_ledger.py`, isolando solo il rendering Markdown del
ledger in un helper dedicato e mantenendo invariati consolidamento, CLI e output
osservabile.
Questa sessione prosegue la stessa traccia Q2 su `mvp_review_dashboard.py`,
isolando solo il rendering Markdown della dashboard in un helper dedicato e
mantenendo invariati build, CLI, JSON e output Markdown osservabile.
Questa sessione prosegue la stessa traccia Q2 su
`mvp_historical_review_targets.py`, isolando solo il rendering Markdown dei
target storici revisionabili in un helper dedicato e mantenendo invariati build,
lettura evidence store, CLI, JSON e output Markdown osservabile.
Questa sessione prosegue la stessa traccia Q2 su `mvp_review_session.py`,
isolando solo il rendering Markdown della sessione review in un helper dedicato
e mantenendo invariati build, focus review, template decisioni, CLI, JSON e
output Markdown osservabile.
Questa sessione prosegue la stessa traccia Q2 su `mvp_review_decisions.py`,
isolando solo il rendering Markdown del riepilogo decisioni in un helper
dedicato e mantenendo invariati validazione, sintesi sessione storici, CLI, JSON
e output Markdown osservabile.
Questa sessione prosegue la stessa traccia Q2 su `mvp_review_queue.py`,
isolando solo il rendering Markdown della review queue in un helper dedicato e
mantenendo invariati build queue, template decisioni, CLI, JSON e output
Markdown osservabile.
Questa sessione apre e chiude T20, primo bridge operativo read-only previsto da
T19: `memoria` Python espone ora `review discover/status/work` per orientarsi
sulle run e sulla worklist MVP senza sostituire i comandi PowerShell
decisionali usati per l'MVP finanziatori.
Questa sessione apre e chiude T21, secondo bridge operativo read-only previsto
da T19: `memoria` Python espone ora `consolidate discover/status` per
orientarsi sugli artefatti consolidati preview senza rigenerare ledger, scrivere
nello store o sostituire i comandi PowerShell preview usati per l'MVP
finanziatori.
Questa sessione apre e chiude T22, terzo bridge operativo read-only previsto da
T19: `memoria` Python espone ora `sources online/offline discover/status` per
orientarsi su registry fonti, sessione sources online e intake offline senza
avviare rete, download, OCR, pipeline o scritture nel data root.
Questa sessione apre e chiude T23: il workspace operativo viene riclassificato
come risorsa logica pluggable. `P:\Comune\Me.Mo.Ri.a` resta backend locale
compatibile per MVP e workflow validati, mentre pCloud diventa il primo backend
cloud candidato, da introdurre solo con incrementi read-only/mock prima di
qualunque scrittura o migrazione reale.
Questa sessione apre e chiude T24: il motore espone ora un contratto
`WorkspaceStorage` e un driver `LocalWorkspaceStorage`; `memoria doctor` usa il
driver local per le verifiche diagnostiche mantenendo invariato il comportamento
osservabile. pCloud resta in attesa della risoluzione del problema API aperto
con il supporto.
Questa sessione apre e chiude T25: il manifest workspace diventa
provider-aware, con provider attivo `local`, descrizione pCloud senza segreti e
resolver CLI aggiornato. Il backend pCloud resta non implementato e in hold
finche' l'accesso API non viene chiarito.
Questa sessione apre e chiude un Q2 behavior-preserving su `memoria_cli.py`:
la risoluzione data-root/manifest viene spostata in `workspace_resolver.py`,
riducendo la responsabilita' della CLI senza cambiare API pubblica, output o
workflow.
Questa sessione apre e chiude un Q2 test-only su `workspace_resolver`: i test
del resolver vengono isolati dal test della CLI diagnostica, migliorando la
tracciabilita' del confine introdotto senza toccare runtime o comportamento.
Questa sessione apre e chiude un Q2 test-only su `LocalWorkspaceStorage`:
rafforza la garanzia che il driver locale resti confinato al workspace root
anche quando riceve path assoluti, senza anticipare T26 o introdurre accessi
cloud.
Questa sessione apre e chiude un Q2 test-only su
`LocalWorkspaceStorage.list_dir`: rende esplicito nei test il contratto degli
entry directory locali, utile per mantenere stabile la diagnostica del workspace
e confrontare in futuro backend alternativi senza introdurre pCloud ora.
Questa sessione apre e chiude T26a, scelto esplicitamente come avanzamento MVP
non-cloud mentre T26 resta in hold: `memoria review decisions` rende visibile
dalla CLI Python lo stato delle decisioni umane review gia' registrate negli
artefatti preview, senza applicare nuove decisioni e senza spostare il workflow
decisionale PowerShell usato per la demo finanziatori.
Questa sessione apre e chiude T26b, secondo avanzamento MVP non-cloud:
`memoria mvp status` compone una vista unica e read-only del walkthrough demo
locale, rendendo provabile il percorso profili -> review -> decisioni ->
consolidamento -> fonti senza generare nuovi artefatti e senza attendere T26
pCloud.

## Vincoli

- Per workflow operativi sui dati reali, il perimetro massimo autorizzato e'
  `P:\Comune\Me.Mo.Ri.a` con le sue sotto-cartelle.
- Scrivere nel data root esterno solo quando serve all'incremento corrente
  documentato, riportando file toccati, validazioni e impatto.
- Non scrivere dati reali fuori da `P:\Comune\Me.Mo.Ri.a`.
- Non cancellare o sovrascrivere massivamente, modificare profili canonici,
  applicare patch o promuovere fatti canonici senza incremento dedicato,
  backup e audit trail.
- Non copiare dati reali nei repository Git.
- Non lanciare OCR.
- Non elaborare JSON-LD.
- Non generare schede.
- Non fare pipeline end-to-end.
- Non fare refactor ampio senza decisione nel decision log.
- Per refactor continuo usare `playbooks/09-continuous-refactor.md` e la traccia
  Q della roadmap tecnica.
- Eseguire un solo incremento piccolo e verificabile per sessione.

## Comandi di validazione

Per incrementi solo documentali:

```powershell
Get-Content memoria-bootstrap\docs\current-next-increment.md
Get-Content memoria-bootstrap\docs\roadmap\02-technical-roadmap.md
Get-Content memoria-bootstrap\docs\funding-demo-golden-path.md
Get-Content memoria-bootstrap\docs\funding-demo-t29-contract.md
Get-Content memoria-bootstrap\docs\decision-log.md
```

Per incrementi che modificano `memoria-engine`:

```powershell
cd memoria-engine
.\.venv\Scripts\python.exe -m pytest
```

Per incrementi mirati sui profili persona:

```powershell
cd memoria-engine
.\.venv\Scripts\python.exe -m unittest tests.test_packaging tests.test_person_profiles tests.test_profiles_runner tests.test_feedback_search_plan tests.test_mvp_document_intake_preflight
```

Per verifiche read-only della CLI:

```powershell
cd memoria-engine
$env:MEMORIA_DATA_ROOT = "P:\Comune\Me.Mo.Ri.a"
.\.venv\Scripts\memoria.exe data-root
.\.venv\Scripts\memoria.exe inventory
.\.venv\Scripts\memoria.exe doctor
.\.venv\Scripts\memoria.exe profiles status
.\.venv\Scripts\memoria.exe mvp demo
```

Per verifiche T31/T32 mirate:

```powershell
cd memoria-engine
.\.venv\Scripts\python.exe -m py_compile tools\register_t31_demo_feedback_loop.py
.\.venv\Scripts\python.exe -m unittest tests.test_feedback_loop_outcome tests.test_feedback_search_plan tests.test_research_feedback_triage tests.test_packaging
.\.venv\Scripts\memoria.exe mvp demo --data-root "P:\Comune\Me.Mo.Ri.a"
```

## Criteri di accettazione del prossimo incremento

- `memoria mvp demo` mostra la run canonica e tutti gli artefatti T30/T31
  presenti;
- i safety flag restano preview-only e non pubblicabili;
- CLI Python, wrapper PowerShell e guide non puntano a run diverse;
- i riferimenti operativi obsoleti, inclusi vecchi vincoli di autorizzazione
  non piu' coerenti con il decision log, sono allineati;
- il walkthrough 7-10 minuti e' verificato almeno in asciutto;
- il pacchetto repository distribuibile non contiene dati reali;
- il sidecar T30 resta dichiarato come ponte temporaneo preview-only da
  sostituire con il flusso standard, senza bloccare la prova interna.

## Aggiornamenti da fare a fine incremento

- Aggiornare questa sezione `Stato` quando l'incremento cambia o viene chiuso.
- Spostare il prossimo candidato nella sezione `Incremento corrente`.
- Registrare in `decision-log.md` solo le decisioni architetturali o
  metodologiche nuove.
- Aggiornare roadmap o playbook solo se cambia il processo operativo.
- Riportare nel riepilogo finale i file modificati e le validazioni eseguite.
