# Person Profile Feedback Loop Core

## Scopo

Guidare incrementi su `PersonResearchProfile`, candidate updates, profile patch
preview/dry-run e ciclo di feedback dalla review a una nuova ricerca.

## Separazione dei livelli

```text
seed/search_hints = indizi non pubblicabili
evidence_claims = candidati con provenance
related_person_hints = piste di ricerca
verified_facts = claim revisionati e riconciliati
profile_patch = modifica proposta, non applicata
feedback_action = richiesta di nuova ricerca
search_run_outcome = risultato o no-result tracciato
```

## Regole di riconciliazione multi-fonte

- Ogni claim mantiene `source_document_id`, source e metodo.
- Claim compatibili possono essere raggruppati, non fusi cancellando la
  provenance.
- Claim divergenti restano entrambi visibili finche' lo storico decide.
- Una decisione su un claim non modifica automaticamente gli altri claim.
- La scheda demo deve mostrare contributi di almeno due fonti differenti.

## Regole patch

- Non modificare profili JSON-LD canonici salvo incremento esplicito.
- Nessun merge automatico.
- `CandidateProfileUpdate` arricchisce solo come proposta.
- `CandidateNewProfile` non crea un profilo canonico senza review.
- `ProfilePatch` resta preview/dry-run finche' non esistono backup, decisione,
  audit e test.
