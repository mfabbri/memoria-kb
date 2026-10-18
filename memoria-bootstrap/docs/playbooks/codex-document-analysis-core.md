# Document Analysis Core

## Scopo

Guidare incrementi su OCR, registrazione documenti, chunking, menzioni,
candidate claim, ledger, review queue, riconciliazione multi-fonte, dataset
preview e output MVP.

## Principio

L'analisi documentale lavora su documenti acquisiti o referenziati. Non produce
fatti verificati senza review e non crea una pipeline parallela per la demo.

## Regole

- Non modificare raw archive, cache o documenti originali.
- Creare solo sidecar, inventari, processed output o report derivati.
- Ogni documento ha fonte, data accesso/riferimento e identificatore.
- Claim candidati sempre `unreviewed`.
- Import store append-only: non promuove claim e non modifica profili.
- `verified_facts.preview` deriva solo da decisioni approvate e resta preview.
- Dataset export e card snapshot restano preview finche' non esiste approvazione
  canonica/editoriale.
- MVP e wrapper aggregano la pipeline principale.

## Workflow OCR CLI T36-T37

`documents process --workflow-manifest` orchestra il runner batch T36 e la
derivazione T37 `DocumentStructure`/Markdown. OcrWorkflow v1.0 esegue T36→T37;
v1.1 aggiunge Tesseract page-scoped diagnostico; v1.2 aggiunge la preparazione
del package di review visuale/lessicale dopo T36/T37/Tesseract. T37 consuma
soltanto evidence PP-OCRv5 di T36 e non usa l'output Tesseract.

Il manifest `OcrWorkflow` v1.0 usa percorsi assoluti o relativi alla propria
directory e dichiara l'hash del manifest batch, configurazione locale del
modello/runtime e profilo T37 per ogni pagina. Le varianti T37 supportate sono
`raw`, `grayscale`, `contrast`, `threshold`; i profili sono
`numbered_report` e `leader_list_report`.

OcrWorkflow v1.1 mantiene gli stessi campi T36/T37 e aggiunge `tesseract` con
`root_dir`, `language`, `tesseract_path`, `page_segmentation_mode`,
`engine_mode`, `dpi`, `preprocess_before_ocr`, `enable_region_ocr` e `pages`.
Ogni pagina dichiara `page_id`, `source_id`, `source_document_id` e riferimenti
`sidecar`/`metadata` con `path` e `sha256`; il TIFF e il suo hash devono
corrispondere alla pagina del manifest T36. Esempio della sola estensione:

```json
{
  "schema_version": "1.1",
  "tesseract": {
    "root_dir": "processed-documents",
    "language": "deu",
    "tesseract_path": "tesseract",
    "page_segmentation_mode": "6",
    "engine_mode": "1",
    "dpi": "",
    "preprocess_before_ocr": false,
    "enable_region_ocr": false,
    "pages": [{
      "page_id": "page-001",
      "source_id": "archive-source",
      "source_document_id": "document-001",
      "sidecar": {"path": "page-001.yaml", "sha256": "<sha256-64-hex>"},
      "metadata": {"path": "page-001.metadata.json", "sha256": "<sha256-64-hex>"}
    }]
  }
}
```

```json
{
  "@type": "OcrWorkflow",
  "schema_version": "1.0",
  "t36": {
    "input_manifest": {"path": "batch.json", "sha256": "<sha256-64-hex>"},
    "language": "deu",
    "model": {
      "ocr_version": "PP-OCRv5",
      "text_detection_model_name": "PP-OCRv5_server_det",
      "text_recognition_model_name": "latin_PP-OCRv5_mobile_rec",
      "text_detection_model_dir": "models/det",
      "text_recognition_model_dir": "models/rec"
    },
    "runtime": {
      "device": "cpu", "enable_mkldnn": false,
      "text_det_limit_side_len": 8192, "text_det_limit_type": "max",
      "tile_width": 2400, "tile_height": 2400,
      "tile_overlap": 200, "retry_limit": 0
    }
  },
  "t37": {
    "variant_id": "raw",
    "page_profiles": {"page-001": "numbered_report"}
  }
}
```

OcrWorkflow v1.2 mantiene i campi v1.1 e aggiunge `review`. Le mappe devono
dichiarare esattamente tutte le pagine e legano ogni risorsa al digest:

```json
{
  "schema_version": "1.2",
  "review": {
    "lexicons": {
      "page-001": {"path": "lexicons/deu.json", "sha256": "<sha256-64-hex>"}
    },
    "glossaries": {
      "page-001": {"path": "glossaries/military.json", "sha256": "<sha256-64-hex>"}
    }
  }
}
```

Il lessico deve essere `OcrLanguageLexicon` e avere lingua compatibile con T36;
il glossario `MilitaryGlossary` è opzionale. V1.2 richiede variante T37 `raw`,
Tesseract nella lingua T36 e senza preprocessing/OCR per regione, affinché le
coordinate siano legate ai pixel originali.

Eseguire prima la preview; solo dopo aver controllato il report usare `--apply`.
`--resume` richiede lo stesso workflow e la directory output esistente. Gli
stage completi vengono riusati dopo verifica di request e inventario hash; uno
stage T36 partial blocca gli stage successivi. Crash gap tra pubblicazione stage e
checkpoint, hash divergenti e artifact aggiunti vengono rifiutati senza
overwrite. Il Tesseract partial è immutabile sul resume. Tutti i risultati
restano `unreviewed`, senza `machine_pass` né auto-validation.

```powershell
memoria documents process --workflow-manifest workflow.json --output-dir <run-esterno>
memoria documents process --workflow-manifest workflow.json --output-dir <run-esterno> --apply
memoria documents process --workflow-manifest workflow.json --output-dir <run-esterno> --apply --resume
```

Con v1.2 `--apply` produce anche l'evidence Tesseract hash-bound e il package
con crop e template visuali/lessicali incompleti; il report termina con
`awaiting_review`. Il package builder deriva un proprio T37 nel package,
distinto dallo stage T37 del workflow e senza altra inferenza. La revisione
visiva e lessicale richiede osservazioni reali nei template; dopo averli
compilati, usare `documents ocr-review-batch` per il gate aggregato. Non usare
`documents process --resume` dopo aver modificato il package: gli artifact
revisionabili sono protetti dal checkpoint immutabile.

Le suite automatiche usano immagini sintetiche e runner iniettati. Le prove
concrete vanno isolate in una nuova directory esterna; il package non attesta
accuratezza e nessun output viene promosso automaticamente.

### Distinguere censimento, esecuzione OCR e review completa

Un inventario con hash, una coorte `prepared` o una classificazione visiva di
layout non sono elaborazione OCR. Riportare separatamente: TIFF identificati e
hashati; pagine realmente passate nei runner OCR; pagine con
`DocumentStructure`/Markdown; review visuali e lessicali completate; traduzioni
generate e relativo `review_status`. Non chiamare "analizzate" o "processate
OCR" le pagine solo censite o stratificate.

