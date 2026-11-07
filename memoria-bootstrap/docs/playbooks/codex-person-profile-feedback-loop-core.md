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

1. Parti da un `FeedbackSearchPlanSet` e registra ogni tentativo con il suo
   `feedback_search_plan_id`, `action_id`, `source_id`, strategia, `run_id`,
   query ed `executed_at` timezone-aware. `feedback_loop_outcome.py` produce
   un `FeedbackLoopOutcome` per l'esito reale (`candidate_results`,
   `no_results`, `needs_manual_review` o `blocked_or_dynamic`). Un risultato
   candidato non e' un documento acquisito; associa `result_source_document_ids`
   solo a documenti identificabili. `no_results` non prova assenza storica.
2. Per attribuzione claim, passa al valutatore un `CandidateEvidenceClaimSet`
   reale con ID univoco, `source_id` e `source_document_id`. La metrica misura
   la presenza di questi riferimenti, non verifica che il documento esista nel
   catalogo.
3. Durante il triage, compila `reviewer`, `review_started_at` e `reviewed_at`
   in ISO 8601 con timezone. L'evaluation calcola la latenza solo quando la
   decisione e' legata senza ambiguita' a un singolo outcome. Timestamp assenti
   o non validi restano `unavailable`.
4. Se la riconciliazione incontra un conflitto reale, registra in
   `FeedbackLoopEvaluationMeasurements.conflicts` `conflict_id`, `outcome_id`,
   `before_claim_ids` e `after_claim_ids`. Non creare record di conflitto per
   simulare una misura.
5. Per l'uso sessione registra in `sessions` `session_id`, `run_id` e i valori
   realmente disponibili: `input_tokens`, `cached_input_tokens`,
   `output_tokens`, `cost_usd`. Per confrontare baseline e candidate aggiungi
   `comparison_group_id`, `task_contract_sha256`, `quality_gate_status`,
   `model_id` e `comparison_role`. Il gruppo richiede un solo baseline e almeno
   un candidate, fingerprint del task identico e quality gate `passed`; i delta
   descrivono osservazioni e non dimostrano risparmi o causalita'.

L'evaluation accetta questi artifact con:

```text
python -m caduti_fonti_report.document_analysis.feedback_loop_evaluation --feedback-plan-json <plan.json> --outcome-json <outcome.json> --candidate-claims-json <claims.json> --measurements-json <measurements.json> --review-summary-json <review-summary.json> --output-json <evaluation.json>
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
