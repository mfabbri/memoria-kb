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

## Seed importati da CSV

I profili operativi non devono mantenere `seed.source` o `seed.payload`
collegati a `caduti_purocielo.csv`. Per la migrazione amministrativa usare il
launcher installato `memoria profiles seed-migration` in preview, verificare il
conteggio atteso e l'audit, poi aggiungere `--apply` solo con autorizzazione
esplicita. L'operazione conserva gli originali nei backup hash-verificati e
marca il profilo con `seed.source=profile_seed_migration`; non revisiona dati
biografici, non cambia stati editoriali e non crea `verified_facts`. Il termine
`profile_seed_migration` registra la trasformazione del seed e non e' una fonte
storica.

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

La review dell'utilità di una `ResearchFeedbackAction` non risolve l'identità
della menzione e non autorizza una ricerca. Prima del run, confrontare ogni
`attempt_id` del piano con l'autorizzazione esplicita dell'utente, i run già
eseguiti e le query escluse. Eseguire soltanto gli ID autorizzati e non ancora
consumati con `memoria sources online run --attempt-id ...`; il flag è
ripetibile e consente di escludere i template non selezionati. Un piano può
contenere attempt già eseguiti o esclusi: `ready_for_review` e `BUONA` non
abilitano l'esecuzione.

Se non restano attempt autorizzati, fermarsi e proporre una nuova query
fonte-specifica per approvazione. Non attribuire retroattivamente a una nuova
action risultati di ricerche avvenute prima che action e piano fossero creati.
Registrare `FeedbackLoopOutcome` solo dopo il run autorizzato collegato a
quell'action e a quel piano.

## Review dei claim persona da un report fonte

