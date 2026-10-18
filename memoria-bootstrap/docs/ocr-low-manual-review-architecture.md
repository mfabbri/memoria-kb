# Decisione: assessment OCR legato alla candidata

Data: 2026-10-13
Stato: selezionata; primo gate diagnostico implementato e testato, calibrazione ancora assente.

## Decisione

Mantenere OCR PP-OCRv5/Tesseract e la ricostruzione deterministica esistenti.
Inserire dopo l'esportazione della `DocumentStructure` un assessment che leghi
per digest la struttura candidata, il Markdown generato, l'`OcrPageEvidence` e
la review lessicale. Il primo increment controlla coerenza e provenienza e
raggruppa gli alert lessicali per blocco. Non corregge il testo e non richiede
un nuovo modello.

L'assessment ora include la copertura delle regioni `OcrPageEvidence`: confronta
le regioni presenti con l'unione dei `source_region_ids` della candidata. Una
regione non rappresentata blocca il routing. Questa misura dice soltanto se la
candidata ha perso regioni gia' riconosciute dall'OCR; non misura copertura
dell'immagine e non rileva omissioni condivise dai motori OCR. Zero regioni
produce un rapporto non definito (`null`), non copertura completa.

Il controllo d'ownership richiede che ogni regione OCR compaia una sola volta
nella struttura candidata: duplicati nello stesso blocco o riferimenti condivisi
fra blocchi bloccano l'assessment. Anche un'evidence senza regioni blocca il
controllo, invece di produrre una candidata apparentemente processabile.
L'assessment espone sempre `review_preparation_status: incomplete`,
`human_review_request_allowed: false` e `visual_coverage_status: not_assessed`:
la coerenza degli artefatti OCR non certifica il confronto con i pixel e non
autorizza da sola una richiesta di review umana. Per arrivare a un gate positivo
servono contratti CLI verificabili per osservazioni visuali, struttura tipizzata
e disposition degli alert.

### Ledger delle osservazioni visuali (v1)

`documents ocr-visual-review-audit --ledger ledger.json --image page.tiff
--evidence evidence.json --structure structure.json` audita in sola lettura
un `OcrVisualReviewLedger` con `schema_version: "1.0"`. Stampa il rapporto JSON;
non espone `--apply` e non scrive artefatti. Un audit bloccato restituisce exit 1.

Il ledger richiede `page_id`, `source_image_hash` (SHA-256 esadecimale senza
prefisso), `source_page` identico all'evidence, `frame_index` esplicito e
`source_dimensions: {width, height}`. `source_evidence_digest` e
`source_structure_digest` usano `sha256:<hex>` e vincolano i byte effettivi dei
due JSON. Il TIFF viene aperto sul frame dichiarato, verificando hash e
dimensioni rispetto a `source_page.original_page`; anche l'evidence deve
dichiarare `source_page.frame_index`. Sono supportati soltanto il frame raw
full-page con transform `original` e le trasformazioni dichiarate `byte_copy`;
crop, resize, rotazioni o frame non dimostrabili bloccano l'audit.

`review_tiles` dichiara oggetti `{tile_id, bbox}`; bbox e geometrie sono rettangoli
`[x0, y0, x1, y1]` con coordinate intere nel frame originale. Ogni rettangolo
deve essere interno all'immagine e avere area positiva. L'assenza di overlap
fra tile e l'uguaglianza fra somma delle aree e area del frame provano la
partizione completa, inclusi margini ed eventuali aree senza testo.

`observations` contiene record con `observation_id`, `unit_type` (`tile`,
`block`, `region`), `unit_id`, `bbox`, `outcome` (`readable`, `illegible`,
`no_text`) e `text` non vuoto, anche per dichiarare illeggibilita' o assenza di
testo. Ogni tile, blocco candidato e regione evidence richiede esattamente un
record. I record di blocco/region richiedono `candidate_text` identico alla
candidata/evidence; quelli di blocco richiedono anche `source_region_ids`
identici. Le bbox dei blocchi corrispondono all'inviluppo delle regioni collegate;
ogni regione deve avere esattamente un blocco proprietario.

Ogni record richiede `crop_artifact: {path, digest}` con digest `sha256:<hex>`;
i path relativi si risolvono dalla directory del ledger, i byte devono esistere
e corrispondere al digest, e i pixel decodificati devono coincidere esattamente
con il bbox dichiarato ritagliato dal frame TIFF originale selezionato. `observer` richiede stringhe non vuote `observer_id`,
`model`, `configuration` (identificativo della configurazione) e `observed_at`
ISO 8601 con timezone. Questi metadati documentano una dichiarazione: non
autenticano l'osservatore e non attestano la correttezza della lettura.
Un booleano isolato non costituisce un'osservazione.

