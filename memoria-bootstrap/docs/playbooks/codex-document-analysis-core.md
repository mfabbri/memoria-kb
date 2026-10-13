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
   umana, non per regione OCR, e chiedere in un solo passaggio una conferma
   page-level del candidato esatto.

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
La confidence, l'accordo fra motori, il numero di regioni e gli alert lessicali
non sono conteggi di errori o azioni umane. Prima di processare decine di pagine
serve il runner batch pilotato da manifest, con rapporto e stato fail-closed per
pagina; l'adapter Tesseract corrente e' ancora una funzione Python, non un
runner batch. Nessun risultato del pilot abilita auto-pass: la soglia va
calibrata e verificata su gold e holdout separati, includendo errori strutturali
e copertura visiva indipendente.
