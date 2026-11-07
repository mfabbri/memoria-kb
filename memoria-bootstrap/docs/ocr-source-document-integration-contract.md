# Contratto T45/T46: OCR revisionabile -> SourceDocument

Versione: 1.1 (T45 contratto; T46 bridge CLI implementato)

## Scopo e confini

Il `SourceDocument` identifica il documento originale acquisito da una fonte.
`OcrPageEvidence`, `DocumentStructure` e Markdown sono derivati revisionabili
che conservano il legame al documento e ai byte sorgente. La disposizione
`provisional_auto_validated` descrive soltanto l'esito operativo T42 nel suo
scope; non è revisione umana, attestazione di accuratezza o approvazione di
claim.

T46 implementa la registrazione descritta qui tramite
`documents register-ocr-source`. Il bridge registra provenienza e identità;
non esegue OCR, non estrae claim e non cambia il modello `SourceDocument`.

## Mapping del documento originale

| `SourceDocument` | Regola T46 |
| --- | --- |
| `document_id` | ID deterministico e idempotente per `(source_id, raw_uri canonico, SHA-256 dei byte originali)`. Rielaborare OCR o cambiare motore non crea una nuova identità del documento. |
| `source_id` | ID esplicito di una definizione fonte esistente; non dedurlo da titolo, percorso o OCR. |
| `title` | Titolo descrittivo della fonte, senza derivarlo dal testo riconosciuto. |
| `url` / `local_path` | URI remoto originale in `url`, oppure percorso del file originale in `local_path`; il valore deve essere preservato e non deve puntare a una derivata OCR. |
| `access_date` | Timestamp UTC della registrazione/accesso alla fonte, non data storica descritta nel documento. |
| `media_type` | Tipo del documento sorgente originale. Non sostituirlo con `text/markdown` per effetto della trascrizione. |
| `content_hash` | SHA-256 completo dei byte originali. Non è l'hash del Markdown, della struttura o del testo OCR. |
| `raw_text` | Contenuto testuale originale soltanto se presente nella fonte. Non sovrascriverlo con la trascrizione OCR. |
| `metadata` | Campi stringa `ocr_artifact_manifest_path`, `ocr_artifact_manifest_sha256`, `ocr_workflow_status`, `ocr_review_status` e flag di non-promozione (`machine_pass`, `human_verified`, `claim_extraction_allowed` impostati a `false`). |

L'URI e l'hash sorgente sono obbligatori per il ramo OCR. Per immagini locali
il percorso resta nel workspace/runtime esterno al repository. Il bridge deve
fallire chiuso se `source_document_id` non corrisponde all'identità registrata.
`source_image_hash` resta distinto da `content_hash` quando l'evidence si
riferisce a una rappresentazione pagina/raster derivata; il manifest deve
registrare la trasformazione che collega i byte sorgente ai byte immagine.

## Manifest delle derivate OCR

Il manifest, legato a `SourceDocument.metadata` tramite percorso e SHA-256,
registra una o più pagine. Ogni pagina contiene:

- `page_id` e indice/pagina sorgente;
- hash SHA-256 dell'immagine sorgente e `source_document_id`;
- riferimenti (URI/percorso e SHA-256) a `OcrPageEvidence`,
  `DocumentStructure` e Markdown derivato;
- `schema_version`, profilo struttura, motore, modello, lingua e trasformazioni
  sufficienti a identificare la specifica candidata;
- `transcription_validation_status`, `review_status` e l'eventuale riferimento
  alla decisione umana, senza appiattire gli stati a livello documento.

`DocumentStructure.source_evidence` deve concordare con pagina, hash, engine,
lingua, modello e trasformazione di `OcrPageEvidence`. Il Markdown è derivato
dalla stessa struttura; i suoi hash non sostituiscono l'hash dei byte originali.
I manifest e gli artefatti restano esterni a Git quando contengono dati reali.

## Stati e passaggio ai claim