Tutti gli artifact di una review reale devono restare nella destinazione
operativa persistente `P:\Comune\Me.Mo.Ri.a\risultati\runs\<run-id>\`.
Usare sottodirectory della stessa run per claim, queue/manifest, receipt e
CandidateProfileUpdate; creare un nuovo run ID senza sovrascrivere run esistenti.
Le cartelle `.tmp`, `.tmp-tests` e quelle nel workspace sono riservate a fixture
sintetiche e smoke test. Se la destinazione persistente non è disponibile,
fermarsi e segnalare il blocco: non usare cartelle temporanee come destinazione
iniziale. Comunicare il path e il comando CLI successivo.

Per una ricerca gia' eseguita e autorizzata, selezionare un solo profilo dal
report dei connettori. La CLI genera i claim candidati senza chiedere allo
storico di preparare JSON e senza avviare altre ricerche:

```text
memoria review claims-build --report-json <report-fonte.json> --profile-id <profile-id> --source-document-id <documento-persona-o-luogo> --output-dir <claims-dir>
memoria review claims-preview --claims-json <claims-dir/candidate_evidence_claims.json> --source-documents-db <database-operativo/evidence.sqlite> --output-dir <review-dir>
memoria review claims-wizard --manifest <review-dir/candidate_claim_review_manifest.json> --output <nuova-receipt.json>
memoria review claims-updates-preview --receipt <nuova-receipt.json> --profile-jsonld <profilo-esistente.jsonld> --output-dir <proposte-dir>
```

Ripetere `--source-document-id` per ogni documento che contiene un record
specifico del soggetto principale selezionato (persona o luogo). La selezione è
obbligatoria: `claims-build` include solo i claim legati agli ID indicati e
registra nel payload e nel manifest gli ID selezionati e i claim esclusi. Non
selezionare titoli di portali, pagine di ricerca o altri documenti generici come
se fossero record del soggetto. Verificare che titolo, URL e tipo di documento
identifichino il record principale prima di passare gli ID; la presenza del
SourceDocument nel catalogo viene verificata al passo `claims-preview`.

### Ambito dei claim e nomi propri

Un `EvidenceClaim` di questo flusso deve esprimere un'affermazione riferibile al
soggetto principale selezionato (persona o luogo), con proprietà e valore
supportati dal documento identificato. Non creare claim generici su portali,
pagine di ricerca, intestazioni, provenienza o metadati che non descrivono quel
soggetto. La provenienza resta associata al claim come fonte, non diventa da sola
un fatto del soggetto. Se un elemento estratto non ha un soggetto principale
chiaro, escluderlo dalla coda dei claim invece di chiedere allo storico di
classificarlo come claim.

Per i nominativi, conserva la forma letterale della fonte e non assegnare
automaticamente le parole ai campi nome, secondo nome o cognome solo in base
all'ordine tipografico. Punteggiatura e convenzioni della fonte possono essere
indizi, ma non bastano da sole a risolvere un'identità ambigua. Mantieni la
segmentazione come candidata finché una fonte o un'altra evidenza la supporta;
presenta la discrepanza allo storico prima di proporre un aggiornamento del
profilo.

Usare il database operativo gia' configurato, non un catalogo scratch per una
review reale. `claims-build` conserva i riferimenti del report e non consulta il
catalogo; `claims-preview` richiede il database SQLite esistente e verifica in
sola lettura l'esistenza di ogni `source_document_id`. Queue e manifest legano
path, digest del database e dell'eventuale WAL e l'elenco esatto degli ID
risolti. La presenza nel catalogo non verifica il contenuto storico o
l'identita' della persona.

Il wizard mostra evidenza, fonte e un claim per volta, raccoglie reviewer,
decisione e nota e registra il timestamp al momento della scelta. Quando serve
l'intervento dello storico, presentare una sola domanda per messaggio e
attendere la risposta prima di proporre la successiva. Ogni domanda deve
riportare il candidato/claim in esame, la fonte e il dato che supportano la
proposta, le eventuali discrepanze o incertezze e l'effetto pratico della
decisione. Quando le domande sono già note, dichiarare il totale e quante ne
restano, aggiornando il conteggio dopo ogni risposta; se il totale dipende dalle
risposte, dichiararlo. Non accorpare scelte distinte, non interpretare il
silenzio come consenso e, se la domanda non è visibile nell'interfaccia,
riproporla nel messaggio successivo con contesto e avanzamento.

Spiegare i termini di dominio prima di chiedere una scelta; ad esempio, chiarire
che `claim generico` indica un'affermazione non riferibile alla persona o al
luogo principale. Una risposta esplicita come «accetto come candidata» o
«confermo» è la decisione sull'elemento attualmente presentato: registrarla e
passare alla domanda successiva senza chiedere se fosse davvero una decisione.
`accept_candidate` lascia il dato candidato e non lo rende un fatto verificato.
Se la risposta non ha un riferimento univoco, chiedere una sola chiarificazione.
Le decisioni espresse in chat non autorizzano a fabbricare o retrodatare una
receipt; conserva la decisione nel contesto della sessione e usa il wizard per
una receipt con il suo timestamp effettivo, senza ripetere decisioni già chiare.

`q` o mancata conferma finale non scrivono una receipt; il reviewer dichiarato
non viene autenticato. Non trasformare decisioni raccolte in chat in una
receipt retrodatata e non ricostruire tempi mancanti: il wizard registra le
decisioni solo con il timestamp effettivo della review.

Il wizard ricontrolla input e catalogo prima e dopo la raccolta delle decisioni;
la receipt conserva gli stessi riferimenti. Anche `claims-updates-preview`
ricontrolla il binding. Se il database o il WAL cambiano, rigenerare la preview
e riprendere la review sui nuovi artifact: le receipt precedenti rimangono
auditabili, ma non autorizzano il consumer. I manifest precedenti senza
catalogo (v1.0) non sono accettati dalla review operativa v1.1.

Solo `accept_candidate` alimenta le proposte `pending`; gli altri esiti non
producono aggiornamenti. I conflitti restano da discutere. Gli artifact nelle
directory indicate dalla CLI conservano provenance e hash; non applicano patch,
non creano `verified_facts` e non modificano il profilo canonico.

## Raccolta delle misure T49

Le metriche T49 si alimentano con artifact di una ricerca e di una review
effettivamente avvenute. Registrare gli ID e i timestamp durante il lavoro;
non ricostruire tempi, token o costi a posteriori. Conservare run e dati reali
fuori da Git.

Per estrarre testo da documenti già acquisiti, il launcher accetta sidecar
JSON o YAML selezionati uno per volta e scrive `ProcessedDocumentText` in una
directory di output. I sidecar online `*.document.yaml` possono contenere
`file` e metadata annidati; quelli JSON locali possono usare `raw_file` relativo
alla radice esplicita:

```text
memoria documents text-extract --metadata-json <document.metadata.json> --raw-root <raw-root> --output-dir <text-output>
```

Ripetere `--metadata-json` solo per i documenti scelti. Nonostante il nome
dell'opzione, sono validi anche i sidecar YAML online. Il comando non esegue
OCR né scansioni ricorsive; mantiene `source_document_id`, URL e
`review_status`, e calcola il digest del testo estratto. I dati reali e gli
output di run restano fuori da Git.

Per comporre i candidati dalle sole estrazioni selezionate, passa uno o più
`ProcessedDocumentText` al launcher. Il comando produce chunk, segmenti deboli,
menzioni e un manifest con digest degli input/output; le menzioni restano
`unreviewed` e non abilitano claim:

```text
memoria documents mention-preview --text-json <document.text.json> --output-dir <preview-dir>
```

Ripetere `--text-json` solo per documenti che si vogliono includere. La directory
di output deve essere nuova o vuota.

Prima genera le action candidate dal directory di `DocumentMentionCandidate`
usando il launcher installato. Il comando produce una preview JSON/Markdown e
digest SHA-256 per ogni file di menzioni; non crea fatti o patch ai profili:

```text
memoria feedback actions --mentions-dir <mentions-dir> --output-dir <actions-dir> --output-json <actions.json> --output-md <actions.md>
```

Quando il file di menzioni contiene più persone, si può restringere la preview
a ID `mention_id` espliciti e dichiarare il profilo come collegamento candidato:

```text
memoria feedback actions --mentions-dir <mentions-dir> --profile-id <person-profile-id> --person-mention-id <mention-id> --output-json <actions.json> --output-md <actions.md>
```

Il comando rifiuta ID persona mancanti e lega comunque `mentions_sha256`
all'intero file consumato. Il profilo resta un collegamento candidato
`unreviewed`: va verificato nella review umana prima di pianificare una ricerca.
Le menzioni deterministiche possono contenere falsi positivi; anche una
menzione persona con `BUONA` non dimostra che la persona citata sia il profilo
canonico indicato. Conservare ID e contesto della menzione e lasciare la
risoluzione d'identità allo storico.

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
