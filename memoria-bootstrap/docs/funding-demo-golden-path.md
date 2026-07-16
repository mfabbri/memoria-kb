# Funding Demo Golden Path

Data: 2026-07-15

Stato: direzione approvata; T29, T30, T31 e T32 chiusi; T33 e' il prossimo
incremento prioritario.

Contratto operativo T29:

```text
memoria-bootstrap/docs/funding-demo-t29-contract.md
```

## Scopo

Trasformare le capacita' tecniche gia' presenti in Me.Mo.Ri.A in una sola storia
dimostrativa, verificabile e comprensibile da storici e finanziatori.

La rifattorizzazione ha consolidato architettura, CLI, registry fonti, knowledge,
regole, evidence store e output preview. Il rischio principale non e' piu'
l'assenza di capacita', ma la dispersione fra run, report e percorsi differenti.

La golden path deve dimostrare:

```text
fonti eterogenee
  -> documenti identificabili
  -> claim con provenance
  -> riconciliazione multi-fonte
  -> decisione umana
  -> fatto verificato preview
  -> patch profilo preview
  -> feedback per una nuova ricerca
  -> esito della ricerca tracciato
```

## Problemi che questa corsia deve correggere

### Run frammentate

Artefatti utili possono esistere in run differenti. La demo esterna non deve
richiedere all'operatore di cambiare run per mostrare review, decisioni,
consolidamento, fonti e patch.

### Merge multi-fonte poco evidente

Una vista unica non e' sufficiente se tutti i fatti rilevanti derivano da una
sola fonte. La demo deve rendere visibile il contributo specifico di documenti
eterogenei allo stesso profilo.

### Feedback loop solo potenziale

Generare molte azioni o query non dimostra il ciclo. Almeno una richiesta dello
storico deve essere eseguita e produrre un esito auditabile.

### Output troppo numerosi

Il valore non deve essere affidato a una cartella di report. Ogni artefatto deve
avere un ruolo preciso nel walkthrough.

### Direzione tecnica dispersiva

Storage cloud, nuove fonti e micro-refactor restano validi, ma non devono
precedere la costruzione della prova finanziatori salvo blocco diretto.

## Contratto del caso demo

### Persona e documenti

Selezionare:

- 1 persona principale con materiale sufficiente;
- opzionalmente 1 persona di contrasto;
- 2-4 documenti;
- almeno due fonti o famiglie documentali differenti;
- almeno una fonte offline/locale e una fonte online/istituzionale, quando i
  materiali gia' acquisiti lo consentono senza nuova acquisizione rischiosa.

Il caso ideale contiene:

- una informazione complementare fra fonti;
- una incertezza o discrepanza;
- una domanda che possa generare una ricerca successiva ragionevole.

### Riconciliazione multi-fonte

La scheda di lavoro deve mostrare per ogni claim:

- soggetto collegato;
- valore proposto;
- tipo di claim;
- documento e fonte;
- metodo di estrazione;
- confidenza;
- stato di review;
- eventuale relazione con claim compatibili o conflittuali.

Il merge e' accettato per la demo se si verifica almeno una delle condizioni:

1. lo stesso fatto e' sostenuto da due documenti indipendenti;
2. due fonti forniscono campi complementari nella stessa scheda;
3. due fonti propongono valori divergenti e la review rende visibile la scelta
   o l'incertezza senza cancellare l'alternativa.

### Decisione umana

La demo deve contenere almeno:

- una decisione `confirm`/`accept` o equivalente;
- una decisione `uncertain`, `reject` o una richiesta di ulteriori fonti;
- reviewer e timestamp;
- collegamento a claim e documento;
- audit trail nel review/evidence store.

### Patch preview

Almeno una patch deve:

- derivare da una decisione approvata;
- riferirsi al profilo selezionato;
- mostrare prima/dopo o operazione proposta;
- restare preview/dry-run;
- non modificare automaticamente il profilo canonico;
- conservare run, document, claim, decision e reviewer ID.

## Contratto del feedback loop chiuso

Il ciclo e' completo solo se tutti i passaggi sono presenti.

1. **Trigger storico**
   - lacuna, conflitto o dato insufficiente;
   - decisione o azione esplicita dello storico.

2. **Candidate feedback action**
   - domanda formulata;
   - persona/evento/luogo interessato;
   - motivazione e priorita'.

3. **Piano fonte-specifico**
   - fonte o famiglia di fonti;
   - query e varianti;
   - strategia;
   - limiti e stato atteso.