| Evento | Stato consentito |
| --- | --- |
| Nessuna review umana conclusa | `review_status=unreviewed`; l'eventuale esito T42 resta `provisional_auto_validated` e `machine_pass=false`. |
| Revisione visuale esplicita e registrata, legata ai digest esatti | Aggiornare solo la disposizione revisionata; il workflow OCR non inventa la decisione umana. |
| Estrazione semantica successiva | Produce `CandidateEvidenceClaim` con riferimento al `SourceDocument` e agli span/regione di provenienza; resta candidato e non approvato. |
| Approvazione editoriale | Richiede la decisione umana prevista dal review store. Solo tale passaggio può creare o aggiornare un claim approvato. |

Il consumer provisional non imposta `human_verified`, non abilita
`claim_extraction_allowed`, non crea righe approvate in `evidence_claims` e non
modifica fatti o profili canonici. Un documento registrato non equivale a un
claim verificato. L'idempotenza riguarda la registrazione del medesimo documento
originale; la revisione delle derivate non deve duplicare il `SourceDocument`.

## Evidenza offline già disponibile

I test `test_ocr_candidate_assessment.py` e
`test_ocr_provisional_threshold.py` verificano che la valutazione resti
diagnostica/provisional, `machine_pass` e `human_verified` restino falsi e
`claim_extraction_allowed` resti falso. Il test
`test_document_analysis_evidence_store_import.py` distingue i record
`candidate_evidence_claim` dalle righe approvate nello store (`evidence_claims`).
Questi test sono fixture sintetiche e non attestano accuratezza OCR reale.

## Gate per T46

Prima del bridge verificare preview/apply, idempotenza sullo stesso documento,
conservazione di URI e hash sorgente, rifiuto di binding divergenti, round-trip
del manifest delle derivate e assenza di promozione da provisional a review o
claim approvati. Usare fixture offline; nessuna run OCR reale è prerequisito.

## Bridge T46 implementato

Comando:

```powershell
memoria-engine\.venv\Scripts\python.exe -m caduti_fonti_report.memoria_cli documents register-ocr-source `
  --manifest <manifest.json> --database <evidence.sqlite> `
  [--sources-registry <registry.yaml>] [--apply]
```

Senza `--apply` il comando valida e mostra il risultato previsto senza creare
database o directory di destinazione. Con `--apply` usa `SQLiteEvidenceStore`,
inserisce un solo `SourceDocument` e un `SearchRun` auditabile nella stessa
transazione e non sovrascrive righe esistenti. Un retry identico è un no-op;
un payload diverso per la stessa identità viene rifiutato. La fonte deve essere
presente nel registry (default: `memoria-sources/registry/camalanca_fonti.yaml`).

Il manifest JSON v1.0 usa `@type: OcrSourceDocumentRegistration` e contiene
`source_id`, `source_document_id`, `local_path`, `content_hash`, `title`,
`media_type`, `access_date` UTC, `workflow_status`, `review_status` e `pages`.
Ogni pagina contiene `page_id`, `source_document_id`, `source_page`, riferimenti
hash-bound `source_image`, `evidence`, `structure`, `markdown`,
`transcription_validation_status` e `review_status`. I riferimenti relativi
sono risolti dalla directory del manifest. Per raster derivati,
`source_image_transform` deve legare SHA-256 originale e SHA-256 raster con una
descrizione. L'evidence deve corrispondere a documento, pagina e immagine; la
structure viene ricostruita dall'evidence e il Markdown confrontato con il
renderer deterministico.

Lo schema può essere preso dalla fixture sintetica eseguibile in
`memoria-engine/tests/test_ocr_source_document_registration.py`; evitare di
copiare dati reali nei manifest di esempio o nel repository. T46 v1.0 accetta
solo originali locali e `review_status=unreviewed`; un aggiornamento della
review o delle derivate non è supportato. `provisional_auto_validated` può
restare in `workflow_status` e `transcription_validation_status`, ma non
abilita `machine_pass`, `human_verified` o `claim_extraction_allowed`, e non
crea claim.

Verifica offline T46: 9 test sintetici registrano preview, apply, retry,
conflitto divergente, digest/binding, coerenza structure/Markdown, no-promote e
trasformazione raster. Non attestano la correttezza di OCR reale né una review
umana.
