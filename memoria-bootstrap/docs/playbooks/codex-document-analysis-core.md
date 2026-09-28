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