- Ogni patch conserva profilo, claim, documento, decisione, reviewer e run.
- Per un'applicazione canonica autorizzata si applica la
  [Checklist di applicazione canonica](codex-session-contract.md#checklist-di-applicazione-canonica),
  inclusi piano/provenance/hash, dry-run, autorizzazione separata, backup,
  audit post-run e rollback condizionato agli hash.

## Regole del feedback loop

Un feedback loop e' chiuso solo quando:

1. lo storico seleziona una lacuna, incertezza o contraddizione;
2. viene creata una feedback action con motivazione;
3. planner e registry producono una strategia fonte-specifica;
4. la ricerca viene eseguita o affidata a review manuale tracciata;
5. l'esito viene registrato come documento/claim oppure stato negativo
   (`no_results`, `needs_manual_review`, `blocked_or_dynamic`);
6. il profilo o il piano successivo collega l'esito all'azione originaria;
7. eventuali nuovi claim tornano in review e non diventano automaticamente
   verified facts.

La sola generazione di molte query candidate non completa il ciclo.

## Raccolta delle misure T49

Le metriche T49 si alimentano con artifact di una ricerca e di una review
effettivamente avvenute. Registrare gli ID e i timestamp durante il lavoro;
non ricostruire tempi, token o costi a posteriori. Conservare run e dati reali
fuori da Git.

Prima genera le action candidate dal directory di `DocumentMentionCandidate`
usando il launcher installato. Il comando produce una preview JSON/Markdown e
digest SHA-256 per ogni file di menzioni; non crea fatti o patch ai profili:

```text
memoria feedback actions --mentions-dir <mentions-dir> --output-dir <actions-dir> --output-json <actions.json> --output-md <actions.md>
```

`feedback plan` e il riepilogo prodotto da `feedback triage summarize-table`
conservano `actions_sha256` per l’action set consumato. Quando si registra un
outcome passando `--review-summary-json`, l’approvazione della decisione viene
attribuita solo se il plan e il riepilogo hanno digest SHA-256 validi e uguali;
digest mancante o diverso lascia l’outcome in attesa di approvazione. Questo
controllo lega la review ai byte esatti, ma non autorizza né avvia ricerche.
L’evaluation applica la stessa condizione al KPI di latenza: un riepilogo con
digest mancante o diverso dal piano resta escluso dalla misura e produce
un’issue di provenance.
La tabella Markdown di triage include il digest dell’action set all’origine;
`summarize-table` marca `invalid` una tabella priva di digest (incluse tabelle
legacy) o non più corrispondente al file actions passato.

1. Genera la preview del piano con le azioni, l'indice profili e il registry
   espliciti:

   ```text
   memoria feedback plan --actions-json <actions.json> --profiles-index <profiles-index.jsonld> --sources-yaml <camalanca_fonti.yaml> --output-json <plan.json> --output-md <plan.md>
   ```

   Il comando produce solo il piano review-only; `execution_allowed` e
   `online_search_started` restano false.
2. Prima di una ricerca, raccogli la valutazione umana delle action candidate
   con il wizard dal launcher. Chiede l'identificativo
   dichiarato del reviewer, che non viene autenticato; mostra un'azione alla volta
   e registra l'inizio/fine di ogni decisione:

   ```text
   memoria feedback triage review-wizard --actions-json <actions.json> --output-review-table-md <decisions.md> --output-json <review-summary.json> --output-md <review-summary.md>
   ```

   I file vengono scritti solo dopo conferma; `q` o mancata conferma non
   producono artifact. Le decisioni `BUONA`, `DUBBIA` e `INUTILE` valutano
   l'utilita' della action: non sono un'autorizzazione a eseguire la ricerca.
   Anche `approved_for_demo` nell'outcome non abilita l'esecuzione; il piano
   resta `execution_allowed=false`. Prima di procedere, verifica che la richiesta
   utente autorizzi gia' action, fonte e strategia/query; altrimenti fermati e
   chiedi quel via libera esplicito. Per review batch resta disponibile la coppia
   `memoria feedback triage build-table` / `summarize-table`; compilare decisioni
   e tempi nel Markdown, mai in JSON. Le tabelle senza hash o con hash diverso
   dall'action set corrente vengono invalidate.
3. Solo dopo un tentativo di ricerca realmente autorizzato e svolto, registra
   l'esito reale dal launcher:

   ```text
   memoria feedback outcome --feedback-plan-json <plan.json> --review-summary-json <review-summary.json> --action-id <action_id> --plan-id <plan_id> --source-id <source_id> --strategy-id <strategy_id> --outcome-status <candidate_results|no_results|needs_manual_review|blocked_or_dynamic> --query <query-eseguita> --run-id <run_id> --executed-at <timestamp-ISO-8601-con-timezone> --result-source-document-id <source_document_id> --output-json <outcome.json> --output-md <outcome.md>
   ```

   Ripetere `--strategy-id` e `--result-source-document-id` quando necessario;
   non aggiungere ID documento se non identificano SourceDocument registrati.
   Conserva `feedback_search_plan_id`, `action_id`, `source_id`, strategia,
   `run_id`, query ed `executed_at` timezone-aware effettivi. `no_results` non
   dimostra assenza storica.
4. Per attribuzione claim, passa al valutatore un `CandidateEvidenceClaimSet`
   reale con ID univoco, `source_id` e `source_document_id`. La metrica misura
   la presenza di questi riferimenti, non verifica l'esistenza nel catalogo.
5. Se la riconciliazione incontra un conflitto reale, registra in
   `FeedbackLoopEvaluationMeasurements.conflicts` `conflict_id`, `outcome_id`,
   `before_claim_ids` e `after_claim_ids`. Non creare record di conflitto per
   simulare una misura.
6. Per l'uso sessione registra in `sessions` `session_id`, `run_id` e i valori
   realmente disponibili: `input_tokens`, `cached_input_tokens`,
   `output_tokens`, `cost_usd`. Per confrontare baseline e candidate aggiungi
   `comparison_group_id`, `task_contract_sha256`, `quality_gate_status`,
   `model_id` e `comparison_role`. Il gruppo richiede un solo baseline e almeno
   un candidate, fingerprint del task identico e quality gate `passed`; i delta
   descrivono osservazioni e non dimostrano risparmi o causalita'.

Usa il launcher installato `memoria feedback evaluate`; non invocare il modulo
con `python -m` e non chiedere all'utente di compilare artifact JSON:

```text
memoria feedback evaluate --feedback-plan-json <plan.json> --outcome-json <outcome.json> --candidate-claims-json <claims.json> --measurements-json <measurements.json> --review-summary-json <review-summary.json> --output-json <evaluation.json> --output-md <evaluation.md>
```

Ripetere `--outcome-json` per ogni outcome. Claims, measurements e review
summary sono input opzionali: ometterli lascia le metriche corrispondenti
`unavailable`, senza stime. Gli input sono hash-bound nell'evaluation. Il log
locale di routing esaminato nella sessione T48i conteneva eventi, modello,
agente e orario, ma non token o costi; quei valori richiedono una fonte di
telemetria esplicita. Se il provider non espone la misura, lasciarla assente.

## File tipici

```text
memoria-engine/code/caduti_fonti_report/*profile*
memoria-engine/code/caduti_fonti_report/document_analysis/*profile*
memoria-engine/code/caduti_fonti_report/*feedback*
memoria-engine/tests/test_*profile*.py
memoria-engine/tests/test_*feedback*.py
<data-root>/ricerche/person_profiles/
<data-root>/risultati/runs/
```

I path nel data root sono operativi e non devono essere copiati nei repository.

## Test e verifica

- usare fixture sintetiche per patch e feedback;
- verificare idempotenza e audit linkage;
- verificare che `no_results` non generi fatti;
- per T31, usare una ricerca controllata o un pacchetto manual-review tracciato;
- non richiedere una pipeline massiva.

## Revisione manuale a blocchi

Quando una worklist contiene molti candidati:

1. estrarre blocchi numerati con `candidate_update_id` stabile, valore, profilo
   e documento sorgente;
2. sottrarre gli ID gia' decisi prima di costruire il blocco successivo;
3. mostrare all'utente le proposte con gli stessi ID usati nel registro;
4. dopo la registrazione, verificare conteggi e copertura degli ID;
5. generare preview separate per decisioni accettate e lasciare invariati i
   profili canonici;
6. se un blocco e' stato costruito con un mapping errato, invalidare il
   registro, conservarlo per audit e registrare una correzione con
   `supersedes` o riferimento esplicito all'artefatto invalidato.

Un riepilogo per nome non sostituisce il controllo sugli ID: nomi ripetuti,
alias e frammenti estratti dal contesto possono produrre mapping ambiguo.

## Review multi-profilo via CLI

La review di più profili è una sola sessione preview-only con una worklist
comune, non una fusione dei profili. Il percorso raccomandato è:

1. usare `memoria review discover` per verificare le run candidate;
2. usare `memoria review start --preview`, con `--run-id` solo quando la scelta
   della run deve essere esplicita;
3. usare `memoria review targets --profile-id <id> --profile-id <id>` per
   restringere la vista ai profili interessati;
4. mostrare e decidere i target con `item_id` o numero di worklist;
5. verificare summary, conteggi e provenance con `memoria review decisions`.

Il filtro multi-profilo non altera queue, profili o evidence store. Non si
riconosce un target dal solo nome: il mapping minimo è profilo + documento +
`item_id`. Una decisione su un profilo non approva né modifica automaticamente
claim o profili omonimi.

Se non esiste una run, il flusso si ferma dopo `discover` con esito esplicito:
prima si prepara o si seleziona una run tramite il workflow autorizzato, poi si
avvia la review. Non si crea una decisione vuota e non si modifica il profilo
per “iniziare” la raccolta.

## Gate finale della migrazione

Prima di dichiarare chiusa la revisione verificare:

- copertura completa della worklist o elenco esplicito dei `needs_review`;
- conteggi finali per `accepted`, `rejected` e `needs_review`;
- provenance presente per ogni decisione accettata;
- `preview_only=true` e nessuna modifica canonica;
- JSON valido, diff pulito e artefatti finali collegati al planner.

## Stop condition

Fermarsi se serve:

- approvare un claim al posto dello storico;
- risolvere definitivamente un conflitto;
- applicare una patch canonica;
- pubblicare una scheda;
- usare credenziali non disponibili.