4. **Esecuzione controllata**
   - nessuna ricerca massiva;
   - run e timestamp;
   - stato `candidate_results`, `no_results`, `needs_manual_review`,
     `blocked_or_dynamic` o equivalente.

5. **Esito**
   - nuovo `SourceDocument`/claim candidato; oppure
   - esito negativo documentato che evita di ripetere la stessa ricerca.

6. **Rientro nel profilo**
   - aggiornamento preview della memoria di ricerca;
   - collegamento fra feedback action, search run, risultato e profilo;
   - nessun fatto promosso senza nuova review.

Un `no_results` e' un esito valido se e' tracciato e modifica la memoria della
ricerca, evitando che l'assenza di risultato venga interpretata come assenza del
fatto storico.

## Contratto della golden run

T30 deve introdurre o formalizzare un descrittore di demo nel workspace esterno,
senza dati reali nei repository. Nome indicativo:

```text
<data-root>/database/memoria_mvp_demo.active.json
```

Il nome definitivo puo' essere confermato in T29. Il descrittore dovrebbe
contenere almeno:

```json
{
  "contract_version": "memoria_mvp_demo.v1",
  "run_id": "<canonical-run-id>",
  "primary_profile_ids": ["<profile-id>"],
  "source_document_ids": ["<document-id>"],
  "source_ids": ["<source-id>"],
  "review_session_id": "<review-session-id>",
  "consolidate_session_id": "<consolidate-session-id>",
  "status": "ready_for_internal_demo",
  "artifacts": {}
}
```

Il descrittore non sostituisce manifest di run o store. Serve a dichiarare quale
run e quali artefatti costituiscono la demo ufficiale.

## Artefatti minimi della golden run

- manifest della run;
- profilo/i selezionato/i;
- inventario documenti e source records;
- tabella di riconciliazione multi-fonte;
- claim candidati rilevanti;
- review worklist ridotta;
- decision summary;
- verified facts preview;
- profile patch preview;
- feedback action e search plan;
- esito del feedback loop;
- scheda/dossier leggibile dallo storico;
- report di readiness della demo.

Gli artefatti devono puntare allo stesso `run_id` oppure dichiarare in modo
esplicito e auditabile eventuali derivazioni da run precedenti. Per il
walkthrough si preferisce una sola run autosufficiente.

## Walkthrough obiettivo, 7-10 minuti

1. **Il problema**: informazioni disperse in documenti e fonti incompatibili.
2. **Il caso**: persona scelta e documenti minimi.
3. **La provenance**: ogni claim torna al documento.
4. **Il merge**: le fonti contribuiscono o divergono nella stessa vista.
5. **La review**: lo storico decide e l'incertezza resta visibile.
6. **La patch**: il sistema propone l'aggiornamento senza applicarlo.
7. **Il feedback**: la review genera una nuova ricerca.
8. **L'esito**: nuovo documento/claim o no-result auditabile.
9. **Il finanziamento**: estendere questo metodo a piu' profili, fondi e
   istituti senza perdere tracciabilita'.

## Milestone tecniche

### T29 - Contratto Funding Demo Golden Path

Output solo documentale e di selezione:

- caso candidato;
- criteri di fonti/documenti;
- contratto golden run;
- artifact map;
- walkthrough;
- comandi di verifica read-only;
- gap tecnici puntuali da risolvere in T30-T32.

Nessuna nuova pipeline deve essere lanciata in T29.

Stato: chiuso il 2026-07-13. Caso principale selezionato:
`person:purocielo:andreoli-dino`; caso di contrasto leggero:
`person:purocielo:balboni-william`; descrittore T30 scelto:
`<data-root>/database/memoria_mvp_demo.active.json`.

### T30 - Golden run multi-fonte canonica

- creare o rigenerare la run selezionata;
- ridurre il perimetro al caso demo;
- allineare store, sessioni e artefatti;
- produrre la tabella di riconciliazione;
- registrare il descrittore della demo;
- mantenere tutto preview-only.

Stato: chiuso il 2026-07-14. La run canonica e' dichiarata nel descrittore
`<data-root>/database/memoria_mvp_demo.active.json` con ledger preview T30,
tabella di riconciliazione multi-fonte, decisioni, verified facts preview e
ProfilePatch preview allineati a
`prova-preview-profili-5-reviewed-01-pipeline`. Il sidecar T30 resta ponte
temporaneo preview-only da sostituire in T32 con il flusso standard.

### T31 - Feedback loop chiuso

- selezionare una decisione che richiede nuove fonti;
- produrre e approvare la feedback action;
- eseguire una ricerca controllata;
- registrare il risultato;
- reinserire l'esito nella memoria di ricerca;
- mostrare il cambiamento nella scheda o nel piano successivo.