Una prova end-to-end reale su una pagina dimostra l'integrazione CLI soltanto.
Per dimostrare che il CLI esegue OCR, usare una nuova directory di output isolata,
`--apply` e una pagina input esplicita; controllare nel report che i runner siano
stati invocati e che `reused_page_count=0` (e `reused=false` per gli stage che lo
espongono). Un output persistito o un resume sono adatti a verificare resume,
provenance e controlli, ma non provano una nuova inferenza. `awaiting_review`/
`unreviewed` indica che il workflow ha prodotto la candidata e il package ma la
review di quel run non è chiusa. Una review precedente di un altro run sulla
stessa scansione non chiude il nuovo package: digest e risultato devono riferirsi
agli artefatti esatti.

Tenere distinti i due obiettivi: chiudere il flusso OCR end-to-end richiede una
review riferita agli artefatti del run reale; calibrare l'auto-validazione
richiede invece una coorte sufficiente, preregistrata e congelata prima
dell'inferenza di calibrazione. Un inventario, uno score diagnostico o una prova
CLI non sostituiscono reference adjudicate e holdout indipendente. Quando il
frame non sostiene uno strato, non inventare esempi o dedurli dal nome file:
escludere quello strato dall'auto-accept e mantenere il fallback di review finché
un frame più ampio non lo supporta.

La trascrizione OCR conserva il testo nella lingua sorgente; una traduzione è un
artefatto distinto e va dichiarata solo se generata, con stato di review
esplicito. La conferma umana di una reference o di un fatto archivistico resta
distinta dalla validità operativa della candidata OCR. Il pilot misura gli errori
materiali come quota di parole per pagina (soglia iniziale 1%) e il rischio di
false accettazioni con limite superiore unilaterale al 95% (massimo 5%). Un
singolo errore sotto la soglia percentuale non invalida automaticamente la
pagina. Finché score e cutoff non sono sostenuti da calibration e holdout
indipendente, non attivare auto-validazione; produrre candidate e limitare
l'intervento umano ai dubbi residui e agli audit di calibrazione, senza chiedere
conferma individuale di ogni pagina o traduzione come gate di validità.

## Golden run multi-fonte

Per T29-T33:

- selezionare 2-4 documenti, non una scansione massiva;
- includere almeno due fonti/famiglie differenti;
- produrre una vista di riconciliazione che mantenga ogni claim separato;
- mostrare compatibilita', complementarita' o conflitto;
- collegare decisioni, verified facts e patch allo stesso `run_id` canonico;
- ridurre worklist e report al caso dimostrativo.

## File tipici

```text
memoria-engine/code/caduti_fonti_report/document_analysis/
memoria-engine/scripts/*document*.ps1
memoria-engine/scripts/*mvp*.ps1
memoria-engine/tests/test_*document*.py
memoria-engine/tests/test_*mvp*.py
```

## Test

Usare fixture offline, directory temporanee o DB SQLite temporaneo. Le run reali
possono essere lette solo in modalita' controllata e read-only quando
l'incremento lo richiede.

## Procedura operativa riutilizzabile per OCR su immagini

Questa è la procedura corrente per un pilot OCR controllato. Gli asset grandi
restano fuori dal repository Git, ma la root, le versioni, gli hash e la
provenance devono essere dichiarati in ogni run. Non usare `%TEMP%`, cache
utente implicite o directory modello scoperte automaticamente come dipendenze
operative.

### Root project-local e asset