Input mancanti/obsoleti, JSON con chiavi duplicate, unita' duplicate o inattese,
record mancanti, bbox invalide e provenance/crop incompleti bloccano l'audit.
Solo in assenza di problemi `visual_coverage_status` diventa
`complete_for_declared_units`: significa integrita' dei record e completezza
geometrica dichiarata, non correttezza delle letture o assenza di omissioni
semantiche. `semantic_accuracy_status: not_attested`, `preview_only: true`,
`human_review_request_allowed: false`, `machine_pass: false` e
`gold_promotion_allowed: false` restano invariati. Il comando autonomo resta un
gate diagnostico; `documents ocr-review` riesegue questo audit sul TIFF prima
di usare il rapporto negli stadi successivi.

### Layout tipizzato di righe e celle (v1)

`documents ocr-layout-audit --layout layout.json --evidence evidence.json
--visual-audit visual-audit.json` controlla un `OcrPageLayout` con
`schema_version: "1.0"`. Il comando stampa un `OcrPageLayoutAudit` JSON in
preview senza scrivere file; un audit bloccato restituisce exit 1.

Il layout dichiara `page_id`, `source_image_hash` e `source_page` identici
all'evidence. `source_evidence_digest` e `source_visual_audit_digest` sono
`sha256:<hex>` dei byte effettivi dei due JSON. Il rapporto visuale deve essere
un `OcrVisualReviewLedgerAudit` v1 senza issue, `diagnostic_only` e
`complete_for_declared_units`; i digest `inputs.evidence` e `inputs.image`
devono coincidere con l'evidence e il suo hash immagine. Si verifica il rapporto
fornito: questo comando non riesegue le osservazioni visuali o l'audit dei crop.

`columns` contiene `{column_id, column_index}` e `rows` contiene
`{row_id, row_index, bbox, cells}`. ID univoci, indici interi da zero, contigui
e ordinati sono obbligatori. Ogni cella dichiara `{cell_id, column_index, bbox,
source_region_ids, joiner, text}`. Gli indici colonna di ogni riga sono ordinati
e contigui da zero e non superano le colonne dichiarate; sono ammesse righe
con meno celle. Righe e celle vuote sono rifiutate. Le bbox intere positive nel
frame originale contengono le regioni collegate; la bbox della riga contiene
anche quelle delle sue celle.

`reading_order` e' una permutazione esplicita di tutti i `cell_id`, senza
duplicati o riferimenti sconosciuti. Non viene inferito un ordine dai bbox.
`source_region_ids` e' una lista ordinata non vuota; `text` deve essere uguale
alla concatenazione dei testi OCR raw di quelle regioni, usando il `joiner`
esplicito ammesso (`""`, `" "` oppure `"\n"`), senza normalizzazione o correzioni.
`exclusions` e' una lista esplicita di `{region_id, reason}` con motivo non
vuoto per ogni regione fuori dalle celle. Ogni regione evidence deve comparire
esattamente una volta fra celle ed esclusioni. Regioni mancanti, condivise,
duplicate o sconosciute bloccano l'audit.

Il rapporto calcola conteggi di righe, colonne, celle, regioni evidence, link
nelle celle ed esclusioni. `structural_consistency_status` completo indica
soltanto coerenza dei dati dichiarati: non certifica che celle, associazioni o
ordine siano semanticamente corretti. `semantic_accuracy_status: not_attested`,
`human_review_request_allowed: false`, `machine_pass: false`,
`human_verified: false` e `gold_promotion_allowed: false` restano obbligatori.
Questo audit autonomo non autorizza la richiesta umana; l'orchestratore
`documents ocr-review` riapplica il controllo al report visuale ricalcolato.

### Disposition degli alert lessicali (v1)

`documents ocr-alert-dispositions-audit --structure structure.json
--lexicon-review lexicon-review.json --visual-audit visual-audit.json
--ledger visual-ledger.json --dispositions dispositions.json` confronta un
`OcrLexicalDispositionLedger` con la candidata, gli alert `not_found`, il
report dell'audit visuale e il ledger che lo ha prodotto. Il sidecar vincola
per SHA-256 struttura, review lessicale e audit visuale. Ogni alert e'
identificato da `page_id`, `block_id`, offset `[start, end)` e testo grezzo;
occorrenze ripetute della stessa parola restano decisioni distinte.