Stato: chiuso il 2026-07-15. Preflight read-only del 2026-07-14: selezionata
come candidata demo `research-feedback-action:7bdbb2060d955baa`, collegata ad
Andreoli e al documento `legacy_csv:a4ac96061a2381b5`; il piano
`feedback-search-plan:a19b13e6e3cd8b0d` e' pronto per review con fonti
`storia_memoria_bo` e `partigiani_italia`.

Aggiornamento repository-only del 2026-07-15: `memoria-engine` dispone ora del
builder preview-only `feedback_loop_outcome`, che puo' registrare l'esito T31
come `candidate_results`, `no_results`, `needs_manual_review` o
`blocked_or_dynamic`, collegandolo ad action, piano, profilo e memoria di
ricerca preview senza creare verified facts, senza promuovere claim e senza
modificare profili. Questo aggiornamento ha preparato la chiusura operativa:
mancavano ancora approvazione demo ed esito persistito nel perimetro operativo
autorizzato della golden run.

Chiusura operativa del 2026-07-15: la singola azione demo e' stata isolata in
artefatti T31 audit-only, marcata `BUONA` per la demo, collegata al piano
`feedback-search-plan:a19b13e6e3cd8b0d` e registrata con
`FeedbackLoopOutcome` preview-only:

```text
P:\Comune\Me.Mo.Ri.a\risultati\runs\prova-preview-profili-5-reviewed-01-pipeline\historian_review\feedback_loop_outcome.t31-demo.json
```

Stato loop: `closed_with_auditable_outcome`. Esito: `needs_manual_review`.
Il descrittore attivo della demo punta ora agli artefatti T31. Nessun claim e'
stato promosso, nessuna patch e' stata applicata e nessun profilo canonico e'
stato modificato.

### T32 - Hardening demo

- rigenerare dal flusso standard di arricchimento schede lo stesso risultato
  ottenuto temporaneamente in T30 con il sidecar `--output-aligned-ledger`;
- non avanzare la prova generale se i claim `legacy_csv` e `local_docx` della
  golden run dipendono ancora dal sidecar come fonte primaria invece che dal
  percorso documenti/claim/evidence store/ledger;
- correggere selezione/visualizzazione della run canonica;
- correggere test path/cross-platform che bloccano la ripetibilita';
- allineare CLI, PowerShell e guide;
- rimuovere ambiguita' di naming come candidati alla pubblicazione non
  approvati;
- verificare distribuzione del repository senza dati reali;
- eseguire prova generale offline o controllata.

Stato: chiuso il 2026-07-16. Avanzamento del 2026-07-15: `memoria mvp status` e'
stato allineato a `memoria mvp demo` e mostra ora la golden run canonica dal
descrittore attivo, con status, artefatti e safety flag preview-only. La
verifica reale conferma `ready_for_internal_demo` sulla run
`prova-preview-profili-5-reviewed-01-pipeline`, `12/12` artefatti presenti e
`publication_ready=false`. La scansione repository non ha trovato corpus
binario, database o log, ma mantiene aperto il rischio dei profili JSON-LD
legacy in `memoria-engine/ricerche/person_profiles` per il pacchetto
distribuibile. Evidenza:
`memoria-bootstrap/docs/funding-demo-t32-hardening-readiness.md`.

Avanzamento walkthrough del 2026-07-15: eseguita prova asciutta read-only del
percorso demo. `memoria consolidate status` espone ora anche la `Demo golden
run` dal descrittore e avvisa quando la sessione consolidate attiva punta a una
run diversa, evitando ambiguita' durante la presentazione. Evidenza:
`memoria-bootstrap/docs/funding-demo-t32-walkthrough-dry-run.md`.

Avanzamento rischio distribuzione del 2026-07-16: il rischio dei profili
JSON-LD legacy in `memoria-engine/ricerche/person_profiles` e' stato trattato
come blocker esplicito per il pacchetto repository/workspace distribuibile
esterno. Il package Python resta confinato a `code`, ma un archivio completo del
tree non e' pronto per distribuzione finche' quei profili non vengono esclusi o
rimossi con passaggio dedicato e auditabile. Evidenza:
`memoria-bootstrap/docs/funding-demo-t32-distribution-risk.md`.