Usare esclusivamente la root project-local
`D:\CaDiMalanca\me.mo.ri.a-kb-runtime\`, con questa separazione:

```text
D:\CaDiMalanca\me.mo.ri.a-kb-runtime\
├── ocr-assets\
├── ocr-cache\
└── ocr-runs\
```

Impostare `PADDLE_HOME` e `PADDLEOCR_HOME` alla root project-local e passare
sempre al runner directory modello esplicite (detector, recognizer e, se
applicabile, `tessdata`). Registrare nel manifest la root, le versioni del
runtime e dei modelli, i digest SHA-256 e la provenienza degli asset. La root
non va aggiunta al repository: deve però essere ricostruibile o verificabile a
partire da manifest e hash.

### Discovery, campione e migrazione

Il percorso delle immagini di riferimento è:
`P:\Comune\Me.Mo.Ri.a\documenti_da_processare\foto\T314 R1275`.
Prima di scegliere il campione:

1. enumerare ricorsivamente i TIFF e calcolare il loro SHA-256;
2. distinguere gli input TIFF dalle cartelle `test`, `ocr-output-test`, dagli
   output Markdown/TSV/JSON e dai sidecar, che non sono input immagini;
3. registrare percorso relativo, dimensioni, estensione, hash e motivo di
   inclusione/esclusione nel manifest del campione;
4. escludere `00026` e `00028`, già analizzati, e non ripetere la riga 5 di
   `00026` già oggetto di analisi/reference.

Per migrare asset o output, copiare senza cancellare le sorgenti. Confrontare
SHA-256 sorgente/destinazione e produrre `migration-manifest.json` con root,
file count, percorsi relativi, dimensioni e hash. Bloccare la procedura se il
file count non coincide o se esiste anche un solo mismatch; registrare invece
esplicitamente l'esito quando il confronto è completo.

### Smoke PP-OCRv5 e normalizzazione fail-safe

Ogni smoke test deve registrare almeno versione Paddle/PaddleOCR, modello e
directory modello, parametri effettivi, `max_side_limit=4000`, latenza e
numero di regioni. Se `rec_boxes` non è allineato a `rec_texts`, escludere il
campo fail-safe, registrare l'evento nel manifest e mantenere le altre evidenze.
Non inventare geometrie, non riallineare per indice e non trasformare un
payload parziale in una geometria attendibile.

### Accuracy e delega

Gli output reali restano `unreviewed`. Non calcolare o dichiarare CER, WER,
accuracy, coverage qualitativa o claim senza una reference umana verificata e
page-scoped, con identità della pagina corrispondente. Confidence OCR,
processabilità tecnica e numero di regioni non sono accuratezza.

Se il runner custom non parte, registrare il fallback con causa, agente,
parametri, input e directory di output; mantenere separati gli artefatti e non
duplicare run indistinti. Un fallback non autorizza a modificare TIFF, claim,
profili canonici o a promuovere output.

## Benchmark OCR su immagini

### Ambiente locale PP-OCRv5 su Windows

Procedura usata il 2026-09-19 per il benchmark opt-in, con PowerShell dalla
cartella `D:\CaDiMalanca\me.mo.ri.a-kb\memoria-engine`. Riutilizzare il venv
del repository e verificare il suo interprete prima di installare. Quando si
guida l'installazione in modo interattivo, confermare la cartella corrente e
fornire un comando per volta, attendendo l'esito prima di procedere:

```powershell
Test-Path .\.venv\Scripts\python.exe
```

Il risultato deve essere `True`. Installare PaddlePaddle CPU 3.3.0 dall'indice
CPU ufficiale, quindi fissare PaddleOCR alla versione provata:

```powershell
.\.venv\Scripts\python.exe -m pip install paddlepaddle==3.3.0 -i https://www.paddlepaddle.org.cn/packages/stable/cpu/
.\.venv\Scripts\python.exe -m pip install paddleocr==3.7.0
```

Verificare interprete, versioni e import con il Python del venv:

```powershell
.\.venv\Scripts\python.exe -c "import paddle, paddleocr; print('PaddlePaddle', paddle.__version__); print('PaddleOCR', paddleocr.__version__)"
```

Per il runner dal repository, impostare `PYTHONPATH` nella sessione PowerShell
e usare il medesimo interprete `.venv`. Il runner benchmark esistente è
`caduti_fonti_report.document_analysis.ocr_benchmark`; non serve creare uno
script di installazione o un comando custom. Evitare installazioni nel Python
globale o in altri ambienti del repository.

Questi comandi preparano i pacchetti Python e non scaricano i pesi OCR. La
procedura seguente è storia del benchmark del 2026-09-19 e non è riutilizzabile
come setup operativo: nella sessione i modelli erano già scaricati ed estratti sotto
`%TEMP%\memoria-ppocr-v5-20260919\models`; non è stata ricostruita qui una
procedura affidabile di download, quindi non aggiungere comandi di download
ipotetici. Il benchmark ha usato le directory locali appiattite
`PP-OCRv5_mobile_det_infer`, `latin_PP-OCRv5_mobile_rec_infer`,
`en_PP-OCRv5_mobile_rec_infer` e `eslav_PP-OCRv5_mobile_rec_infer`.
Un primo tentativo ha assunto erroneamente directory annidate come
`en\PP-OCRv5_mobile_rec_infer` ed è fallito con `FileNotFoundError`; controllare
i percorsi realmente presenti prima di invocare il runner. Non copiare o
salvare i modelli nei repository.

Esempio del solo setup del path per il runner, dalla directory
`memoria-engine`:

```powershell
$env:PYTHONPATH = 'code'
```

Consultare il runner e la nota di benchmark in `../current-next-increment.md` per
gli argomenti richiesti; evitare di mantenere comandi one-liner lunghi nella
procedura di setup.

- Registrare hash SHA-256 dell'originale e del payload effettivamente inviato a
  ciascun motore.
- Descrivere la pipeline riproducibile di decode e trasformazione: formato,
  algoritmo di resize/crop e dimensioni risultanti; registrare modalità colore
  e orientamento solo se applicati. Se si afferma che due
  modelli hanno ricevuto gli stessi pixel, verificare un hash canonico dei pixel
  decodificati o una verifica equivalente; un hash PNG differente non prova
  pixel differenti, mentre sorgente e dimensioni uguali non provano payload
  identici.
- Registrare la provenance specifica dei motori, inclusi modello/versione,
  parametri, prompt e hash del prompt quando applicabile.
- Riportare output vuoto o zero-token come nessuna trascrizione, senza
  conteggiarlo come copertura utile.
- Su immagini reali, riportare accuratezza solo in presenza di ground truth
  umana validata; altrimenti presentare gli output per revisione senza metriche
  di accuratezza.

## Direzione OCR corrente - 2026-09-20

Documento autorevole: `../ocr-structured-evidence-strategy.md`.

Per i prossimi incrementi non aprire una nuova gara fra framework. Usare questa
sequenza:

1. PP-OCRv5 come recognizer primario del pilot e Tesseract come seconda lettura.
2. Conservare regioni, testo, confidence, polygon/bbox e trasformazioni in
   `OcrPageEvidence`; non ricostruire layout dalla stringa normalizzata.
3. Su scansioni degradate preferire crop/tiling tracciato al downscale globale
   obbligatorio; preprocessing diversi sono varianti indipendenti.
4. Ricostruire `DocumentStructure` con geometria e regole deterministiche. I
   primi profili sono `leader_list_report` (00028) e `numbered_report` (00026).
5. Generare Markdown soltanto da `DocumentStructure`, mantenendo
   `source_region_ids` per ogni blocco. La confidence/status della struttura
   descrive la regola di layout, resta distinta dalla confidence OCR e non e'
   una misura di accuratezza.
6. Introdurre un VLM soltanto su crop ambigui se una reference umana mostra un
   vantaggio misurabile. Nessun page-to-Markdown libero.
7. PP-StructureV3 e Docling restano comparatori; non aggiungerli al runtime
   corrente senza un difetto misurato che giustifichi la dipendenza.

Il quality gate OCR corrente misura processabilita' tecnica, non accuratezza.
Non usare `accepted` come sinonimo di testo affidabile o revisionato.

### Avvio CLI del pilot T36

Il primo passaggio di OCR ad alta risoluzione e' disponibile nella CLI Python
con `memoria documents ocr-transform-pilot`. Richiede due TIFF espliciti, nomi
e directory locali dei modelli PP-OCRv5 e una directory output nuova esterna al
repository. Senza `--apply` mostra il preflight senza inizializzare Paddle,
eseguire inferenza o scrivere; `--apply` produce il pacchetto T36 con varianti,
tile, evidence strutturata, hash e provenienza. Gli output rimangono
`unreviewed` e non attestano accuratezza.

Esempio da adattare ai percorsi locali verificati dei pesi:

```powershell
memoria documents ocr-transform-pilot `
  --input <00026.tif> `
  --input <00028.tif> `
  --output-dir <runtime-root>\ocr-runs\t36-cli-<run-id> `
  --language deu `
  --text-detection-model-dir <ocr-assets>\PP-OCRv5_server_det `
  --text-detection-model-name PP-OCRv5_server_det `
  --text-recognition-model-dir <ocr-assets>\latin_PP-OCRv5_mobile_rec `
  --text-recognition-model-name latin_PP-OCRv5_mobile_rec
