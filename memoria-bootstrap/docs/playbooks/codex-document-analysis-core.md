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

Questi comandi preparano i pacchetti Python e non scaricano i pesi OCR. Nella
sessione i modelli erano già scaricati ed estratti sotto
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
   `source_region_ids`.
6. Introdurre un VLM soltanto su crop ambigui se una reference umana mostra un
   vantaggio misurabile. Nessun page-to-Markdown libero.
7. PP-StructureV3 e Docling restano comparatori; non aggiungerli al runtime
   corrente senza un difetto misurato che giustifichi la dipendenza.

Il quality gate OCR corrente misura processabilita' tecnica, non accuratezza.
Non usare `accepted` come sinonimo di testo affidabile o revisionato.

Prossimo incremento: T36. Il pilot resta limitato ai due TIFF guida e non anticipa T37-T40.