Avanzamento trattamento sidecar del 2026-07-16: verificato in sola lettura che
la demo interna resta `ready_for_internal_demo` usando il ledger sidecar
`mvp_consolidated_review_ledger.t30-preview.json`, mentre il flusso standard
senza sidecar resta `blocked_for_internal_demo`: copre solo
`partigiani_italia`, lascia mancanti `legacy_csv` e `local_docx`, e non scrive
output. Il sidecar resta quindi ponte preview-only accettabile per walkthrough
interno, ma non percorso canonico per T33. Evidenza:
`memoria-bootstrap/docs/funding-demo-t32-sidecar-treatment.md`.

Chiusura trattamento sidecar del 2026-07-16: implementato nel builder standard
del consolidated review ledger il riallineamento preview-only da link
documento-persona e da claim collegati fuori perimetro demo. Il ledger attivo
della golden run e' ora `mvp_consolidated_review_ledger.json`, il descrittore
attivo non punta piu' al sidecar T30 e `memoria mvp demo-build` senza
`--ledger` conferma `ready_for_internal_demo`, 3 famiglie coperte e 4/4
documenti coperti. Nessun profilo canonico modificato, nessuna patch applicata
e nessun verified fact canonico creato.

Chiusura rischio distribuzione del 2026-07-16: aggiunta `.gitattributes` con
esclusioni `export-ignore` per i residui operativi legacy
`memoria-engine/ricerche/person_profiles/**`,
`memoria-engine/ricerche/caduti_purocielo.csv` e
`memoria-engine/ricerche/mvp/**`. `tests.test_packaging` verifica la presenza
delle esclusioni. Il tree locale conserva i profili legacy per continuita', ma
il pacchetto distribuibile deve essere prodotto tramite un archivio che rispetti
queste regole. Evidenza:
`memoria-bootstrap/docs/funding-demo-t32-distribution-risk.md`.

### T33 - Pacchetto finanziatori

- dossier breve;
- script del walkthrough;
- diagramma architetturale e metodologico;
- screenshot o output stabilizzati;
- roadmap dell'uso dei fondi;
- dichiarazione trasparente di limiti e prossimi passi.

Stato: aperto e prioritario.

Avanzamento del 2026-07-16: creato l'entrypoint documentale T33
`memoria-bootstrap/docs/funding-demo-t33-package-entrypoint.md`, con run
canonica, reading order, walkthrough 7-10 minuti, comandi fallback, guardrail
editoriali e checklist dei criteri T33. Nessuna scrittura nel data root esterno
e nessun output preview presentato come pubblicabile.

Avanzamento del 2026-07-16: creato il diagramma T33
`memoria-bootstrap/docs/funding-demo-t33-evidence-flow-diagram.md`, collegato
all'entrypoint del pacchetto. Il diagramma rende leggibile per finanziatori la
catena fonti-documenti-evidenze-review-patch preview-feedback outcome e ribadisce
i safety flag preview-only.

Avanzamento operativo del 2026-07-16: il builder del pacchetto finanziatori e'
stato reso descriptor-aware e ha generato nella run canonica:
`mvp_funding_dossier.md`, `mvp_go_no_go_checklist.md` e
`funding_package_index.md`. Il go/no-go usa il perimetro del descriptor attivo
1 profilo primario, 4 documenti e 3 famiglie fonte, con esito
`go_with_review_blockers`: demo finanziabile e revisionabile, non pubblicabile.

Avanzamento del 2026-07-16: creata la scheda caso demo
`memoria-bootstrap/docs/funding-demo-t33-demo-case-card.md`, collegata
all'entrypoint T33. La scheda racconta il caso Andreoli/Balboni con provenance
leggibile, famiglie fonte, stati di riconciliazione, decisione storica,
verified facts preview, ProfilePatch preview e feedback outcome, mantenendo
espliciti i guardrail preview-only.

## Priorita' e stop condition

Fino a T33:

- T29-T33 prevalgono su T26-T28 e Q2;
- un Q2 puo' entrare solo come sotto-task se corregge un blocco della golden run;
- una nuova fonte puo' entrare solo se il caso selezionato non puo' dimostrare il
  merge con materiali gia' disponibili;
- non aumentare il perimetro oltre 2 profili e 4 documenti senza decisione
  esplicita;
- non applicare patch ai profili canonici;
- non presentare preview come pubblicazione.

## Esito atteso

Al termine di T33, un osservatore deve poter rispondere si' a queste domande:

- capisco da dove viene ogni informazione?
- vedo che fonti differenti sono state riconciliate senza perdere la loro voce?
- vedo cosa ha deciso lo storico e cosa resta incerto?
- vedo una modifica proposta ma non applicata automaticamente?
- vedo che la revisione ha prodotto una nuova ricerca concreta?
- capisco perche' il finanziamento permette di scalare un metodo gia'
  dimostrato, non solo un'idea?