```

Aggiungere `--apply` soltanto dopo aver controllato input, modelli e destinazione.
Il manifest registra un fingerprint dei TIFF, modelli locali, lingua, tiling e
opzioni runtime, oltre a durata di processing, throughput e p95 per target OCR.
La durata esclude inizializzazione runtime e serializzazione dei report; la
latenza per target include la materializzazione della risposta Paddle. Costo e
tempo di revisione sono `null` finche' non esiste una sorgente misurabile.
Per riusare un run completato, passare `--resume` con gli stessi input, modelli,
opzioni e directory output: la CLI non inizializza Paddle e verifica il
fingerprint e l'hash dell'intero inventario degli artifact. Run legacy senza
checkpoint, input/configurazioni divergenti o file mancanti, alterati o extra
vengono rifiutati. Il resume non recupera run interrotti e non li sovrascrive.
Il runner consente inoltre `--retry-limit 0|1` (default `1`): ritenta solo
eccezioni del runner o della materializzazione dell'output Paddle, non gli errori
deterministici di input/evidence. Se una pagina fallisce dopo i tentativi, i suoi
artifact parziali vengono rimossi e la pagina successiva viene comunque
elaborata. Il manifest/checkpoint segnala `partial`, la CLI restituisce exit 1 e
quel checkpoint non e' riutilizzabile; T37 e il bridge Tesseract rifiutano le
pagine incomplete. Il limite del comando pilot resta due TIFF.

### Runner T36 da manifest con checkpoint per pagina

Per preparare un batch senza cambiare il pilot guida usare
`memoria documents ocr-transform-batch`. Il manifest UTF-8 ha schema v1.0 e
contiene almeno una pagina; `path` relativo si risolve dalla directory del
manifest e `sha256` deve corrispondere ai byte del TIFF:

```json
{
  "schema_version": "1.0",
  "pages": [
    {"page_id": "pagina-1", "path": "scans/pagina-1.tif", "sha256": "<sha256-64-hex>"}
  ]
}
```

La preview e' il default e non inizializza Paddle ne' scrive. Con `--apply`, il
runner valida tutte le pagine e il fingerprint prima di inizializzare il runtime;
ogni pagina ha directory e checkpoint atomici propri. `--resume` senza `--apply`
verifica la richiesta e mostra quante pagine complete sono riusabili. Con
`--apply --resume` le pagine complete con artifact intatti vengono riusate,
mentre quelle fallite o interrotte sono riprocessate; checkpoint completi
alterati e richieste divergenti falliscono chiusi. Il manifest aggregato resta
`OcrTransformPilot` v1.0, compatibile con T37 e col bridge Tesseract; se una
pagina fallisce lo stato e' `partial` e i consumer rifiutano il lotto incompleto.
Gli output restano `unreviewed`.

Il comando batch abilita l'orchestrazione tecnica, non autorizza a estendere il
pilot reale oltre i due TIFF guida prima della relativa review. Tesseract,
struttura T37, Markdown, lessico, verifiche deterministiche e review page-level
restano passaggi distinti; VLM e auto-validazione non sono prerequisiti. Il grafo
dei consumer e': T36 produce sia l'input diretto per T37, sia l'ancora raw del
ramo Tesseract. T37 usa le evidence PP-OCRv5 dal manifest T36; il bridge
`ocr-tesseract-from-t36` aggiunge evidence Tesseract diagnostiche per il
confronto, ma non e' un input di `ocr-transform-structure`. Non concatenare i due
rami fingendo una dipendenza o un'unica trascrizione selezionata.

### Derivazione T37 dal pacchetto T36

`memoria documents ocr-transform-structure` consuma il `pilot-manifest.json`
T36 gia' prodotto. Richiede una variante full-page esplicita e una coppia
`page_id=profile` per ogni pagina; verifica hash della scansione e della
variante, identita' dell'evidence e coordinate full-page prima di derivare
`OcrPageEvidence`, `DocumentStructure` e Markdown. La preview esegue i controlli
senza scrivere; `--apply` crea una nuova directory esterna al repository con
gli artefatti e un `run-manifest.json` che lega digest e fasi completate.

```powershell
memoria documents ocr-transform-structure `
  --manifest <t36-run>\pilot-manifest.json `
  --variant contrast `
  --page-profile T314-1275-00026=numbered_report `
  --page-profile T314-1275-00028=leader_list_report `
  --output-dir <runtime-root>\ocr-runs\<nuovo-run-t37>
```

Aggiungere `--apply` per scrivere. Il report mantiene esplicitamente pending
Tesseract, lessico, copertura visuale, layout, disposition e review page-level;
la candidata resta `unreviewed`, senza attestazione semantica, gold o machine
pass. La variante e i profili sono scelte dichiarate dall'operatore, non
selezionate dalla confidence.

### Verifica visuale assistita e richieste di review

Il controllo linguistico è un passaggio obbligatorio **prima** di coinvolgere
l'utente. Sulla trascrizione candidata (e non soltanto sul raw OCR) eseguire o
riusare il triage T43/T44 per la lingua corretta: dizionario Hunspell locale
con versione/hash espliciti e glossario militare esplicito per parole composte
e abbreviazioni. Consultare gli esiti `exact_match`, `not_found` e tutti i
`fuzzy_suggestions`; per i termini non trovati verificare se sono nomi propri,
forme storiche/composte o sigle non incluse nel glossario. Se il triage
persistente è riferito alla stessa pagina ma alla trascrizione raw, controllare
che copra anche le forme corrette/aggiunte nella candidata e interrogare
Hunspell per le forme nuove. Registrare risorsa, versione, hash, copertura,
risultati e classificazione dei non trovati prima della richiesta umana.

Un match lessicale è un indizio, non una prova della lettura; l'assenza dal
dizionario o dal glossario non è un errore certo e un suggerimento fuzzy non è
una correzione automatica. Usare i database per individuare parole o acronimi
da ricontrollare e per risolvere forme sostenute da fonti lessicali esplicite;
conservare le forme storiche e non espandere sigle senza supporto. La richiesta
all'utente può partire solo dopo questo passaggio e il confronto visuale.

Prima di chiedere all'utente una correzione visuale, eseguire i controlli
riproducibili gia' disponibili: confrontare crop dell'immagine, regioni e testo
OCR persistente; se utile, usare una seconda lettura indipendente sul solo crop.
Non rilanciare OCR quando un output valido e' gia' disponibile. Registrare
separatamente i casi risolti automaticamente e quelli ancora ambigui; chiedere
intervento umano solo su questi ultimi, mostrando il crop e l'evidenza che
impedisce una conclusione.

Per ridurre il carico manuale, leggere prima la pagina e i crop alla risoluzione
utile, confrontando tutti gli output persistenti. Conteggiare i soli dubbi che
restano irrisolti dopo questo passaggio; non chiedere conferma di gruppi gia'
leggibili o di differenze OCR risolvibili sull'immagine. Se il conteggio e'
zero, salvare una trascrizione candidata `unverified_model_assisted` con
provenance e proseguire alla pagina successiva. Se restano molti dubbi, fermare
la batch review e rivalutare crop, segmentazione o strumenti prima di scaricare
decine di decisioni sull'utente. Questa scorciatoia produce candidati, non una
reference `human_verified`; quest'ultima richiede la conferma umana prevista dal
contratto prima di metriche o promozioni.

Separare esplicitamente le decisioni richieste: confermare il testo non
conferma la struttura del Markdown, e confermare la struttura non conferma
l'associazione tra blocchi e regioni dell'immagine. Evitare richieste generiche
come "confermi il mapping?". Per ogni dubbio indicare pagina, blocco/regioni,
letture candidate e la scelta precisa richiesta; se nessuna scelta e'
sostenibile, lasciare il campo irrisolto.

Il disaccordo fra OCR, lettura visuale e reference puo' ordinare una review,
non stabilire quale lettura e' vera ne' rimuovere elementi dalla coda. Le prove
di normalizzazione vanno eseguite solo in confronto ombra, simmetricamente su
reference e output, conservando gli originali. Se la trasformazione cambia la
segmentazione, dichiarare il nuovo denominatore e non confrontare gli indici
come se fossero invariati. Un risultato su poche pagine non definisce una
soglia o una regola di accettazione; i risultati diagnostici T41 sono registrati
in `../current-next-increment.md`.

### Sequenza end-to-end e controllo del Markdown

Per ogni pagina, seguire questo ordine prima di chiedere lavoro all'utente:

1. Verificare identita' e SHA-256 del TIFF e degli output gia' persistiti. Non
   rilanciare OCR se gli output validi esistono; l'immagine originale resta la
   fonte primaria.
2. Costruire o riusare una mappa strutturata di regioni con `source_region_id`,
   bounding box, tipo (titolo, paragrafo, tabella, nota) e ordine di lettura.
   Verificare copertura e raggruppare regioni spezzate che appartengono alla
   stessa riga/voce, cosi' il numero di regioni non diventa il numero di review.
