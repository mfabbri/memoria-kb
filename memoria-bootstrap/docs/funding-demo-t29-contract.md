# T29 Funding Demo Golden Path Contract

Data: 2026-07-13

Stato: chiuso. Contratto documentale per T30.

## Incremento

T29 - Contratto Funding Demo Golden Path.

Questo incremento e' stato eseguito in modalita' read-only/documentale. Non sono
state lanciate pipeline, OCR, ricerche live o scritture nel data root esterno.

## Caso selezionato

Caso principale:

- profilo: `person:purocielo:andreoli-dino`;
- etichetta operativa: `Andreoli Dino`;
- run candidata di review: `prova-preview-profili-5-reviewed-01-pipeline`;
- motivazione: il profilo ha documenti di famiglie diverse, decisioni storiche
  gia' accettate, verified facts preview e ProfilePatch preview collegati alla
  stessa catena di provenance.

Caso di contrasto leggero:

- profilo: `person:purocielo:balboni-william`;
- etichetta operativa: `Balboni William`;
- ruolo: mostrare che il contratto si applica a un secondo profilo senza
  allargare la demo. T30 deve restare centrato sul caso principale salvo
  necessita' di confronto.

## Documenti candidati

I documenti restano nel data root esterno e sono referenziati solo per ID.

| Ruolo | Source document ID | Famiglia | Uso demo |
|---|---|---|---|
| Fonte locale/tabellare | `legacy_csv:a4ac96061a2381b5` | seed/CSV legacy | aggancio al profilo e contesto di partenza |
| Fonte locale/documentale | `local_docx:4c2ad1d2ab937913` | documento Word locale | contesto narrativo e possibili richieste di nuove fonti |
| Fonte online/istituzionale A | `partigiani_italia:b45553cd6b1673d8` | dettaglio online strutturato | verified facts e patch preview gia' collegate ad Andreoli |
| Fonte online/istituzionale B | `partigiani_italia:b6b3c9e526723a27` | dettaglio online strutturato | alternativa/conflitto o conferma da mantenere visibile |

Per il caso di contrasto e' disponibile anche
`partigiani_italia:dadc75fad9db03ae`, usato nelle preview gia' esistenti per
`person:purocielo:balboni-william`.

## Criterio di merge multi-fonte

T30 deve dimostrare il merge su una sola scheda di lavoro, non una lista di
risultati. Il merge e' accettato se la tabella di riconciliazione mostra, per
Andreoli:

- almeno due famiglie documentali tra `legacy_csv`, `local_docx` e
  `partigiani_italia`;
- per ogni claim: `profile_id`, `claim_type`, valore proposto,
  `source_document_id`, famiglia fonte, metodo, confidence se disponibile,
  stato di review e relazione con altri claim;
- almeno un contributo complementare o divergente mantenuto visibile, ad
  esempio differenze fra dettagli online Partigiani d'Italia e contesto locale;
- almeno un claim accettato che resta collegato a decisione storica,
  verified fact preview e ProfilePatch preview.

La demo non deve cancellare alternative o conflitti. La review puo' scegliere,
lasciare incerto o chiedere fonti, ma la tabella deve conservare il contributo
di ogni documento.

## Decisione, verified fact e patch preview

Artefatti gia' osservati nella run candidata:

- `historian_review/review_decisions_summary.json`: `10` decisioni accettate,
  di cui `6` su Andreoli e `4` su Balboni;
- `historian_review/verified_facts.preview.json`: `8` facts preview, con
  source run `prova-preview-profili-5-reviewed-01-pipeline`;
- `historian_review/profile_patch.preview.json`: `2` ProfilePatch preview e
  `8` operazioni; policy
  `requires_explicit_apply_profile_patch_command`;
- esempio Andreoli: operazione preview `set` su
  `/identity/canonical_name`, proveniente da
  `partigiani_italia:b45553cd6b1673d8` e da una decisione storica accettata.

T30 deve riusare o rigenerare questi collegamenti nello stesso `run_id`
canonico. Nessuna patch deve essere applicata ai profili canonici.

## Feedback trigger candidato

Trigger consigliato:

- profilo: `person:purocielo:andreoli-dino`;
- origine: differenze e incompletezze fra fonti locali e dettagli online,
  in particolare i claim online collegati a `partigiani_italia` e il contesto
  narrativo locale;
- decisione attesa in T31: una richiesta esplicita di nuova fonte o verifica,
  non la promozione automatica di un fatto;
- fonti candidate per il piano: `storia_memoria_bo`, `partigiani_italia` e,
  solo se gia' previsto dal piano esistente, `bundesarchiv_invenio`;
- esito valido: nuovo documento/claim candidato oppure `no_results`,
  `needs_manual_review` o `blocked_or_dynamic` tracciato e reinserito nella
  memoria di ricerca del profilo.

Nota: nella run candidata esistono `856` ResearchFeedbackAction in stato
`pending`; T31 deve selezionarne una sola, ridurla e chiuderla con esito
auditabile.

## Descrittore golden run

Nome scelto per T30:

```text
<data-root>/database/memoria_mvp_demo.active.json
```

Contratto minimo:

