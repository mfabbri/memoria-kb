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