3. Allineare PP-OCR, Tesseract e gli altri output disponibili per blocco. Se
   utile, eseguire una lettura visiva indipendente solo tramite il percorso
   Ollama WSL documentato (`ollama-wsl` o endpoint locale esplicito), dopo aver
   verificato runtime, modello, digest e compatibilita'. Salvare tale lettura
   separatamente: non deve sovrascrivere OCR, struttura o candidata.
   Prima di qualsiasi richiesta VLM, verifica il runtime WSL canonico con GET
   read-only a `/api/version` e `/api/tags` tramite:

   ```powershell
   wsl.exe -e curl --fail --silent --show-error --max-time 10 http://127.0.0.1:11434/api/version
   wsl.exe -e curl --fail --silent --show-error --max-time 10 http://127.0.0.1:11434/api/tags
   ```

   Registra versione, tag richiesto, digest e capability. Ollama e' installato
   in WSL (confermato dall'utente). `E_ACCESSDENIED`/`Access denied` quando il
   sandbox avvia WSL significa `runtime_access_blocked`, non runtime assente.
   Non usare l'istanza Windows come fallback e non dichiarare WSL/Ollama mancanti.
   In questo caso ferma solo il passaggio VLM, continua il lavoro offline e
   riprendi quando il percorso WSL documentato e' accessibile. `model_missing` si
   assegna solo dopo aver ricevuto correttamente `/api/tags` dal runtime WSL.
   Per misurare un resolver VLM usa `memoria documents vlm-crop-evaluate` solo
   su una coorte esterna `OcrVlmCropEvaluationCohort` con `cohort_role=development`
   e reference `OcrPageReference` verificate. Il comando rifiuta il ruolo
   `holdout`, genera i crop dall'immagine hash-bound e non invia la reference al
   modello. La preview esegue inferenza live; `--apply` salva solo il report.
   Le metriche valgono solo sulla coorte e non autorizzano auto-acceptance o la
   soglia pilot 5%.
4. Comporre il Markdown dalla mappa strutturata, preservando ordine, righe,
   intestazioni, celle e forme stampate. Non dedurre contenuto mancante dalla
   plausibilita' linguistica e non normalizzare silenziosamente numeri o sigle.
5. Eseguire Hunspell e glossario esplicito sulla candidata esatta. Si puo'
   riusare un triage raw solo dopo aver verificato che copra le forme della
   candidata; interrogare le forme nuove. Classificare i non trovati e i fuzzy
   per termine e posizione: sono alert, non conteggi di dubbi o azioni manuali.
6. Eseguire controlli deterministici: copertura una-volta-sola delle regioni,
   ordine geometrico coerente, conteggio righe/colonne/celle, associazione
   Markdown-cella e assenza di blocchi persi o duplicati. Renderizzare il
   Markdown quando serve e confrontare ogni area con pagina/crop corrispondente.
7. Risolvere automaticamente soltanto i disaccordi sostenuti dall'immagine,
   da piu' evidenze indipendenti o da risorse lessicali esplicite. Il VLM puo'
   segnalare regioni e letture alternative; non decide da solo e deve poter
   dichiarare incertezza. Raggruppare gli eventuali dubbi residui per decisione
   umana, non per regione OCR. Chiedere in un solo passaggio le sole decisioni
   che cambiano materialmente la lettura; una singola parola degradata ma
   plausibile non blocca la chiusura se la candidata e' accettata con incertezza
   esplicita e tutte le altre verifiche sono concluse.

#### Classificazione degli alert e coerenza degli artefatti

Per ogni alert lessicale registrare la forma esatta, lo stato Hunspell/glossario,
gli eventuali fuzzy suggestion e tutte le occorrenze con `block_id` e
`source_region_ids` (o coordinate equivalenti). Classificare ogni forma/occorrenza
come forma stampata o storica, sigla/identificatore, nome proprio/termine di
dominio, frammento di riga o parola spezzata, errore OCR confermato oppure dubbio
irrisolto. Per le parole spezzate verificare il testo stampato ai due lati della
fine riga; non unire frammenti solo per plausibilita' linguistica.

Nel riepilogo riportare separatamente: forme uniche, occorrenze, alert classificati,
correzioni sostenute e applicate, dubbi residui distinti e decisioni effettivamente
richieste all'utente. `not_found`, numero di suggerimenti fuzzy, token o regioni
non sono conteggi di decisioni manuali. Confrontare ogni dubbio con l'immagine/
crop ed eventuali fonti lessicali esplicite. Se i pixel restano ambigui ma una
candidata e' sostenuta dalla lingua e dal contesto, registrare la lettura come
accettata con riserva, senza presentarla come certezza visiva. La pagina puo'
essere classificata `review_complete_with_residual_uncertainty` quando copertura,
correzioni, provenance e struttura sono state controllate e i residui sono
localizzati e conteggiati; non serve un tasso di incertezza pari a zero. Lasciare
`needs_review` se resta una decisione materiale, una riga non confrontata o un
problema di identita'/copertura.

Dopo ogni correzione, verificare che la stringa sia presente nella candidata esatta
e che non resti la forma precedente dove l'immagine la smentisce. Ricalcolare il
digest della candidata, rieseguire il controllo lessicale sulla versione aggiornata
e allineare report, elenco correzioni e stato di review. Una correzione descritta
nel report ma non applicata alla candidata e' una discrepanza; non riportarla come
completata. La candidata senza dubbi residui resta comunque
`unverified_model_assisted` finche' non interviene la conferma umana richiesta per
una reference. La chiusura della review page-level non equivale a una reference
gold completa: quest'ultima richiede il livello di conferma previsto dal relativo
contratto. Una pagina chiusa con riserva resta fuori dalla calibrazione metrica se
la reference necessaria non e' verificata.

#### Gate per una soglia di validazione automatica

Prima di calcolare metriche o soglie, ricostruire l'inventario delle reference dai
record page-scoped correnti, verificando stato di review, origine umana, identita'
e hash della pagina. Non assumere che un inventario aggregato sia aggiornato:
confrontarlo con i record e gli audit piu' recenti. Usare report di confronto
riconciliati e controllare denominatori, regioni abbinate, trasformazioni e
`accuracy_eligible`; metriche discordanti o obsolete vanno ricalcolate, non mediate
o scelte in base al valore piu' favorevole.

Definire prima gli strati rilevanti (almeno lingua, leggibilita' e layout), fissare
la divisione calibrazione/holdout e mantenere il holdout fuori da tuning e scelta
della soglia. Valutare errori testuali, omissioni, aggiunte, copertura e fedelta'
strutturale nei soli strati eleggibili. Un campione iniziale di 8-10 pagine avvia
il pilot ma non autorizza da solo l'auto-accettazione: servono criteri congelati,
misura dei falsi passaggi e holdout separato. Se mancano reference verificate,
stratificazione, metriche riconciliate o holdout integro, dichiarare `no-go` e
continuare a produrre candidati non verificati; non inventare una soglia.

Con l'attuale calibrazione CLI, i minimi di 80 (tre strati) o 86 (quattro
strati) sono casi **auto-accettati** per strato in ciascuna partizione, con zero
falsi passaggi; non sono il numero grezzo di pagine da processare. Qualunque
falso passaggio richiede un campione maggiore. Stimare quindi il volume grezzo
necessario prima di avviare OCR e non congelare una coorte purposive o priva di
uno strato richiesto. Se uno strato raro non ha casi indipendenti in entrambe le
partizioni, restringere esplicitamente il perimetro di auto-accept e lasciarlo
in review manuale, oppure ampliare il frame prima del campionamento.

##### Rubrica per il tasso di errore materiale per pagina

La qualità della pagina non è binaria: si misura il rapporto
`material_word_error_count / reference_word_count`. Il limite iniziale del pilot
è `1%`: una discrepanza su una pagina di 300 parole vale circa `0,33%` e non
blocca da sola la validità della trascrizione. La soglia di sistema è separata:
tra le pagine che il punteggio auto-accetterebbe, il limite superiore unilaterale
al 95% della quota di pagine che superano l'1% deve essere al massimo `5%`, sia
nel totale sia negli strati richiesti.

Confrontare la candidata OCR esatta con la reference `human_verified/verified` e
il TIFF originale. Contare ogni parola affetta da discrepanza materiale una sola
volta anche se ricade in più categorie. Sostituzioni, omissioni e aggiunte
adjudicate come materiali contribuiscono al numeratore; una parola inserita o
omessa conta una volta. Per errori strutturali, contare le parole la cui
associazione errata cambia la lettura. Il denominatore è il numero di parole
nella reference. Usare esclusivamente le categorie gia' previste dal contratto CLI:

- `text`: sostituzione o aggiunta che cambia il contenuto, per esempio negazione,
  azione, soggetto, destinatario o relazione. Punteggiatura o grafia sono
  materiali solo se cambiano il significato o l'identificazione.
- `omission`: una parola, riga, intestazione, nota o altro contenuto leggibile e
  informativo manca dalla candidata. Non contare margini vuoti o segni non
  testuali; se un testo e' visibile ma non adjudicabile, non dichiararlo assente.
- `number_or_name`: nome, toponimo, sigla, identificatore, data, quantita',
  unita' o numero di riferimento e' omesso o alterato in modo da cambiare
  identita', tempo, quantita' o attribuzione. Non normalizzare grafie storiche
  per rendere la candidata simile a una forma moderna.
- `structure`: ordine, raggruppamento, allineamento tabellare o relazione tra
  intestazione, riga, colonna e valore e' errato e cambia l'associazione o la
  lettura. Una differenza puramente visiva senza effetto interpretativo non
  basta.

Registrare `material_word_error_count`, `reference_word_count` e una o più
`material_error_categories` senza duplicati; se non vi sono discrepanze materiali,
il conteggio è zero e la lista è vuota. Conservare per ciascun rilievo i
`source_region_ids` o le coordinate/crop, la classe d'errore e una motivazione
breve nel sidecar di adjudication. CER, WER, confidence, accordo fra motori e
alert lessicali orientano il controllo, ma non determinano da soli la materialità.

L'adjudicazione dettagliata e' limitata ai campioni di calibrazione e audit che
richiedono una reference verificata; non si ripete su ogni scansione operativa.
In produzione il punteggio calibrato stima il rischio di superare il limite e
indirizza a controllo mirato solo i casi incerti o ad alto rischio. La soglia
per pagina resta basata sulla quota di parole, non sul conteggio grezzo degli
errori.

L'adjudicazione usa il TIFF, la candidata legata al digest e la reference
page-scoped verificata. Due revisori classificano indipendentemente gli esiti
del pilot senza vedere engine, confidence, score o cutoff; un adjudicatore
risolve i disaccordi e registra la decisione. Se una discrepanza non si puo'
risolvere sull'immagine e sulla reference, il caso resta non adjudicabile e
blocca l'audit: non va etichettato come assenza di errori, escluso dal
denominatore o convertito in una categoria per supposizione. Il contratto CLI
registra conteggio di parole affette, numero di parole reference e categorie;
un caso non adjudicato non e' completo.

##### Preregistrazione della coorte e separazione

Prima di consultare output OCR o metriche per la coorte da aggiungere, congelare
un registro datato con: ID pagina e documento, SHA-256 del TIFF, motivazione e
frame di campionamento, lingua, leggibilita', layout, strato assegnato,
partizione (`calibration` oppure `holdout`), esposizione precedente a engine,
trasformazioni/output persistenti e responsabile della selezione. Le etichette
qualitative di leggibilita' e layout si assegnano dal TIFF, prima di leggere il
risultato OCR. Non spostare pagine tra partizioni dopo aver consultato testo,
confidence, errori o metriche.

Dichiarare l'unita' di indipendenza con evidenza esplicita. Non dedurre che file
con nomi distinti siano documenti indipendenti, né unirli in un documento per
somiglianza dei nomi. Un'attestazione che i TIFF selezionati sono documenti
singoli vale per la coorte e il ciclo indicati: non aggiorna retroattivamente
identita' o provenance di evidence create in precedenza.

La calibrazione puo' usare le proprie reference adjudicate per scegliere score
e cutoff. Prima di aprire risultati o label del holdout, registrare nome e
direzione dello score, cutoff, digest del set di calibrazione, strati richiesti
e digest della lista holdout. I revisori del holdout restano ciechi al cutoff e
allo score. Riconciliare il dataset di audit con l'intera lista holdout
preregistrata: ogni pagina deve comparire una sola volta con score, reference,
evaluation eleggibile e label; nessuna pagina senza label puo' essere omessa per
ridurre il denominatore. Se la coorte, la provenance o una label non quadra,
l'esito e' `no-go`.

Il comando `documents ocr-threshold-audit` richiede il dataset holdout v1.2 e
`--cohort-manifest` con un manifest preregistrato esterno v1.1. Il manifest
registra frame e metodo di campionamento, unità di indipendenza, definizioni
esplicite degli strati (lingua, leggibilità, layout) e per pagina motivazione,
esposizione precedente ai motori e trasformazioni. L'audit richiede una sola
pagina per `source_document_id`, rifiuta hash TIFF duplicati e controlla che i
descrittori della pagina corrispondano allo strato dichiarato. Il dataset lega
`cohort_id` e SHA-256 del manifest; il manifest include `frozen_at` e
`frozen_before_threshold: true`, mentre il dataset lega `threshold.frozen_at`.
Il comando rifiuta timestamp senza fuso o un cutoff congelato prima della
coorte, poi confronta l'insieme esatto dei
page ID e, per ogni caso, documento, SHA-256 TIFF e strato. Rifiuta pagine
mancanti, extra, duplicate o divergenti e riporta digest e numerosita' della
coorte nel report. Il digest lega il dataset al file fornito, ma non prova da
solo la veridicita' della data di congelamento: conservare il manifest in una
registrazione esterna immutabile prima di consultare soglie o risultati holdout.

Per costruire feature di calibrazione da una candidata già prodotta, usare
`documents ocr-risk-features` indicando il TIFF originale, il candidato
`OcrCandidateAssessment`, struttura, Markdown, evidence candidata, review
lessicale, comparison e le due evidence sorgente. Il comando ricalcola
assessment e confronto dai file originali, verifica digest e identità TIFF/page/
frame, e rifiuta report obsoleti o artefatti modificati. La preview è read-only;
`--apply` scrive un nuovo `OcrRiskFeatureBundle` hash-bound senza modificare gli
input. Le feature includono conteggi/rapporti di agreement, disagreement,
coverage delle regioni presenti, alert lessicali e ambiguità. La coverage non è
coverage visiva della pagina e regioni unmatched possono sovrapporsi ai
componenti ambigui. Il bundle non contiene ancora uno score calibrato: lascia
`risk_score` e `cutoff` null e `score_status=not_calibrated`. Il bundle v1.1
riporta riepiloghi di confidence per ciascuna evidence separatamente, con scala
nativa e copertura; valori assenti, scale mancanti/miste o valori invalidi sono
dichiarati e non aggregati in modo ambiguo. Le confidence non si normalizzano né
si confrontano direttamente tra motori e non sono mappate sul rischio. Non
inviare il bundle all'audit holdout come se fosse uno score congelato; serve
prima calibrare sui soli dati di calibrazione con label materiali adjudicate.

Dopo aver compilato i sidecar esplicitamente modificabili, usare
`documents ocr-review-finalize --manifest <review/package-manifest.json>
--final-manifest <review/finalized-package-manifest.json> --output
<review-batch-report.json> --apply`. Il comando aggiorna gli hash solo di
`lexicon_review`, `layout`, `ledger` e `dispositions`, crea un manifest
derivato e ricalcola il gate batch. Verifica che gli altri input e output siano
ancora identici al package originale; una correzione a evidence, struttura o
Markdown richiede la rigenerazione upstream del package. Senza `--apply` esegue
gli stessi controlli in preview read-only. Il report resta diagnostico e non
abilita `machine_pass`, auto-validation o promozioni; dopo modifiche/finalize
non riprendere il workflow originale.

La coorte holdout non si usa per scegliere score, cutoff, feature o strata. Il
controllo statistico riguarda le sole pagine che il cutoff congelato avrebbe
auto-accettato, ma tutte le pagine preregistrate devono essere riconciliate con
il dataset. Una pagina oltre l'1% è un falso passaggio per il secondo target;
una pagina con errori che resta entro l'1% non conta come falsa accettazione.
Con zero pagine oltre soglia il limite aggregato unilaterale al 95% richiede
almeno 59 pagine auto-accettate; i controlli per strato possono richiederne di
piu'. Nessun esito abilita `auto_validation_enabled` o `machine_pass` finché il
campione indipendente non sostiene entrambi i limiti.

Caso T41 00598 (2026-10-14): 35 forme lessicali uniche, 42 occorrenze, tre
correzioni visivamente confermate e zero decisioni manuali residue. La candidata
e' rimasta non verificata e il risultato non ha autorizzato una soglia: esistevano
solo quattro reference verificate, mancava la stratificazione richiesta e alcuni
report dovevano essere riconciliati. Usare il caso come esempio di conteggio, non
come benchmark o regola di accettazione.

Caso T41 00007 (2026-10-15): tutte le 51 regioni persistite sono state confrontate
con TIFF e crop; 43 sono state mappate e 8 escluse con motivazione. Dopo aver
ricomposto le parole spezzate, il controllo lessicale della candidata ha prodotto
244 exact, 38 not-found, 7 fuzzy e 34 occorrenze non-word. Questi conteggi
descrivono categorie diagnostiche e non si traducono in altrettante decisioni
manuali. Prima della conferma restava una sola decisione umana: il glifo in
`vorzu[s/e]toßen`. L'utente ha confermato la
candidata completa e `vorzustoßen`; Duden documenta la forma come infinito con
`zu` di `vorstoßen`. Dopo la conferma non restavano decisioni manuali aperte e la
pagina è stata registrata come reference `human_verified/verified`. Questo mostra
che una incertezza grafica localizzata non impedisce di completare la review della
pagina, ma la candidata non diventa reference gold senza la conferma umana.

Il confronto PP-OCRv5 ha prodotto CER `0.026440` e WER `0.090909`, con 5/5
controlli di identità superati. Sono metriche diagnostiche di una pagina in prosa;
le metriche strutturali del profilo `leader_list_report` sono state escluse perché
il profilo non è adatto. La reference porta il campione T41 a cinque pagine, ancora
insufficienti per fissare una soglia: completare il campione stratificato e
preservare `00072`/`00900` come holdout. È disponibile il preflight page-level
`memoria documents ocr-review`: ricalcola il candidate assessment e l'audit
visuale dal TIFF, poi rivalida layout e disposition prima di preparare
un'eventuale coda manuale. Richiede i sidecar lexical review/layout/ledger/
disposition già prodotti e non rilancia l'OCR. Richiede inoltre `--tesseract-evidence`
e `--comparison`: il gate ricalcola il confronto tra evidence correnti
`paddle-ocr-v5` e Tesseract, ne verifica identità pagina/TIFF, percorsi e SHA-256,
e blocca report mancanti, obsoleti o incoerenti. L'accordo o il disaccordo resta
diagnostico e non sceglie una trascrizione. La coda manuale non equivale a gold;
`machine_pass` e auto-validazione restano disabilitati.

Anche `memoria documents ocr-review-scaffold` richiede gli stessi argomenti
`--tesseract-evidence` e `--comparison`. Prima di generare lexicon review, crop
e template incompleti verifica il confronto sugli stessi byte e lega path/digest
dei due artefatti al `scaffold-manifest.json`. Preview non scrive; `--apply`
crea solo nuovi sidecar e crop. Le osservazioni visuali, il layout e le
disposition richiedono ancora revisione; il confronto non le sostituisce.

Per collegare output Tesseract gia' esistenti alle pagine raw di T36 usare
`memoria documents ocr-tesseract-from-t36 --manifest <t36-manifest.json>
--processed-text page_id=<ProcessedDocumentText.json> ... --output-dir
<nuova-directory>`. Ripetere `--processed-text` per ogni pagina. La CLI verifica
che la variante sia full-page/raw e byte-identica al TIFF single-frame, e che
digest e provenance dei testi processati corrispondano. Preview non scrive;
`--apply` crea un nuovo package evidence con `run-manifest.json`, dove
`pages[].evidence.path` identifica l'output da passare a
`--tesseract-evidence page_id=path` nel package di review. Tesseract deve essere
gia' stato eseguito: questo raccordo non avvia OCR e l'evidence resta
diagnostica/non revisionata.

Per comporre T36/T37 e la preparazione page-level usare
`memoria documents ocr-review-package` con `--page-profile page_id=profile`,
`--tesseract-evidence page_id=path` e `--lexicon page_id=path` ripetuti per ogni
pagina; `--glossary page_id=path` e' opzionale. Questa CLI accetta solo la
variante T36 `raw` se manifest e digest confermano che i byte coincidono col TIFF
originale, e verifica che il TIFF abbia un solo frame prima di aggiungere il
locator 0 alle copie detached di review. Gli artifact sorgente T36/T37 e i loro
identificativi di trasformazione non vengono riscritti. Preview non lascia
artifact persistenti; `--apply` richiede una directory nuova. Il risultato e'
un template incompleto `unreviewed`: confronto e package non attestano accuratezza
e non sostituiscono review visuale, audit layout o disposition umane.

Dopo aver completato e verificato i sidecar umani, il gate aggregato si esegue
con `memoria documents ocr-review-batch --manifest <package-manifest.json>
--output <batch-review.json>`. Il comando valida path e SHA-256 dei dieci ruoli
page-level, ricalcola `ocr-review` per ciascuna pagina e continua anche se una
pagina risulta bloccata. Senza `--apply` mostra il report in preview; con
`--apply` scrive soltanto il report nuovo, esterno al package e al repository.
Non modifica sidecar e non promuove risultati.

Il percorso WSL e' distinto dall'eventuale installazione Ollama Windows:
non inferire che WSL sia assente o inutilizzabile da un errore di enumerazione
WSL nel sandbox. Per provider, invocazione `wsl -e curl` ed esempio d'uso,
seguire `memoria-engine/docs/stato-implementazione-meta-motore.md`. Per le
metriche dei modelli visuali consultare la valutazione T41 nella roadmap e il
checkpoint dei risultati; non sostituire il runtime documentato con l'istanza
Windows solo perche' questa e' visibile dal terminale corrente.
La prova sintetica T41 di `llava-llama3` registrata in
`../roadmap/02-technical-roadmap.md` ha misurato una configurazione specifica
con molte aggiunte; non e' una conclusione sui VLM in generale. La documentazione
registra anche che `llama3.2-vision` era incompatibile con Ollama 0.33.2. Qwen3-VL
e GLM-OCR sono alternative candidate, non risultati convalidati per questo
corpus. Prima di usare qualsiasi modello per triage reale, controllarne
disponibilita'/compatibilita' nel WSL e valutarlo con lo stesso benchmark contro
reference gold, per lingua e tipo di pagina. Nessun risultato vendor o fixture
sintetica autorizza auto-accettazione.

Gli alert lessicali, i disaccordi OCR e le regioni non sono equivalenti alle
incertezze reali. Il report deve indicare: forme uniche controllate, alert
classificati, dubbi residui distinti e numero di decisioni richieste. Non
presentare un totale di azioni manuali finche' gli alert non sono stati
deduplicati e classificati.

Auto-accettazione e' una decisione separata. Non definire una soglia da una
singola pagina o da fixture sintetiche. Calibrare e verificare soglie per
lingua e tipo di documento su reference gold, misurando omissioni, aggiunte,
errori testuali e fedelta' strutturale; mantenere holdout separati. Finche' il
gate non e' validato, la pipeline produce candidati non verificati e non
reference `human_verified`.

## Glossario militare versionato e traduzioni candidate

Le abbreviazioni e i termini militari non vanno mantenuti in un Markdown
separato come fonte applicativa. Il glossario operativo e' una risorsa JSON-LD
`MilitaryGlossary` in `memoria-knowledge/glossary/military/`; ogni voce deve
avere un `@id` stabile, la forma originale, eventuali alias/abbreviazioni,
`translation_it`, fonti esterne e `review_status`. Le fonti documentano la
lettura proposta, ma non trasformano automaticamente una menzione OCR in un
fatto storico.

Per ricalcolare le menzioni di una pagina usare il comando preview-first:

```powershell
memoria documents glossary-preview `
  --structure <DocumentStructure.json> `
  --glossary <MilitaryGlossary.jsonld> `
  --output <CandidateMilitaryGlossaryMentionSet.jsonld>
```

Il comando deve ricevere una risorsa glossario esplicita e conserva nel
risultato `glossary_resource`, `glossary_version`, `glossary_digest`, gli ID
delle voci, `source_region_ids` e la provenance della pagina. Senza `--apply`
non scrive; con `--apply` crea un nuovo preview. Un output identico viene
saltato, mentre un output già esistente ma diverso deve essere rifiutato.

Le menzioni prodotte sono sempre candidate, `unreviewed`,
`preview_only`, senza abilitazione a `EvidenceClaim` o a risoluzione di
unita'/presenza territoriale. La forma OCR originale resta invariata; lo
scioglimento italiano va mostrato come annotazione derivata. Se una sigla e'
spezzata dalla struttura tabellare, non ricostruirla silenziosamente come
testo sorgente: registrare la provenienza delle regioni coinvolte e mantenere
la ricostruzione manuale in una copia di lettura non canonica.

Quando cambia il glossario, produrre un nuovo preview con nuova versione e
digest. Il diff tra versioni, la migrazione delle revisioni umane e qualsiasi
promozione canonica richiedono un incremento separato e non sono impliciti nel
ricalcolo.

T37 e' completato: i due profili emettono blocchi con provenance e Markdown
derivato da fixture OCR sintetiche; i sei test mirati e la review indipendente
finale sono PASS. Il passo candidato e' T38, subordinato a una reference umana
verificata prima di qualsiasi metrica su scansioni reali. Il feedback visivo
T36 (preferenza per `contrast-x1.8`; overview ritagliati) riguarda gli
artefatti e non convalida trascrizioni OCR o accuratezza.

Il sotto-incremento offline T38 `t38-human-reference-contract-offline-metrics`
e' completato: `OcrPageReference` page-scoped e evaluator misurano CER/WER,
coverage/invenzioni, ordine e tipi strutturali, e pairing label-valore. Ogni
risultato conserva la provenance OCR completa e l'anchor stabile della pagina
originale emesso da T36; crop e varianti restano distinguibili. L'eleggibilita'
per misure reali richiede audit `human_verified`, reference verificata e
identita' della pagina corrispondente. I 17 test e la review indipendente
finale sono PASS con fixture sintetica; questo dimostra solo determinismo,
non accuratezza OCR. La misurazione reale della pagina 00028 e dei crop 00026
resta in attesa di reference umana verificata; T39 resta condizionale a errori
misurati con tale reference.

### Lezione operativa T41: gate e confronto non equivalgono ad accuratezza

Nel run fresco della pagina `00598`, Tesseract ha superato il proprio gate di
confidence ma ha ottenuto WER `0.288973` rispetto alla reference confermata.
Una pagina `00750` si e' invece fermata prima della registrazione per confidence
insufficiente; `00150` non era compatibile col frame richiesto dal comparatore.
Questi esiti mostrano che il gate attuale misura la processabilita' del run,
non la correttezza della trascrizione, e che le incompatibilita' vanno lasciate
bloccate invece di forzare un confronto. I dettagli e gli hash sono in
`../current-next-increment.md` e nella decisione
`../ocr-low-manual-review-architecture.md`.

Prima di presentare dubbi a una persona, completare il confronto pagina/crop,
allineare le letture per blocco e verificare la candidata esatta con il lessico
locale e i glossari disponibili. Le correzioni sostenute dall'immagine o da
fonti esplicite vanno applicate alla candidata; le domande devono contenere solo
decisioni ancora irrisolte e vanno raggruppate per voce, non per regione OCR.
Prima del controllo lessicale, ricomporre i token separati dalla segmentazione
per righe (inclusi i trattini tipografici a fine riga) nella candidata di lettura;
classificare poi gli alert sul testo esatto ricomposto. Il totale degli alert del
lessico resta diagnostico e non diventa un numero di decisioni manuali.
La confidence, l'accordo fra motori, il numero di regioni e gli alert lessicali
non sono conteggi di errori o azioni umane. Prima di processare decine di pagine
serve il runner batch pilotato da manifest, con rapporto e stato fail-closed per
pagina; l'adapter Tesseract corrente e' ancora una funzione Python, non un
runner batch. Nessun risultato del pilot abilita auto-pass: la soglia va
calibrata e verificata su gold e holdout separati, includendo errori strutturali
e copertura visiva indipendente.