```json
{
  "contract_version": "memoria_mvp_demo.v1",
  "created_at": "<iso-8601>",
  "updated_at": "<iso-8601>",
  "status": "ready_for_internal_demo",
  "preview_only": true,
  "publication_status": "not_publishable_without_human_review",
  "run_id": "<canonical-run-id>",
  "run_dir": "<data-root>/risultati/runs/<canonical-run-id>",
  "primary_profile_ids": ["person:purocielo:andreoli-dino"],
  "contrast_profile_ids": ["person:purocielo:balboni-william"],
  "source_document_ids": [
    "legacy_csv:a4ac96061a2381b5",
    "local_docx:4c2ad1d2ab937913",
    "partigiani_italia:b45553cd6b1673d8",
    "partigiani_italia:b6b3c9e526723a27"
  ],
  "source_families": ["legacy_csv", "local_docx", "partigiani_italia"],
  "review_session_id": "<review-session-id>",
  "consolidate_session_id": "<consolidate-session-id>",
  "artifacts": {
    "run_manifest": "<path>",
    "reconciliation_table": "<path>",
    "review_queue": "<path>",
    "review_decisions_summary": "<path>",
    "verified_facts_preview": "<path>",
    "profile_patch_preview": "<path>",
    "feedback_action": "<path>",
    "feedback_outcome": "<path>",
    "readiness_report": "<path>"
  },
  "safety": {
    "no_canonical_profile_patch_applied": true,
    "no_publication_output": true,
    "real_data_not_copied_to_git": true
  }
}
```

Il descrittore non contiene documenti reali e non sostituisce manifest, store o
sessioni. Dichiara solo quale run e quali artefatti costituiscono la demo
ufficiale.

## Artifact map T30

| Artefatto | Stato attuale | Azione T30 |
|---|---|---|
| Run review | `prova-preview-profili-5-reviewed-01-pipeline` | usarla come candidata o rigenerare run canonica unica |
| Sessione review | `database/memoria_review_session.active.json` | allineare al run canonico |
| Ledger consolidato | presente nella run candidata | ridurre/rigenerare con perimetro Andreoli + contrasto |
| Review decisions summary | presente | conservare decisioni accettate e pending rilevanti |
| Verified facts preview | presente | collegare a descrittore e claim selezionati |
| ProfilePatch preview | presente | collegare a descrittore, non applicare |
| Research feedback actions | presenti ma troppo numerose | selezionare una sola azione per T31 |
| Reconciliation table | non ancora esplicita come artefatto golden | produrre tabella claim-fonte-compatibilita |
| Readiness report | presente ma non canonico | riallineare alla run ufficiale |

## Walkthrough 7-10 minuti

1. Mostrare `memoria mvp status` e dichiarare modalita' preview-only.
2. Presentare Andreoli come caso principale e Balboni come contrasto leggero.
3. Aprire la tabella di riconciliazione: gli stessi soggetti sono collegati a
   `legacy_csv`, `local_docx` e `partigiani_italia`.
4. Evidenziare un claim accettato e la sua provenance fino a documento e
   decisione.
5. Mostrare che contributi divergenti o complementari restano visibili.
6. Mostrare `verified_facts.preview` come preview non pubblicabile.
7. Mostrare `profile_patch.preview` e la policy che impedisce il merge
   automatico.
8. Selezionare la lacuna/trigger e mostrare la ResearchFeedbackAction candidata.
9. In T31, mostrare esecuzione controllata ed esito registrato.
10. Chiudere con cosa finanziamento rende scalabile: piu' fonti e profili senza
    perdere provenance, decision trail e separazione fra preview e pubblicazione.

## Comandi read-only di verifica

```powershell
cd memoria-engine
$env:MEMORIA_DATA_ROOT = "P:\Comune\Me.Mo.Ri.a"
.\.venv\Scripts\memoria.exe mvp status
.\.venv\Scripts\memoria.exe review status
.\.venv\Scripts\memoria.exe review decisions
.\.venv\Scripts\memoria.exe review work
.\.venv\Scripts\memoria.exe consolidate status
```

## Gap tecnici puntuali

T30:

- creare o rigenerare una sola run canonica centrata su Andreoli;
- creare `database/memoria_mvp_demo.active.json`;
- produrre la tabella di riconciliazione multi-fonte come artefatto esplicito;
- allineare sessioni review/consolidate alla stessa run;
- ridurre la review queue al perimetro demo.

T31:

- selezionare una sola ResearchFeedbackAction;
- registrare decisione `request_more_sources` o equivalente;
- eseguire una ricerca controllata o sessione manuale tracciata;
- registrare esito e collegamento alla memoria di ricerca.

T32:

- fare in modo che `memoria mvp status` riconosca il descrittore demo;
- allineare naming e guide alla run canonica;
- verificare che il repository distribuibile non contenga dati reali;
- eseguire prova generale offline/controllata.

## Evidenza read-only T29

Ricognizioni eseguite:

- `memoria mvp status`: profili `57/57`, review attiva, decisioni `114`,
  decisioni storiche sostanziali `10`;
- `memoria review status`: run attiva
  `prova-preview-profili-5-reviewed-01-pipeline`;
- `memoria review decisions`: `10` decisioni `confirm/accepted`;
- `memoria consolidate status`: sessione consolidate attiva, ledger presente;
- lettura non ricorsiva degli artefatti della run candidata.

Stop condition raggiunta: T30 puo' partire senza nuova decisione di direzione.