Ogni disposition richiede un motivo non vuoto e l'ID dell'unica osservazione
visuale leggibile del blocco. Gli esiti ammessi sono
`visually_confirmed_candidate` (il testo osservato allo stesso offset coincide
con il token candidato), `visual_correction_proposed` (il testo osservato
all'offset coincide con `replacement_text`, che deve differire dal candidato)
e `unresolved`. Alert mancanti o duplicati, offset che non individuano il token,
osservazioni non corrispondenti e hash obsoleti bloccano l'audit. Le proposte
v1 richiedono che la lettura occupi lo stesso intervallo del token nel testo
osservato; non tentano allineamenti fuzzy quando la lunghezza cambia. Non
vengono applicate al `DocumentStructure` e richiedono in seguito di rigenerare
tutti gli artefatti legati alla candidata corretta.

Il rapporto raggruppa le sole incertezze residue per blocco e conta un'azione
per gruppo. Anche un sidecar completo resta `diagnostic_only`: una disposizione
è una registrazione dell'analisi, non una prova indipendente della lettura.
`human_review_request_allowed`, `machine_pass`, `human_verified` e promozione
gold restano disabilitati per questo audit. Solo l'orchestratore può autorizzare
la preparazione di una richiesta umana dopo aver rieseguito tutti i gate.

### Orchestratore page-level `documents ocr-review`

`documents ocr-review --image page.tiff --evidence evidence.json --structure
structure.json --markdown page.md --lexicon-review lexicon-review.json --layout
layout.json --ledger visual-ledger.json --dispositions dispositions.json` esegue
in sequenza i controlli page-level senza rilanciare l'OCR e senza scrivere sugli
artefatti. Ricalcola il candidate assessment; ricalcola l'audit visuale dal TIFF,
frame, evidence, struttura e crop; poi usa quel report appena ricalcolato per
verificare layout e disposition. I sidecar richiesti devono legarsi agli stessi
byte tramite digest. Il report include path e SHA-256 degli otto input e un gate
finale verifica che non siano cambiati durante il run. Se uno stadio fallisce,
i successivi non vengono eseguiti e la richiesta umana resta disabilitata.

Gli input lexical review, layout, ledger e disposition devono essere preparati
prima: il comando verifica che siano completi e coerenti, non inventa
osservazioni visuali o letture lessicali. `documents ocr-review-scaffold` riduce
la preparazione ripetitiva di questi input senza sostituire tali osservazioni.
Le fasi sono visibili in `stages` e
lo stato finale è uno tra `blocked`, `candidate_ready`, `needs_review` e
`correction_required`. `needs_review` produce una coda deduplicata per blocco o
unità visuale e consente di preparare la richiesta soltanto quando tutti i gate
passano e non ci sono correzioni proposte. `correction_required` richiede di
applicare la correzione alla candidata e rigenerare gli artefatti dipendenti;
la coda della candidata obsoleta non viene esposta.

Per creare `OcrPageLayout` e `OcrLexicalDispositionLedger`, usare la stessa
grafia normalizzata dei path passati a `ocr-review` quando si genera l'audit
visuale: il report visuale include tali path e i sidecar ne fissano il digest.

### Preparazione assistita `documents ocr-review-scaffold`

`documents ocr-review-scaffold --image page.tiff --evidence evidence.json
--structure <page>.structure.json --markdown page.md --lexicon lexicon.json
--output-dir review-scaffold` esegue una preview senza scrivere. `--apply`
scrive atomicamente solo in una directory nuova sotto il parent già esistente.
Il JSON struttura e il Markdown possono essere generati con `documents
structure --apply`: per ogni pagina il comando salva ora entrambi gli artefatti
derivati, mantenendo separata l'evidence OCR grezza.
Il comando genera la review lessicale tramite il builder esistente, tile che
coprono il frame TIFF e crop PNG per tile/blocco/regione con digest, oltre a
template per ledger visuale, layout e disposition. Il manifest contiene gli hash
degli input e i campi da completare.

Tutti i template portano `template_status: incomplete` e i rispettivi audit li
bloccano. Il comando non deduce testo letto, outcome, identità dell'osservatore,
colonne, ordine di lettura, motivazioni o disposition. Questi campi vanno
compilati esplicitamente; poi `documents ocr-review` riesegue l'intera catena.
Lo scaffold accelera la preparazione, ma non conclude la verifica OCR e non
abilita auto-validazione o richiesta di review.

Una candidata `candidate_ready` non equivale ad accuratezza certificata: indica
solo che non sono stati dichiarati residui da sottoporre a review. In ogni esito
`machine_pass`, `auto_validation_enabled`, verifica umana, promozione gold ed
estrazione claim restano false. La soglia pilota del 5% non viene attivata.

Il Markdown confrontato deve essere esattamente quello prodotto dal renderer
strutturato. Un Markdown modificato a mano rende l'assessment `blocked` finche'
la modifica non viene riportata nella candidata e i controlli non vengono
rigenerati. Link a regioni inesistenti, identita' dell'evidence discordanti e
review lessicali mancanti o con digest obsoleto bloccano il routing.

## Semantica dei tre esiti

- `processability_status`: `diagnostic_only` se i controlli passano;
  `blocked` se manca un input o la candidata non e' coerente.
- `routing_status`: sempre `not_calibrated` in questo incremento. La futura
  policy puo' produrre `machine_pass`, `needs_review` o `blocked` solo dopo la
  calibrazione prevista.
- `human_review_status`: gruppi lessicali restano `pending_classification`.
  `manual_action_count` resta `null`: piu' alert dello stesso blocco non sono
  automaticamente piu' decisioni umane e un alert non e' di per se' un dubbio.

`machine_pass` non e' `human_verified`, non crea reference gold e non autorizza
estrazione di claim o pubblicazione. Il campo legacy `needs_human_review` nella
review lessicale e' conservato per compatibilita': l'assessment lo considera
segnale diagnostico e non lo converte in un'azione. Il chiamante deve usare gli
esiti dell'assessment per il routing. L'assessment resta legato agli hash degli
input; ogni modifica richiede rigenerazione.

## Percorso verso intervento quasi nullo

1. Identificare originale, trasformazioni, evidence OCR e candidata esatta.
2. Ricostruire la struttura dai blocchi/regioni e generare Markdown in modo
   deterministico; `documents structure --apply` salva sia il JSON
   `DocumentStructure` sia il Markdown derivato.
3. Confrontare Markdown, link regione, identita' evidence e digest della review
   lessicale; usare lessico e glossario locali come diagnostica, mai come prova
   che una parola sia stampata correttamente.
4. Raggruppare alert per blocco/cella decisionale; aggregare piu' regioni che
   appartengono alla stessa voce. Preservare ogni occorrenza e provenance.
5. In seguito provare letture OCR/VLM indipendenti o guidate distinguendole,
   misurare ciascun modello e includere controlli visuali di copertura. L'accordo
   tra motori e' un segnale da calibrare, non una prova indipendente se gli
   errori sono correlati.
6. Dividere i dati per lingua, layout e degrado in sviluppo, calibrazione e
   holdout; tenere pagine/template correlati nello stesso gruppo. Definire prima
   gli errori critici e il budget di rischio. Attivare auto-pass solo per gli
   strati in cui il limite superiore dell'incertezza sul tasso di pagine errate
   passate automaticamente rispetta quel budget. Le quattro reference T41
   attuali non consentono di fissare soglie o percentuali.
7. Mantenere audit casuali anche sulle pagine auto-pass; un cambio di modello,
   pesi, prompt, layout o risorse lessicali richiede rivalutare la policy.

Misurare CER/WER e omissioni/aggiunte sulla candidata, numeri e sigle, ordine e
copertura visuale/strutturale, errori sfuggiti al routing, quota di pagine
passate, gruppi manuali per pagina, tempo umano, retry e latenza. Una gold
umana resta distinta dall'auto-pass.

## Comparatore regionale delle letture OCR

`compare_ocr_page_evidence(left=..., right=...)` in
`ocr_evidence_comparison.py` confronta due `OcrPageEvidence` solo quando pagina,
hash dell'originale, `source_page`/crop, lingua, `transform_id` e
`image_transform` coincidono; engine o modello devono distinguere le letture.
Le geometrie `bbox` o `polygon` sono confrontate nel frame dichiarato, senza
conversioni o soglia di overlap. Componenti geometriche uno-a-uno sono
classificate come accordo/disaccordo testuale (uguaglianza esatta ed equivalenza
NFKC/casefold/spazi); split, merge e sovrapposizioni multiple restano ambigui.
Le regioni senza overlap sono elencate come non abbinate.

Il risultato e' `diagnostic_only`: conserva i testi e gli ID di entrambe le
letture, non corregge OCR e non modifica il routing. Un overlap non certifica la
correttezza; engine/modello distinti non provano indipendenza statistica. Il
comparatore non vede i pixel, non verifica copertura visiva e non rileva aree
omesse da entrambi i motori. L'adapter Tesseract collegato sotto converte solo
run nuovi con provenance e frame full-page/raw verificati.

Il comando `memoria documents ocr-evidence-compare --left A.json --right B.json
--output comparison.json` espone questo confronto nel flusso CLI. La preview
non scrive file; `--apply` crea il report solo se la destinazione non esiste.
Gli hash SHA-256 dei byte di entrambe le evidence sono aggiunti al report per
legare il risultato agli input effettivi. Errori d'identita', frame o geometria
terminano il comando senza report. L'output resta diagnostic-only e mantiene
`machine_pass=false`, `auto_validation_enabled=false` e
`semantic_accuracy_status=not_attested`; i disaccordi servono a ordinare
un'eventuale verifica, non sono letture corrette. Il comando non invoca VLM,
non crea osservazioni visuali e non sostituisce `documents ocr-review`.

Le nuove registrazioni Tesseract persistono `ocr_run_provenance` versione 1.0:
SHA-256 dell'originale prima/dopo l'OCR, hash e tipo dell'input selezionato,
probe dimensioni/frame, pagine e dimensioni TSV, configurazione, tentativi e
preprocessing dichiarato. Una variazione dei byte sorgente o dell'input durante
il run annulla la registrazione. Il flag `adapter_ready` resta falso se il probe
non e' disponibile, il documento ha piu' frame, il mapping TSV/dimensioni non
corrisponde o la trasformazione geometrica e' ignota.

`adapt_tesseract_page_evidence` converte una nuova `ProcessedDocumentText` solo
se source hash e input originale coincidono con l'ancora della primary evidence,
il run e' single-frame, lingua e TSV corrispondono e il frame e' full-page/raw.
Al momento rifiuta input preprocessati e crop. Mantiene ID TSV, confidence e
provenance del run; non corregge letture, non valuta l'accuratezza e non abilita
`machine_pass`. Gli output storici non vengono reinterpretati. La verifica
visuale indipendente della copertura resta necessaria per scoprire omissioni
comuni ai motori.

### Prova fresca 00598

Il run Tesseract nuovo sulla pagina verificata `T314-1275-00598` ha superato il
gate confidence ed e' stato adattato con tutti i controlli d'identita' passati.
Contro 54 regioni PP-OCRv5 e 46 righe Tesseract il comparatore ha trovato 3
accordi uno-a-uno, 5 disaccordi e 6 componenti ambigue; 46 regioni PP-OCRv5 e
38 righe Tesseract non hanno overlap diretto. Questi non-abbinati non sono una
stima di omissioni visive: i due motori segmentano in modo diverso.

Sulla stessa reference, Tesseract misura CER `0.134582`, WER `0.288973` e
copertura token `0.870722`; PP-OCRv5 misura CER `0.004681`, WER `0.011407` e
copertura `0.996198`. Quindi il gate confidence ha accettato un output con
WER vicino al 29%: il suo stato `accepted` non puo' essere usato da solo per
decidere l'auto-pass. Metriche strutturali, copertura visiva e soglia di rischio
restano da calibrare; questo risultato non produce `machine_pass`. Run config:
Tesseract `5.5.3.20260724`, OEM 1/PSM 6; SHA-256 di `deu.traineddata`
`19d219bbb6672c869d20a9636c6816a81eb9a71796cb93ebe0cb1530e2cdb22d`.

## Alternative scartate per il percorso canonico

- VLM che genera direttamente Markdown: resta comparatore sperimentale, perche'
  perde ancoraggio regionale e rende piu' difficile localizzare omissioni.
- Maggioranza tra OCR e VLM: non risolve errori correlati; l'accordo va misurato.
- Correzioni automatiche da dizionario: possono normalizzare nomi e sigle
  storiche in modo errato.
- Nuovo stack documentale obbligatorio: non giustificato dai pilot disponibili;
  si puo' confrontare su benchmark stratificati.
- Generalizzare la prova LLaVA: i risultati valgono per il modello e la
  configurazione misurati. GLM-OCR, Qwen3-VL e Gemma3 richiedono prove comparabili
  nel runtime Ollama WSL documentato.

### Valutazione CLI di crop VLM

`documents vlm-crop-evaluate` e' un comparatore live locale, non un pass OCR.
Accetta una coorte `OcrVlmCropEvaluationCohort` v1.0 conservata fuori dal
repository, con `cohort_role=development`; il CLI rifiuta esplicitamente
coorti `holdout`. Ogni caso lega `source_document_id`, `page_id`, immagine sorgente e
SHA-256, frame, bbox, variante, candidato OCR e reference text a un file
`OcrPageReference` con hash, `origin=human_verified` e `review_status=verified`.
Il `reference_id` deve coincidere con quello nel file; il testo target deve
comparire nella trascrizione verificata della pagina.
Il comando verifica identita', hash, frame e geometria prima di contattare
Ollama; la reference text serve al confronto e non entra nel prompt. I crop PNG
sono derivati in memoria dal frame e bbox dichiarati.

Su Windows il trasporto esegue `curl` dentro WSL, senza fallback a Ollama
Windows; versione e tag del modello sono verificati prima delle inferenze. La
richiesta usa temperatura 0 e schema con il solo campo `text`. Il report lega
coorte, crop, reference, digest modello, prompt, output e latenza, e misura exact
match, match normalizzato e coverage soltanto sulla coorte dichiarata. I risultati
sono `diagnostic`, con `machine_pass=false`, `auto_validation_enabled=false`,
`semantic_accuracy_status=not_attested` e `promotion_status=unreviewed`.

La valutazione live va invocata esplicitamente, anche in modalita' preview; solo
il salvataggio del report richiede `--apply`. Manifest, immagini, reference e
report reali restano nel runtime esterno. Il singolo crop del pilot non determina
integrazione, affidabilita' generale o attivazione del target 5%.

Il comando richiede `--manifest`, `--model` e `--output`; usa una coorte esterna
composta esclusivamente da casi adjudicati. La preview chiama comunque il
runtime e stampa il rapporto; `--apply` crea il JSON solo se il percorso non
esiste. I test CLI usano immagini sintetiche e un trasporto iniettato, mai la
coorte archivistica reale.

Esempio di forma del caso (hash abbreviati solo per leggibilita'):

```json
{
  "@type": "OcrVlmCropEvaluationCohort",
  "schema_version": "1.0",
  "cohort_id": "pilot-curated-v1",
  "cohort_role": "development",
  "cases": [{
    "case_id": "case-001",
    "source_document_id": "document-id",
    "page_id": "page-id",
    "source_image": "images/page.tif",
    "source_image_sha256": "<sha256-lowercase-64-hex>",
    "frame_index": 0,
    "source_bbox": [100, 200, 500, 280],
    "variant_id": "raw",
    "candidate_ocr": "uncertain candidate",
    "reference_text": "human-verified text",
    "reference_status": "verified",
    "reference_id": "reference-id",
    "reference_file": "references/page.json",
    "reference_sha256": "<sha256-lowercase-64-hex>",
    "scale_factor": 2
  }]
}
```

Con `cohort.json` e i file sorgente nel runtime esterno, l'invocazione e':

```powershell
memoria documents vlm-crop-evaluate --manifest cohort.json --model qwen3-vl:4b `
  --output qwen3-vl-4b-report.json
```

## Primo micro-incremento

Implementato `documents candidate-assessment`: preview predefinita, `--apply`
idempotente, nessun auto-pass. I test mirati verificano identity/hash,
coerenza del Markdown, region links, alert raggruppati, stato di calibrazione e
scrittura idempotente. Non ricostruisce il Markdown libero o la trascrizione
esterna esistente di `00312`.

File principali: `memoria-engine/code/caduti_fonti_report/document_analysis/ocr_candidate_assessment.py`,
`memoria-engine/tests/test_ocr_candidate_assessment.py` e il gruppo CLI in
`memoria-engine/code/caduti_fonti_report/memoria_cli.py`.

## Passi successivi candidati

1. Pilot controllato del runner completato su `T314-1275-00598`: un caso
   diagnostico, zero errori, 46 regioni e input invariati; nessuna scrittura sui
   gold.
2. Aggiungere un controllo visuale indipendente di copertura delle aree stampate
   e delle omissioni comuni, mantenendo gli output separati dalle letture OCR.
3. Confrontare modelli VLM candidati sullo stesso manifest stratificato e sul
   runtime WSL documentato.
4. Estendere il contratto struttura/reference per celle tabellari e relazioni
   di graffa prima di valutare auto-pass per quei layout.
5. Accumulare reference gold separate da calibrazione e holdout; poi definire
   budget d'errore e policy selettiva.
