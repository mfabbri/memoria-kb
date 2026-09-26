# Current Next Increment

## Chiusura smoke test dalla root project-local - 2026-09-26

Il runner PP-OCRv5 è stato eseguito usando esclusivamente:

- asset: `D:\CaDiMalanca\me.mo.ri.a-kb-runtime\ocr-assets\`;
- cache: `D:\CaDiMalanca\me.mo.ri.a-kb-runtime\ocr-cache\`;
- output: `D:\CaDiMalanca\me.mo.ri.a-kb-runtime\ocr-runs\t41-project-local-smoke-20260926\`.

Lo smoke test su `00007` è riuscito con 51 regioni e latenza `44231.912 ms`.
Manifest, raw prediction e structured evidence sono JSON validi e dichiarano
`cache_policy: project_local_only`. Durante la normalizzazione il campo
opzionale `rec_boxes` è risultato non allineato a `rec_texts` ed è stato
escluso fail-safe; l'evento è registrato nel manifest. Nessuna accuracy,
CER/WER o promozione è stata calcolata.

Il prossimo passo è raccogliere reference page-scoped esterne e confrontare
PP-OCRv5 project-local con Tesseract.

## Chiusura migrazione asset OCR project-local - 2026-09-26

È stata creata la root persistente fuori dal repository:
`D:\CaDiMalanca\me.mo.ri.a-kb-runtime\`.

Sono stati copiati `PP-OCRv5_mobile_det_infer`,
`latin_PP-OCRv5_mobile_rec_infer`, `tessdata` e i tre artefatti dello smoke
test T41. Il controllo ha verificato 52 file con SHA-256, senza mismatch. Il
manifest di migrazione è
`D:\CaDiMalanca\me.mo.ri.a-kb-runtime\migration-manifest.json`.

Le sorgenti sotto `C:\Users\info\AppData\Local\MeMoRiA\` sono state
conservate e nessun TIFF o file del repository è stato modificato. Il prossimo
passo è configurare il runner per usare esclusivamente la nuova root e
rieseguire uno smoke test, prima del confronto con reference page-scoped.

## Chiusura requisito root project-local OCR - 2026-09-26

È stato formalizzato il vincolo che venv/runtime, versioni, pesi, cache,
`tessdata`, output di run e manifest OCR siano locali al progetto, sotto una
root persistente dichiarata e associata a Me.Mo.Ri.A. `Temp` e cache utente
implicite non sono dipendenze operative ammesse.

Gli asset grandi o operativi restano fuori dal repository Git; root, versioni,
hash e provenance devono essere configurabili e verificabili. In questo
micro-incremento non sono stati spostati o scaricati file e non sono stati
modificati TIFF, dati storici canonici, profili o claim.

Il prossimo incremento runtime separato dovrà migrare e verificare gli asset
attuali da `C:\Users\info\AppData\Local\MeMoRiA\ocr-assets` e
`C:\Users\info\AppData\Local\MeMoRiA\ocr-runs` verso la root dichiarata,
preservando versioni, hash e provenance. Dovrà inoltre eliminare ogni
dipendenza operativa residua da `Temp` o cache utente implicite.

## Chiusura smoke test PP-OCRv5 - 2026-09-26

I pesi PP-OCRv5 erano già installati nella posizione persistente
`C:\Users\info\AppData\Local\MeMoRiA\ocr-assets\`; il controllo precedente
aveva considerato soltanto la cache temporanea. Lo smoke test su
`T314-1275-00007.tif` è riuscito con PaddlePaddle `3.3.0`, PaddleOCR `3.7.0`,
CPU e `enable_mkldnn=false`.

Il run ha prodotto 51 regioni in `41925.245 ms` e ha scritto manifest, raw
prediction e structured evidence in
`C:\Users\info\AppData\Local\MeMoRiA\ocr-runs\t41-ppocrv5-smoke-20260926`.
Gli hash di sorgente, modelli e output sono nel manifest. PaddleOCR ha
ridimensionato internamente la pagina al limite effettivo `max_side_limit=4000`;
non sono state calcolate accuracy, CER/WER né claim storici.

Il prossimo passo è raccogliere reference page-scoped esterne per un
sottoinsieme del campione T41 e confrontare PP-OCRv5 con Tesseract.

## Chiusura preflight runtime PP-OCRv5 - 2026-09-26

Il preflight iniziale aveva verificato solo la cache temporanea e aveva quindi
segnalato erroneamente l'assenza dei pesi. Una ricerca successiva ha trovato
le directory persistenti nella cartella Me.Mo.Ri.A; il runtime locale importa
PaddlePaddle `3.3.0` e PaddleOCR `3.7.0`.

`C:\Users\info\AppData\Local\Temp\memoria-ppocr-v5-20260919\models\PP-OCRv5_mobile_det_infer`

`C:\Users\info\AppData\Local\Temp\memoria-ppocr-v5-20260919\models\latin_PP-OCRv5_mobile_rec_infer`

Il runner PP-OCRv5 può quindi essere avviato usando i pesi persistenti. Non
sono stati eseguiti download o installazioni; lo smoke test successivo ha
confermato l'inferenza su `00007`. Restano da raccogliere reference
page-scoped per il confronto con Tesseract.

## Chiusura T41 pilot OCR su 10 pagine - 2026-09-26

Dal percorso corretto `P:\Comune\Me.Mo.Ri.a\documenti_da_processare\foto\T314 R1275`
sono state selezionate 10 pagine stratificate: `00007`, `00024`, `00072`,
`00150`, `00312`, `00415`, `00598`, `00750`, `00900`, `01000`. Le pagine
`00026` e `00028` sono state escluse perché già analizzate.

La delega custom si è interrotta prima dell'avvio, senza output; il fallback
delimitato ha completato Tesseract `deu` su 10/10 TIFF e ha prodotto TSV raw
solo nella directory temporanea esterna
`C:\Users\info\AppData\Local\Temp\memoria-t41-ocr-calibration-20260926`.
Non sono stati modificati TIFF o repository. PP-OCRv5 non è stato eseguito in
questo pilot; non sono state calcolate accuracy, CER/WER o promozioni senza
reference page-scoped.

Il prossimo passo candidato è raccogliere reference page-scoped esterne per
un sottoinsieme del campione e ripristinare/verificare il runtime PP-OCRv5
prima di un confronto tra engine, crop o trasformazioni.

## Preflight T41 - disponibilita' campione OCR - 2026-09-26

Il percorso esterno dichiarato contiene due sole pagine TIFF reali (`00026` e
`00028`), i due sidecar e output OCR/Markdown derivati. Non e' quindi
disponibile il campione minimo di 8-10 pagine richiesto dalla calibrazione T41.

Il preflight e' stato read-only: nessuna immagine e' stata modificata, nessun
nuovo run OCR e' stato avviato e la riga 5 di `00026` non viene ripetuta. Per
avviare T41 servono almeno altre 6-8 pagine reali, con identita', hash e
reference page-scoped esterna al repository per il sottoinsieme di calibrazione.

## Chiusura T41 - calibrazione OCR stratificata - 2026-09-25

La roadmap ora delimita un protocollo in due fasi: 8-10 pagine iniziali e,
solo dopo, 30-50 pagine esplorative stratificate per leggibilita', lingua e
layout. Il confronto previsto copre Tesseract, PP-OCRv5, crop/tile e
trasformazioni, con reference umane page-scoped mantenute fuori dal repository.
CER/WER, coverage, omissioni, invenzioni, geometrie, ordine e latenza restano
metriche di calibrazione; calibrazione e holdout vanno separati prima
dell'estensione. Nessuna promozione automatica o claim di accuratezza e' stato
introdotto e nessun testo reale e' stato copiato.

## Chiusura T40 checkpoint structured persistente - 2026-09-25

Il batch `documents structure` ora preflighta un manifest
`StructuredMarkdownCheckpoint` versione `1.0`, con root, profilo,
`checkpoint_id` e numero di evidenze. La preview espone il manifest che sarebbe
creato senza scrivere file; `--apply` lo crea in modo esclusivo e un rerun con lo
stesso batch lo riconosce come compatibile. Un manifest esistente con root,
profilo, digest o conteggio diversi viene diagnosticato e blocca l'apply senza
sovrascriverlo o produrre Markdown aggiuntivo.

I 5 test offline di `tests.test_document_structure_cli` sono PASS. Le fixture
sono esclusivamente sintetiche; sono rimasti invariati contratto OCR, Markdown
derivato, TIFF, profili, claim e fatti verificati. Il manifest non introduce
resume parziale o batch massivo.

## Chiusura sessione 2026-09-22 - stato OCR corretto

Confermato che la riga 5 del crop `00026` non e' lavoro pendente: reference
umana, confronto T38 e metriche sono gia' stati completati. Il candidato OCR
resta non approvato, ma l'analisi non va ripetuta.

La sessione si chiude senza modifiche runtime. Il planner mantiene selezionato
il prossimo micro-incremento T40 sul manifest persistente del checkpoint
structured, con `next_action: resume`; la delega verra' avviata solo nella
sessione di implementazione.

## Selezione sessione 2026-09-22 - prossimo incremento T40

Ricalcolato il prossimo micro-incremento dopo la chiusura del checkpoint
in-memory: manifest persistente del checkpoint structured, con preflight,
apply esplicito, creazione esclusiva, rerun idempotente e diagnosi dei mismatch
senza sovrascrittura. Il manifest non abilita ancora resume parziale, retry OCR o
batch massivi.

Il routing intenzionale e' `medium / mmr_implementer / gpt-5.6-terra / medium`.
Gli strumenti di delega sono disponibili; la precedente voce "Nessuna delega
custom disponibile" resta nella traccia storica e non descrive questo candidato.

# Chiusura sessione 2026-09-22 - checkpoint batch structured T40

Il report di `documents structure` ora espone `checkpoint_id` SHA-256 e
`checkpoint_item_count`. Il digest deriva dai path relativi ordinati e dai byte
delle evidenze `*.evidence.json`; resta in-memory, non scrive un file checkpoint
e non cambia preview/apply, idempotenza, error isolation o provenance.

I 4 test mirati passano. Il test dedicato verifica che il checkpoint resti
stabile tra preview/apply/rerun e cambi quando cambia un'evidenza. Sono state
usate solo fixture sintetiche; nessun documento reale, profilo, claim o fatto
verificato è stato modificato.

## Selezione sessione 2026-09-22 - T39 resolver visuale preview-only

Il risultato T38 sulla riga ambigua di `00026` soddisfa l'ingresso condizionale
di T39: esiste un errore misurato, ma non ancora un beneficio dimostrato di un
resolver visuale. Il micro-incremento corrente definisce solo il contratto
preview-only e il test con resolver iniettato; non effettua chiamate live e non
promuove o corregge automaticamente il candidato OCR.

Il contratto T39 e' completato: il resolver riceve crop, candidato OCR e
provenance page-scoped e puo' restituire solo testo o `[illeggibile]`. I 4 test
mirati passano. L'integrazione con un VLM reale resta fuori scope e non e'
giustificata finche' un confronto verificato non dimostra beneficio.

## Chiusura T40 CLI strutturata - 2026-09-22

Il comando `documents structure` consuma solo `OcrPageEvidence`, ricostruisce
`DocumentStructure` e produce Markdown derivato. La modalita' predefinita e'
preview read-only; `--apply` crea output mancanti in modo esclusivo e il run
ripetuto li salta. I 3 test mirati passano su fixture sintetiche.

Il report ora include conteggi per stato, `duration_ms` e
`throughput_items_per_second`, mantenendo error isolation e provenance senza
scritture implicite.

## Selezione sessione 2026-09-22 - intake reference 00026

T38 e T38a runtime sono completati. La reference umana della riga 5 di
`T314-1275-00026` è già stata valutata e confermata insieme all'operatore,
usando un crop prodotto dal pilot T36. Il manifest registra pagina originale,
hash, variante e bbox; il testo umano non viene copiato nel repository.

La reference resta separata da OCR e suggerimenti. Il confronto T38 già
registrato sulla riga restituisce CER `0.825`, WER `1.0`, coverage `0.0` e
invention rate `1.0`; il candidato resta non approvato. T39 rimane condizionale.

## Selezione sessione 2026-09-22

Il prossimo micro-incremento è la raccolta page-scoped della reference umana
per un solo crop rappresentativo di `00026`, seguita dalla valutazione offline
T38. Il testo umano non viene copiato nel repository: servono conferma,
coordinate, hash e identità della pagina originale. T39 resta condizionale a
errori misurati; T40 non viene anticipato.

La reference umana della riga 5 del crop è stata confermata in conversazione;
il testo non viene copiato nel repository. Il report T38 è già stato verificato;
il prossimo passo è mantenere questa provenance nel passaggio successivo.

T38a è ora formalizzato nella roadmap: ranking lessicale offline, raw OCR
immutato, suggerimenti provenance-safe e decisione umana separata. I dizionari
reali restano input esterni; le fixture del motore sono sintetiche.

## Chiusura T38a 2026-09-22 - ranking lessicale offline

Il contratto `LexiconEntry` e `rank_ocr_candidates` producono suggerimenti
deterministici per token, con distanza edit, soglia esplicita, provenance della
voce (`category`, `source_id`, `version`) e stato `unreviewed`. Il raw OCR non
viene modificato e nessun candidato viene promosso automaticamente.

I 3 test mirati passano; JSON planner e `git diff --check` sono PASS. Le fixture
sono sintetiche: non sono state usate trascrizioni o dizionari storici reali e
non si dichiara accuratezza OCR. Il prossimo passo resta la reference
page-scoped di un crop `00026`; T39 resta condizionale a errori misurati.

## Strategia accettata 2026-09-20 - qualità OCR su larga scala

Strategia approvata dall'utente: iniziare con T36 sui TIFF guida `00028` (pagina
intera) e `00026` (crop rappresentativi), esponendo output, crop e provenance
per la revisione condivisa. Proseguire con T37 (struttura/Markdown deterministici),
T38 (reference stratificata e metriche), T39 (VLM condizionale su crop ambigui,
solo se il confronto con reference dimostra beneficio) e T40 (CLI e batch
progressivo).

Per la calibrazione su scala, il campione iniziale di 30-50 pagine è esplorativo,
non una garanzia statistica; separare calibrazione e holdout e controllare
casualmente anche output non segnalati. Confidence, disaccordo e processabilità
servono solo al triage. Il batch deve mantenere provenance, checkpoint
idempotenti, retry limitati ed error isolation; monitorare throughput, p95,
costo per 1000 pagine e minuti di review per 100. Nessuna soglia numerica o
accuratezza sulle scansioni reali è dichiarata. I fatti pubblicabili richiedono
sempre fonte tracciabile e revisione umana.

## Chiusura T36 2026-09-20 - pilot trasformazioni e tile OCR

Pilot tecnico sui due TIFF guida (3632x6192): byte hash raw uguali agli
originali, prova della fedelta' della copia TIFF ma non della correttezza della
trascrizione; per pagina, quattro varianti full-page (raw/grayscale/contrast/
threshold) e sei tile raw 2400x2400 con overlap 200. Totale: 8 output full-page,
12 tile e 20 output OCR. Provenance e geometrie verificate; review tecnica PASS,
senza rilievi. Il runtime segnala `max_side_limit=4000` anche con 8192
configurato; i tile restano a 2400. Il threshold danneggia soprattutto 00026.
Full-page e tile divergono su parole ambigue, incluso il caso "Vecohis"/"Boden":
non si sceglie ne' promuove una lettura. Confidence piu' alta dopo contrast non
prova accuratezza. Tesseract, LLM o VLM non correggono automaticamente e in
silenzio il testo; un VLM sara' valutato solo condizionalmente su crop ambigui,
dopo una reference umana e se una prova mostra beneficio. Gli output sono in
`%TEMP%\memoria-t36-ocr-transform-pilot-20260920-final` e restano `unreviewed`.
La review visiva utente ha preferito `contrast-x1.8` per entrambe le pagine;
per `00028` le varianti sono tutte ragionevolmente leggibili. Gli overview
`visual-review` mostrano solo la parte alta a sinistra e appaiono ritagliati.
Questa e' una segnalazione sugli artefatti visivi, non una validazione OCR.

## Chiusura T37 2026-09-20 - struttura deterministica e Markdown

Stato: **completato il 2026-09-20**. Sei test mirati T37 sono passati; il
controllo `python -m json.tool` sul planner e `git diff --check` sono PASS. La
review indipendente finale e' PASS.

`DocumentStructure` e' stato introdotto come derivato page-scoped di
`OcrPageEvidence`. I profili espliciti `leader_list_report` e `numbered_report`
usano geometria, ordine verticale, indentazione e pattern semplici. Ogni blocco
mantiene `source_region_ids`; `status` e `structure_confidence` descrivono la
regola strutturale e restano distinti dalla confidence OCR. Il Markdown deriva
solo da questa struttura e annota ogni blocco con la provenance. Materiale
vuoto o non riconosciuto diventa `[illeggibile]` o `unknown`, senza completare
testo. I golden test usano soltanto OCR sintetico: non sono state processate
immagini reali e non e' dichiarata accuratezza. La revisione visiva T36 ha
preferito `contrast-x1.8` per entrambe le pagine; le varianti `00028` sono
state giudicate abbastanza leggibili, mentre gli overview mostravano solo la
parte alta a sinistra e apparivano ritagliati. Questo feedback riguarda gli
artefatti visivi e non verifica il testo OCR o la sua accuratezza. Il rischio
residuo T37 resta limitato a profili verificati con fixture sintetiche, senza
claim di accuratezza su documenti reali. Prossimo candidato: T38, subordinato
alla disponibilita' di una reference umana verificata.

## Chiusura sotto-incremento T38 2026-09-21 - contratto reference e metriche offline

Il micro-incremento `t38-human-reference-contract-offline-metrics` è
completato. `OcrPageReference` lega testo e annotazioni strutturali a una
pagina originale tramite identità stabile; l'evaluator confronta CER/WER,
coverage e invenzioni, ordine/tipo dei blocchi e pairing label-valore. I
risultati mantengono la provenance OCR completa e distinguono la pagina
originale da crop e varianti. L'eleggibilità per misure reali richiede audit
`human_verified`, reference verificata e identità pagina corrispondente.

I 17 test mirati e la review indipendente conclusiva sono PASS; la fixture JSON
è sintetica e valida solo il comportamento deterministico. In seguito alla
chiusura del micro-incremento, l'utente ha fornito e confermato la trascrizione
umana della pagina 00028; il testo non viene copiato nel repository e non sono
ancora state misurate scansioni reali. Alla prossima sessione riprendere dai
crop rappresentativi della 00026, uno alla volta. T39 resta subordinato a
errori misurati su reference verificata.

## Chiusura 2026-09-20 - T35 PP-OCRv5 structured evidence

Stato: **completato il 2026-09-20**.

### Chiusura 2026-09-20

Il contratto conserva per regione testo, confidence, geometria neutra
polygon/bbox, ID stabili, hash e provenance della trasformazione, engine/modello
e lingua. I test offline/injected sono passati e la review è PASS. La stabilità
degli ID è relativa all'ordine dei risultati; non è stata dichiarata accuratezza
OCR su scansioni storiche.

Decisione di riferimento:
`memoria-bootstrap/docs/ocr-structured-evidence-strategy.md`.

### Obiettivo

Portare PP-OCRv5 dal ruolo di adapter benchmark text-only a sorgente di evidenza
OCR strutturata e tracciabile. Il nuovo contratto deve conservare per regione
`text`, `confidence`, `polygon`/`bbox`, lingua, engine/modello, trasformazione e
identificatore stabile. Non deve ancora inferire titoli, paragrafi, tabelle o
Markdown semantico.

### Motivazione

Il benchmark corrente conserva `rec_texts` ma scarta dal contratto applicativo
`rec_scores`, `rec_polys` e `rec_boxes`. Questa perdita impedisce di usare
PP-OCRv5 come base della ricostruzione strutturale. I pilot PP-StructureV3,
Docling e Qwen page-level non hanno dimostrato un vantaggio sufficiente da
giustificare un altro framework nel critical path.

### Write set atteso

- `memoria-engine/code/caduti_fonti_report/document_analysis/` per contratto e
  adapter PP-OCRv5;
- test OCR dedicati sotto `memoria-engine/tests/`;
- documentazione solo se il contratto pubblico cambia.

### Non obiettivi

- nessun VLM/LLM;
- nessuna ricostruzione Markdown;
- nessuna classificazione semantica di layout;
- nessuna modifica ai TIFF originali o al data root;
- nessuna promozione automatica di PP-OCRv5 a verita' archivistica;
- nessuna rimozione del percorso Tesseract legacy.

### Criteri di accettazione

- un payload engine-neutral conserva testo, score e geometria PP-OCRv5 senza
  ridurli a una sola stringa;
- region ID stabili e provenance permettono di risalire alla pagina e alla
  trasformazione applicata;
- il contratto tollera polygon/bbox secondo quanto disponibile dal motore;
- l'import PaddleOCR resta lazy/opt-in e non diventa dipendenza obbligatoria dei
  test standard;
- test offline/injected verificano mapping, ordine e perdita zero dei campi
  strutturali rilevanti;
- nessun renderer Markdown o parser semantico viene aggiunto in T35.

### Validazione minima

Baseline verificata il 2026-09-20:
`python -m pytest -q tests/test_document_ocr_batch.py tests/test_document_ocr_tesseract.py tests/test_ocr_markdown.py`
restituisce `31 passed, 2 failed`. Le due failure sono preesistenti nei fixture
batch che usano il token singolo `OCR` contro il gate a due token. T35 deve
separare chiaramente eventuali regressioni nuove da questa baseline e, se tocca
il gate, correggere test/semantica in un micro-incremento esplicito.

### Stop condition

Chiudere T35 quando l'evidenza PP-OCRv5 e' conservata in modo strutturato e
testabile. Il passo successivo e' T36, dedicato a crop/tiling e trasformazioni
ad alta risoluzione sui due TIFF guida; non anticipare T37-T40.

## Nota operativa 2026-09-19 - ambiente locale PP-OCRv5

Per riprodurre il setup Python su Windows, dalla cartella
`D:\CaDiMalanca\me.mo.ri.a-kb\memoria-engine` usare il venv esistente:
verificare `.venv\Scripts\python.exe`, installare `paddlepaddle==3.3.0` con
l'indice CPU ufficiale `https://www.paddlepaddle.org.cn/packages/stable/cpu/`,
installare `paddleocr==3.7.0` e verificare versioni/import con lo stesso
interprete. Prima dell'invocazione del runner impostare `$env:PYTHONPATH =
'code'`. La sequenza PowerShell copiabile è nel playbook
`playbooks/codex-document-analysis-core.md`.

I pesi non facevano parte dell'installazione dei pacchetti: erano già scaricati
ed estratti sotto `%TEMP%\memoria-ppocr-v5-20260919\models`. Le directory usate
erano detection `PP-OCRv5_mobile_det_infer` e recognition
`latin_PP-OCRv5_mobile_rec_infer`, `en_PP-OCRv5_mobile_rec_infer` e
`eslav_PP-OCRv5_mobile_rec_infer`. Il primo tentativo fallì perché presumeva
percorsi annidati `en\PP-OCRv5_mobile_rec_infer` ed
`eslav\PP-OCRv5_mobile_rec_infer`; verificare i percorsi effettivi. Non è
stato ricostruito un comando affidabile per scaricare i pesi. Non installare
pacchetti nel Python globale e non conservare i modelli nei repository.

## Chiusura 2026-09-19 - benchmark runtime PP-OCRv5

Completato il benchmark runtime sulle sei fixture sintetiche multilingue con
PaddleOCR 3.7.0, PaddlePaddle CPU 3.3.0 e PP-OCRv5 mobile; inferenza CPU con
`enable_mkldnn=false`. Su 66 token di riferimento, output 67, match 65,
omissioni 1 e aggiunte 2: accuratezza `0.970149`, copertura `0.984848`,
completezza `1.0`, invenzione `0.029851`. Metriche per lingua
accuracy/coverage/invention: `ita` `0.944444/0.971429/0.055556` (35 token di
riferimento, 36 output, 34 match); `deu`, `eng` e `rus` `1/1/0` (10/10/10,
11/11/11 e 10/10/10 rispettivamente). Cinque fixture sono perfette; la
fixture italiana degradata ha accuratezza `0.833333`, copertura `0.909091` e
invenzione `0.166667`. Latenze: 1.469-3.959 secondi per fixture. La seconda
esecuzione, con i file `.cache` esclusi dalla provenance dei modelli, ha
restituito gli stessi sei hash di risposta della prima esecuzione valida.

Provenance: SHA-256 manifest
`08a51b197d34400fdc40943ddfa7a681a4a12d4004bc2f348a38ce8346cbf436`;
hash dei pesi rilevatore `afa1820cb16c1fd0dad589d0f8b389139061c1ef6d68019685fd07be997dda5b`,
Latin `53cdc8b481a7394bb108f96d0fb3432b0a8f392e22c7d18f06dbb2d42b8b25f9`,
English `3ec8a97ed6cefe8568d3e2ee90bb193299b566a7661aa4fd52d224b96b59f66b` ed
East Slavic `f11057b05d8517868bca505271278973d706600d9dcc184cbcf5c4512091c32b`.
La verifica locale registra file attesi e hash, non autentica una firma
ufficiale del modello. Corpus solo sintetico e text-only: non sostiene claim
sull'OCR di scansioni storiche, non misura struttura/layout e non seleziona o
promuove uno stack. Prossimo passo candidato: validare un campione limitato di
scansioni rappresentative con trascrizione umana verificata, mantenendo separati
gli output dei motori.

## Chiusura 2026-09-19 - adapter benchmark PP-OCRv5

Completato l'adapter opt-in PP-OCRv5: l'import del runtime PaddleOCR è lazy e
non introduce dipendenze obbligatorie. L'esecuzione richiede directory di
modello locali con `inference.json`, `inference.pdiparams` e `inference.yml`;
la selezione linguistica mappa `ita`/`deu` a Latin, `eng` a English e `rus` a
East Slavic. Il report registra hash degli asset e versioni Paddle/PaddleOCR.
Le immagini sono lette dalle fixture locali; output e report restano in memoria,
senza scritture. L'interfaccia injected e' stata verificata dal benchmark
runtime, completato nella nota soprastante. Non ne deriva una selezione o
promozione dello stack.

## Chiusura 2026-09-19 - LLaVA con prompt per lingua

Completata la valutazione di `llava-llama3:latest` su sei fixture
sintetiche, con Ollama 0.33.2 (digest
`44c161b1f46523301da9c0cc505afa4a4a0cc62f580581d98a430bb21acd46de`), engine
`ollama-vision` su localhost, timeout 120 s, `num_ctx=4096`,
`num_predict=256`, `think=false`, `temperature=0`. Riferimenti/output/match:
66/193/38; accuratezza 0.196891, copertura 0.575758, invenzione 0.803109.
Per lingua: `ita` 0.657143/0.657143/0.281250 (3 fixture: accuracy/coverage/
invention); `deu` 0.363636/0.400000/0.636364; `eng` 1/1/0; `rus` 0/0/1 (una
fixture ciascuno per `deu`, `eng`, `rus`). Prompt per fixture registrati via
SHA-256: clean-text `1f1134efd78479978bbeba3f98a44e04c858d4266c0e14fd841ef4aa9cf16181`,
risposta `1d3ecf83612720e6ef0308c97158bab23a3d4c9983e3098d85e2661f66bf711c`,
23859.808 ms; degraded-text stesso prompt, risposta
`88e05129b8d7c74f0d31f7cf6d04911159d45c32eb400ce6f1ed9246869b5dab`,
12609.975 ms; mixed-table-layout stesso prompt, risposta
`602efe9e1584ecf044965e850e1ded8d26ec8c4b996ec8c51b733e361df438a8`,
11742.573 ms; german-text prompt
`edf845ecb8bde0fb2d047fed411bd95e8853660e118b49a55927adb238f24f83`, risposta
`84e697e4f17ee1c50bbecd736b653ab90382c3387d3edcf22cbd55eece69015b`,
12495.317 ms; english-text prompt
`3aa64c709d67eeef5348b745cb0322312e571a72c7cdba1e0f6189663750524d`, risposta
`bda71f65e5161ca833b61769cb5b64a1f1a86b0d52a2bd1da65a8c698468154e`,
10771.983 ms; russian-text prompt
`f4b0b472bd127b6dca36e552f6fe5461b713c04cb1a1fa1bd4159412165ee27b`, risposta
`ce03d538e7014940483b7ea830f6e08fb047c64ce5041f259150fb91e35eede4`,
55281.920 ms.

Il code review è PASS; per istruzione non sono stati aggiunti o eseguiti test.
Paddle/PaddleOCR non è installato; LLaMA 3.2 Vision è installato ma
incompatibile con Ollama in uso e non è stato eseguito; Qwen3-VL non è
disponibile. Valutazione solo sintetica: nessuna scansione reale, claim o
selezione/promozione di engine. Prossimo candidato: integrazione PP-OCRv5 e
modelli vision disponibili nel benchmark.

## Chiusura 2026-09-19 - confronto Tesseract 5.5.3

Completato il confronto offline del corpus di sei fixture sintetiche con
Tesseract 5.5.3.20260724, OEM 1 e PSM 6. Accuratezza testuale: `ita` 0.714286
(3 fixture; baseline Tesseract 5.5.0: 0.685714), `deu` 1.0, `eng` 1.0 e
`rus` 1.0 (una fixture pulita ciascuna); totale 0.848485 su 66 token di
riferimento. I language pack `deu` e `rus` provengono dal repository ufficiale
`tessdata_fast` (`main`), con SHA-256 rispettivamente
`19D219BBB6672C869D20A9636C6816A81EB9A71796CB93EBE0CB1530E2CDB22D` e
`E16E5E036CCE1D9EC2B00063CF8B54472625B9E14D893A169E2B0DEDEB4DF225`; i pack
sono stati staged in Temp e la prova ha usato `TESSDATA_PREFIX`. Installer del
rilascio ufficiale:
https://github.com/tesseract-ocr/tesseract/releases/download/5.5.3/tesseract-ocr-w64-setup-5.5.3.20260724.exe,
SHA-256 `BEE9E3434BD94FD65387D9BE28CD467A41F61B1275383B55B0F59A1331270AE4`
(corrispondente al manifest ScoopInstaller/Main). Il certificato del
firmatario risultava scaduto/non verificabile: questo caveat di provenance
resta esplicito.

Valutazione limitata a fixture sintetiche: nessuna scansione reale, claim
approvato o stack OCR selezionato/promosso. Il punto 2 della sequenza roadmap
è chiuso; prossimo candidato: punto 3, integrare PP-OCRv5 e i modelli vision
disponibili nel benchmark offline.

## Nota di sessione 2026-09-19 - fixture OCR multilingue

Il benchmark offline ora dichiara lingua e metriche separate per italiano
(`ita`), tedesco (`deu`), inglese (`eng`) e russo (`rus`), con una fixture
cirillica sintetica. Il report conserva lingua, hash della fixture e, quando
Tesseract usa la selezione automatica, la lingua effettiva per ogni comando.
Sul baseline locale Tesseract 5.5.0.20241111, OEM 1 e PSM 6: `deu`, `eng` e
`rus` sono 1.00 sui rispettivi casi puliti; i tre casi italiani restano 0.686
aggregati, incluso testo degradato e tabella. Sono risultati di sole fixture
sintetiche, non una selezione di engine né una stima per le scansioni reali.

Il confronto Tesseract 5.5.3 è stato completato nell'incremento successivo;
il prossimo candidato è integrare PP-OCRv5 e i modelli vision disponibili sul
medesimo corpus multilingue.

## Nota di sessione 2026-09-19 - sweep OCR LLM locale

Calibrato LLaVA (`llava-llama3:latest`, Ollama 0.33.2) sui tre fixture
sintetici: baseline `temperature=0`, `num_ctx=4096`, `num_predict=256`, prompt
italiano = 0.686 accuratezza; la ripetizione ha restituito gli stessi hash.
`num_ctx=8192` non ha cambiato output. Il prompt italiano con marker
`[illeggibile]` ha raggiunto 0.714, ma il fixture misto resta a 0.50; il prompt
inglese scende a 0.622. `temperature=0.2` non migliora l'aggregato e non e'
ripetibile a parita' di parametri. Tesseract 5.5.0, ita/OEM 1/PSM 6 ottiene
0.686 (clean 1.00, degradato 0.75, misto 0.357). Llama 3.2 Vision e' installato
ma incompatibile con Ollama 0.33.2; Qwen3-VL non e' installato. Risultati solo
sintetici: nessun modello vision e' promosso per scansioni reali. Tesseract e il
quality gate restano il percorso primario; il VLM e' una seconda lettura da
tenere separata. Prossimo passo: confronto su pagine con trascrizione umana
verificata, poi valutazione di crop/tiling.

## Nota di sessione 2026-09-19 - marker per testo OCR non disponibile

L'export Markdown per pagina conserva ora le righe OCR senza testo alfanumerico
con il marker letterale `OCR text unavailable`, mantenendo ID riga/regione e
bounding box senza esporre punteggiatura o valori nulli come trascrizioni. Il
report aggiunge `unavailable_text_lines` e mantiene `skipped_empty_lines` a 0
per compatibilità. Test OCR Markdown: 9/9; quality review indipendente PASS;
planner JSON valido e `git diff --check` pulito. Nessun runtime OCR, soglia o
contenuto storico è stato modificato.

## Nota di sessione 2026-09-18 - valutazione Qwen e confronto appaiato

Aggiornamento: il tag `qwen3-vl:4b` era già installato; nessun download è
stato eseguito. Con Ollama 0.34.2, digest
`1343d82ebee38e26a4dd6b0180b915eb91550184e67c505dea97509571c8f683`, lo
stesso prompt (SHA-256
`04f17ecf2f4bad0f35e24eb34cd74593967434c4e86a7114c33ded07fad85dab`),
`num_ctx=8192`, `num_predict=128` e `think=false`, Qwen 4B ha restituito output
vuoti su tutte e tre le fixture sintetiche: 0/35 token, metriche aggregate
0.0, latenze 67,671 secondi, 56,684 secondi e 56,133 secondi. Sugli stessi TIFF diretti canonici
`T314-1275-00026.tif` e `T314-1275-00028.tif` ha restituito 0 caratteri in
43,995 secondi e 43,693 secondi. I TIFF originali misurano 3632×6192 pixel e
22.489.956 byte; applicando a entrambi la procedura dichiarata di conversione
RGB e ridimensionamento in memoria al massimo lato 1600, i payload PNG 939×1600
sono rispettivamente 908.614 byte (SHA-256
`4b0c3ac7eff4ea9d6a56954cf5c470c1aeda983fa0517a5a12cbf0bf0b39fde5`) e
849.905 byte (SHA-256
`8ebb1177ea906ed7b8f6993ded0c575b4971090910480402e6535fba0cf053df`).
La conversione Pillow ha decodificato/caricato le immagini, convertito in RGB,
ridimensionato con dimensione arrotondata e codificato PNG in `BytesIO`; nessuna
scrittura è stata eseguita. Il confronto con Qwen 8B riguarda gli stessi TIFF
originali; non è stata verificata l'equivalenza pixel-level dei payload inviati
ai due modelli, quindi non si afferma un confronto sugli stessi payload. Le
differenze di codifica possono spiegare hash diversi, ma non provano da sole
l'equivalenza delle immagini. L'esito qualitativo osservato è uguale a Qwen 8B;
senza ground truth umana validata non si dichiara accuratezza sui TIFF.

Completato `ocr-qwen-offline-benchmark-runner-v1`: l'adapter usa le fixture sintetiche del manifest, invia immagini in memoria a Ollama locale e conserva provenance. Con `qwen3-vl:8b` (digest `901cae73216286ea8c5aba8b46d307ff7188f737285ec500c795a12f05225d28`), Ollama 0.34.2, prompt SHA-256 `04f17ecf2f4bad0f35e24eb34cd74593967434c4e86a7114c33ded07fad85dab`, `num_ctx=8192`, `num_predict=128`, `think=false`, tutti e tre gli output sintetici sono vuoti: 0/35 token di riferimento, con latenze 89,7 s, 81,8 s e 107,9 s. Test mirati 13/13 e quality review indipendente PASS.

Subito dopo e' stata eseguita la prova richiesta con entrambi gli engine sui due TIFF presenti nella directory canonica `P:\Comune\Me.Mo.Ri.a\documenti_da_processare\foto\T314 R1275\test`. Il percorso letterale fornito (`documenti\_da\_processare`) non esisteva; sono stati usati soltanto i due TIFF diretti della directory canonica. Gli originali misurano 3632x6192 pixel e 22.489.956 byte ciascuno; per Qwen sono stati convertiti in memoria in PNG RGB ridimensionati a 939x1600, senza scrivere file. SHA-256 originali: `00026`: `9a150b91cb1793d5c4b014546d73d90c642b4c5d0714f5a3ced1c6dea0ac03af`, `00028`: `661d6b0728033fa0526dcb83b9f4451b237a5fe52d986fc9d7a4f62d1779cab8`. SHA-256 PNG inviati a Qwen: `00026`: `ebeb3aef856fc89604f1f9d3a5afe4c652cb0963fda660c653122ea2bcfcc059`, `00028`: `f9555e62c4d0ac848904764db02a4f310689c18faf98ad3cb7314abc23e99c36`.

Tesseract 5.5.0.20241111 con `ita`, OEM 1 e PSM 6 ha prodotto rispettivamente 1250 caratteri in 3916 ms e 994 caratteri in 2208 ms. Con la lingua `deu` disponibile, sugli stessi file ha prodotto 1054 caratteri in 1417 ms (`00026`) e 922 caratteri in 1517 ms (`00028`). Il campione `00028` appare piu' coerente con il testo tedesco, ma resta rumoroso. Qwen ha restituito output vuoti, rispettivamente in 179230 ms e 66396 ms. Non era disponibile una trascrizione validata da una persona: non si riportano metriche di accuratezza. Il testo prodotto da Tesseract resta rumoroso e non sostiene affermazioni sui fatti. Nessun file sorgente o di output e' stato scritto. Prima di concludere sull'accuratezza, valutare una diversa strategia di input immagini per Qwen o un diverso modello/runtime.

## Nota di sessione 2026-09-18 - runner benchmark Tesseract offline

Completato `ocr-tesseract-offline-benchmark-runner-v1`: l'adapter esegue OCR
sui soli PNG sintetici, valuta il testo e riporta versione, lingua, OEM, PSM e
comandi, senza registrare `ProcessedDocumentText` o scrivere file operativi.
Con Tesseract v5.5.0.20241111, lingua `ita`, OEM 1 e PSM 6, l'accuratezza
testuale è stata 1.00 sul caso pulito, 0.75 sul degradato e 0.36 sul tabellare
(0.69 aggregata). Suite simulata 9/9 e quality review indipendente PASS. Sono
risultati su sole fixture sintetiche; le metriche non misurano layout/struttura
e non calibrano le soglie su scansioni reali. Nessun modello Qwen è stato usato.

## Nota di sessione 2026-09-18 - input raster per benchmark OCR

Completato `ocr-visual-fixtures-provenance-v1`: aggiunti tre PNG sintetici
1200×1600 con testo pulito, degradato e tabella con glifi nelle celle. Il
manifest registra file, dimensioni e trasformazioni; il report conserva SHA-256
delle immagini. La validazione indipendente dei PNG controlla chunk, CRC,
decompressione, dimensioni e filtri; containment fail-closed per traversal e
symlink. Test mirati 6/6 e review indipendente PASS. Nessun OCR/modello invocato;
le metriche restano text-only e non valutano la fedeltà strutturale.

## Nota di sessione 2026-09-18 - fondazione benchmark OCR offline

Completato `ocr-offline-benchmark-foundation-v1`: aggiunti tre casi sintetici
con trascrizione attesa e valutatore deterministico per accuratezza testuale,
copertura, completezza, omissioni e aggiunte, con hash SHA-256 e provenance.
Test mirati 5/5 e quality review indipendente PASS. Manifest e output mancanti
o sconosciuti e ground truth esterni alla directory vengono rifiutati. Il caso
tabella/layout misura soltanto il testo, non fedeltà strutturale o ordine di
lettura. Nessun OCR o modello è stato invocato; le soglie quality gate non sono
state calibrate con fixture sintetiche.

Data: 2026-09-02

## Nota di sessione 2026-09-15 - verified facts preview via CLI

Implementato `memoria review verified-facts --preview`: usa la sessione attiva
oppure la run review raccomandata, legge lo evidence store in sola lettura e
genera `verified_facts.preview.json` e Markdown nella run. Supporta filtri
multi-profilo e output espliciti; non modifica profili canonici, verified facts
definitivi o evidence store. Suite CLI: 20 test passati.

## Nota di sessione 2026-09-15 - prossimo incremento verified facts CLI

Selezionato `review-verified-facts-cli-preview-v1`: portare nella CLI Python
la generazione di `verified_facts.preview.json` a partire da queue e decisioni
compilate. Il comando sarà preview-only, manterrà provenance e revisione umana
obbligatoria e non modificherà profili canonici o evidence store.

## Nota di sessione 2026-09-15 - consolidamento documentale

Consolidate nei playbook e nel decision log le regole riutilizzabili emerse
nella sessione: CLI Python come superficie operativa, percorso esplicito con o
senza run preesistente, e review multi-profilo basata su filtri, ID e
provenance. Nessun codice runtime o dato reale modificato.

## Nota di sessione 2026-09-15 - summary decisioni via CLI

Selezionato `review-decision-summary-cli-v1`: dopo `memoria review decide
--preview`, aggiornare tramite CLI anche `review_decisions_summary.json`,
allineando conteggi e decisioni al payload compilato. Il micro-incremento resta
preview-only e non modifica profili canonici, verified facts o evidence store.

Chiusura: `memoria review decide --preview` ricostruisce ora il summary dalla
queue e da `review_decisions.compilato.json`, mantenendo conteggi, stato,
provenance e validazione coerenti. Coperti conferma, `uncertain`, azione non
ammessa e assenza di scritture canoniche; 25 test mirati/combinati passano.

## Nota di sessione 2026-09-15 - direzione CLI unica

Decisione generale: la destinazione post-MVP è usare solo la CLI Python
installabile `memoria` per discovery, raccolta fonti, processazione, review,
consolidamento e artefatti preview. I wrapper PowerShell restano un ponte
transitorio compatibile; la loro sostituzione avverrà per micro-incrementi
verificabili, senza editing diretto dei JSON operativi.

## Nota di sessione 2026-09-15 - avvio sessione review via CLI

Selezionato `review-start-cli-preview-v1`: introdurre `memoria review start
--preview` per creare la sessione review attiva sulla run raccomandata,
preparando worklist e percorsi coerenti con il workflow esistente. Il comando
scriverà solo artefatti preview della sessione; decisioni, profili canonici,
verified facts ed evidence store restano fuori scope.

Chiusura: implementato `memoria review start --preview` con selezione della run
raccomandata, worklist coerente e comportamento idempotente su sessione già
attiva. I 24 test mirati, help CLI, compilazione Python, JSON planner e
`git diff --check` passano. Nessun profilo, decisione o evidence store è stato
modificato.

## Nota di sessione 2026-09-15 - prossimo incremento CLI operativo

Selezionato `review-decision-cli-preview-v1`: introdurre `memoria review
decide --preview` per registrare una decisione sulla sessione review attiva,
usando numero o ID della worklist e validando le azioni ammesse. Il comando
aggiornerà solo gli artefatti preview previsti dal workflow; profili canonici,
verified facts ed evidence store restano fuori scope. Questo incremento applica
la regola metodologica di evitare l'editing diretto dei JSON operativi.

Chiusura: implementato `memoria review decide --preview` con aggiornamento via
CLI degli artefatti preview di decisione e della sessione attiva. Validazione
item/azione, rifiuto delle azioni non ammesse e assenza di sessione sono coperti
da test; 21 test mirati, compilazione Python, JSON planner e `git diff --check`
passano. Nessun profilo canonico o evidence store è stato modificato.

## Nota di sessione 2026-09-15 - regola operativa CLI

Decisione metodologica: evitare l'editing diretto dei JSON operativi. Le
prossime modifiche dovranno usare la CLI `memoria` o un workflow CLI approvato;
se il comando non esiste, va introdotto prima in un micro-incremento delimitato.
Fixture, test, import/migrazioni controllati ed eccezioni motivate restano i
soli casi ammessi per editing diretto, con validazione e audit.

## Nota di sessione 2026-09-15 - selezione post-MVP

Selezionato il micro-incremento `review-targets-cli-json-output-v1`: aggiungere
un formato JSON esplicito a `memoria review targets`, mantenendo il testo come
default, i filtri multi-profilo, l'ordine deterministico, la provenance e il
confine preview-only/read-only. Il formato strutturato serve a rendere la
coda consumabile da integrazioni e report futuri senza introdurre scritture.
La verifica prevista copre JSON senza filtro, filtro su uno o piu' profili,
nessun match e invariance dell'output testuale.

Implementazione avviata: `memoria review targets --format json` espone il
payload filtrato senza banner testuale; `text` resta il default. Il caso senza
run produce un payload JSON vuoto preview-only, senza scritture.

Chiusura: incremento completato. I 19 test mirati, la compilazione Python, la
validazione JSON del planner e `git diff --check` passano. Nessun file operativo,
profilo canonico, decisione o store è stato modificato.

## Nota di sessione 2026-09-12 - review-targets-cli-profile-filter

Chiuso il filtro CLI `--profile-id` ripetibile per `memoria review targets`.
La vista può ora essere concentrata su uno o più profili senza alterare il
builder, il bilanciamento predefinito o la provenance. Il caso senza match è
gestito come lista vuota, sempre read-only/preview-only. I 16 test della suite
CLI e target passano; pCloud resta in hold.

## Nota di sessione 2026-09-12 - review-targets-cli-read-only-bridge

Chiuso il bridge CLI Python `memoria review targets`: legge la sessione attiva
o la run review consigliata e mostra i target storici con limite e provenance
essenziale. Il comando gestisce anche l'assenza di run senza scrivere artefatti,
creare decisioni o modificare profili/store. Suite CLI e test mirati passano;
pCloud resta in hold.

## Nota di sessione 2026-09-12 - review-targets-multi-profile-balance

Chiuso il secondo micro-incremento del prodotto finale: i batch queue-mode
bilanciano in modo deterministico i target pending tra i profili preferiti e
quelli scoperti nella coda. Gli item gia' decisi restano esclusi; provenance,
limite e output preview-only sono invariati. Test mirati e suite review
correlate passano; pCloud resta in hold.

## Nota di sessione 2026-09-12 - review-targets-idempotent-batches

Chiuso il primo micro-incremento del prodotto finale: la selezione dei target
storici in batch esclude gli item gia' decisi quando la review queue viene
riesportata con stato aggiornato. Il confine resta preview-only, con provenance
invariata e nessuna modifica allo evidence store o ai profili canonici.
Test mirati e suite review correlate passano; il prossimo incremento va
selezionato per estendere il workflow su piu' profili.

## Nota di sessione 2026-09-12 - mvp-narrative-dry-run

La prova asciutta della presentazione finanziatori in sei schermate e' stata
verificata come completata: tutti i blocchi narrativi passano, i guardrail
preview-only restano espliciti e non sono state eseguite scritture o
pubblicazioni. Il gate MVP tecnico e' chiuso; resta una revisione umana del
racconto prima di qualsiasi presentazione esterna. Il prossimo incremento va
selezionato dalla roadmap del prodotto finale.

## Nota di sessione 2026-09-12 - t26-pcloud-read-only-mock-contract

La procedura di sessione ha verificato che il driver pCloud read-only, il
resolver provider-aware e i test mock HTTP sono gia' presenti nel checkout.
T26 e' quindi riconciliata come chiusa per il perimetro offline/mock; l'accesso
live resta in hold e richiede autorizzazione esplicita e credenziali locali.
Nessuna chiamata cloud, scrittura remota o modifica runtime e' stata eseguita.

## Nota di sessione 2026-09-11 - memoria-cli-command-groups

Incremento chiuso nel confine approvato: estratto il solo wiring argparse
`sources` in un leaf dedicato, con handler, patch point, output, formatter,
wrapper PowerShell e comportamento read-only invariati. Il test parser copre i
quattro namespace `sources` e i default compatibili; 43 test diagnostici, 6
test CLI, compilazione Python, JSON e `git diff --check` sono passati. Nessun
dato esterno e' stato coinvolto.

## Nota di sessione 2026-09-10 - priorità roadmap aggiornata

Su richiesta dell'utente, la roadmap assegna priorità a `T34b - Chiusura
operativa della migrazione profili legacy` prima del post-MVP, di Q2 e della
traiettoria cloud. T34 resta chiusa per la fase preview, ma i conteggi dei
candidati, i residui pending, il dry-run, il backup, il rollback e l'eventuale
applicazione canonica autorizzata devono essere riconciliati in un gate
separato. Non sono stati modificati profili canonici né dati esterni.

## Incremento corrente

T34b - Chiusura operativa della migrazione profili legacy.

Obiettivo: riconciliare la coda T34, completare la revisione umana dei casi
pending, verificare dry-run, backup, rollback e audit, quindi applicare soltanto
le operazioni esplicitamente autorizzate.

Gate 3 T34b del 2026-09-10: l'utente ha deciso `1 pending, 2 reject, 3
pending, 4 pending, 5 pending, 6 reject, 7 reject`. La decisione e' stata
registrata nel set esterno `review_decisions_block5e.json` con 4
`needs_review` e 3 `rejected`; `preview_only=true` e
`canonical_profiles_modified=false`. Nessun nuovo profilo e' stato creato e
nessuna patch canonica e' stata applicata.

Gate 4 T34b del 2026-09-11: l'utente ha accettato tutti i 4 casi residui. Le
decisioni sono registrate nel set esterno `review_decisions_block5f.json` con
4 `accepted`; `preview_only=true` e `canonical_profiles_modified=false`.
Nessun profilo canonico e' stato creato.

La revisione dei `CandidateNewProfile` e' completa e T34b e' stata chiusa
operativamente con il Gate 9 dell'11 settembre 2026. Dry-run, backup, audit e
rollback condizionato sono verificati; l'applicazione canonica autorizzata ha
creato soltanto i tre profili previsti e collegato il caso gia' esistente.

Gate 5 T34b del 2026-09-11: il preflight read-only ha verificato che
`memoria-engine` applica `ProfilePatch` a profili JSON-LD esistenti, ma non
fornisce un percorso di materializzazione canonica per i `CandidateNewProfile`
accettati. Sono stati trovati profili esistenti per Bergonzoni Guido, Marciatori
Francesco e Saba Mario; non e' stato trovato un profilo canonico per Tacconi
Rosa. Nessuna scrittura e' stata eseguita.

Questo e' un blocker di contratto/migrazione: prima del dry-run applicativo
serve definire il contratto di creazione dei nuovi profili, la mappa
legacy/source-to-target, il manifest, il backup e il rollback. I quattro
`accepted` restano quindi preview-only.

Gate 6 T34b del 2026-09-11: implementato in `memoria-engine` il contratto
`CandidateNewProfileMaterializationPlan` come artefatto immutabile e
preview-only. Il piano richiede provenance completa, target canonico,
risoluzione `create_new`/`link_existing`/`blocked_collision`, hash, manifest,
rollback metadata e audit. I test coprono i quattro casi T34b: tre
`create_new` e Saba Mario `link_existing`, senza scrittura canonica.

Il prossimo incremento dovra' integrare il piano con gli artefatti reali e il
dry-run operativo. Restano fuori scope la CLI, l'applicazione canonica,
`apply_profile_patch.py`, l'indice e i profili esterni.

Gate 7 T34b del 2026-09-11: il preflight in-memory ha letto la coda reale e
`review_decisions_block5f.json` senza scrivere file. Ha prodotto 4 piani
deterministici: `Marciatori Adriano`, `Tacconi Rosa` e `Bergonzoni Lino` in
`create_new`, `Saba Mario` in `link_existing`. Esito aggregato:
`preview_only=true`, `canonical_profiles_modified=false`,
`canonical_write_count=0`.

I 13 test mirati, `py_compile` e `git diff --check` sono passati. Il prossimo
incremento puo' scrivere soltanto l'artefatto preview e produrre il dry-run
operativo; l'applicazione canonica resta esclusa.

Gate 8 T34b del 2026-09-11: scritti nella run esterna gli artefatti
`candidate_new_profile_materialization_t34b.preview.json` e
`candidate_new_profile_materialization_t34b.dry-run.json`. La verifica ha
confermato 4 piani, `preview_only=true`, `canonical_profiles_modified=false`,
`canonical_write_count=0` e risultato
`ready_for_explicit_canonical_authorization`. Le risoluzioni sono 3
`create_new` e 1 `link_existing`.

Il dry-run e' pronto, ma non autorizza la scrittura canonica: backup, rollback
effettivo e audit post-run restano da eseguire soltanto in un incremento
applicativo esplicito.

Gate 9 T34b del 2026-09-11: applicazione canonica autorizzata completata. Sono
stati creati `Marciatori Adriano`, `Tacconi Rosa` e `Bergonzoni Lino` come
profili minimali `accepted/unpublished`; `Saba Mario` e' stato collegato al
profilo esistente senza scrittura. L'indice e' passato da 57 a 60 profili.
Backup dell'indice, audit JSON/Markdown e rollback condizionato agli hash sono
stati generati. Nessun claim o `verified_fact` e' stato creato.

T34b e' chiusa operativamente. Il prossimo incremento puo' essere selezionato
dalla roadmap del prodotto completo; non sono richieste ulteriori modifiche
canoniche per questi quattro casi.

Stato: priorità selezionata il 2026-09-10; l'implementazione non è ancora
La revisione umana è registrata in `review_decisions_block5e.json` come
T34b chiusa operativamente il 2026-09-11; revisione, piano, dry-run, backup,
applicazione e audit post-run sono registrati negli artefatti esterni.

## Ripresa roadmap prodotto - 2026-09-11

Con T34b chiusa, la roadmap torna alla corsia Q2. I renderer già estratti e i
micro-refactor precedenti risultano chiusi; il candidato successivo è
`memoria-cli-command-groups`, da delimitare con review architetturale prima di
modificare la superficie CLI pubblica. pCloud, nuove fonti e ulteriori
migrazioni restano fuori scope.

Restano fuori scope: Q2, pCloud T26-T28, apertura post-MVP, nuove fonti,
promozione automatica di claim e modifiche canoniche non autorizzate.

Chiusura Q2 del 2026-09-11: `q2-cli-sources-offline-renderer-v1` ha estratto il
renderer diagnostico read-only di `sources offline` nel formatter condiviso.
La CLI delega il rendering senza modificare handler, parser, output, return
code o comportamento read-only; i due file di test CLI (42 test ciascuno), la
compilazione Python, il JSON del planner e `git diff --check` passano.

Gate 1 T34b del 2026-09-10: l'artefatto esterno
`intake-t34-manual-review-queue-20260831/manual_review_queue.t34.preview.json`
contiene 51 elementi preview-only (38 `CandidateNewProfile` e 13
`CandidateProfileUpdate`) e dichiara `canonical_profiles_modified=false`.
I decision set `block5a`-`block5d` e `t34_final` si sovrappongono e non possono
essere sommati senza deduplicazione; le note storiche riportano inoltre 61
update e 38 nuovi profili. Il gate ha quindi prodotto una riconciliazione
read-only, ma non autorizza ancora revisione ulteriore o applicazione canonica.

Gate 2 T34b del 2026-09-10: la deduplicazione per identificativo ha verificato
che i 51 ID della coda hanno corrispondenza nei decision set grezzi. Il file
`review_decisions_block5d.correction.json` dichiara però invalido il riepilogo
`block5d`; usando solo i set validi e il set finale successivo risultano 44
decisioni univoche: 24 `accepted`, 18 `rejected` e 2 `needs_review`. Restavano 7
`CandidateNewProfile` senza decisione valida, da sottoporre a revisione; il
successivo Gate 3 ha registrato le decisioni umane su quei 7 residui. Questo
è un inventario meccanico, non una risoluzione storica e non genera patch.

## Nota di sessione 2026-09-06 - selezione e chiusura

La procedura agent-session ha verificato che lo stato precedente era chiuso e
ha selezionato `mvp-pilot-claim-funnel-diagnostics-v1` dalla corsia Q2. La
diagnostica pura del claim funnel è stata estratta in
`mvp_pilot_claim_funnel.py`; `mvp_pilot_summary.py` conserva payload,
diagnostica e workflow invariati. I test offline coprono contesto di segmento,
claim chunk-only, skip con o senza profili candidati e stati vuoti. I 12 test
mirati, `py_compile`, JSON e `git diff --check` sono passati; nessun dato reale,
claim o profilo canonico è stato modificato. La prossima sessione deve
ricalcolare un solo candidato Q2.

## Nota di sessione 2026-09-03 - nuova selezione e chiusura

La procedura agent-session ha verificato che lo stato precedente era chiuso e
ha selezionato `mvp-pilot-signal-blockers-v1` dalla corsia Q2. Il calcolo puro
dei blocker diagnostici dei segnali è stato estratto in
`mvp_pilot_signal_blockers.py`; il summary conserva payload, diagnostica e
workflow invariati. Il test offline copre duplicati, match nominali deboli,
profili senza claim e il caso di segnale leggibile. I 10 test mirati,
`py_compile`, JSON e `git diff --check` sono passati; nessun dato reale, claim
o profilo canonico è stato modificato. La prossima sessione deve ricalcolare
un solo candidato Q2.

## Nota di sessione 2026-09-03 - nuova selezione e chiusura

La procedura agent-session ha verificato che lo stato precedente era chiuso e
ha selezionato `mvp-pilot-document-intake-blockers-v1` dalla corsia Q2. Il
calcolo puro dei blocker dell'intake documentale è stato estratto in
`mvp_pilot_document_intake.py`; il summary conserva payload, blocker,
diagnostica e workflow invariati. Il test offline copre OCR, PDF, revisione
manuale, errori OCR e documenti MVP assenti. I 9 test mirati, `py_compile`,
JSON e `git diff --check` sono passati; nessun dato reale, claim o profilo
canonico è stato modificato. La prossima sessione deve ricalcolare un solo
candidato Q2.

## Nota di sessione 2026-09-03 - nuova selezione e chiusura

La procedura agent-session ha verificato che lo stato precedente era chiuso e
ha selezionato `mvp-pilot-image-ocr-readiness-v1` dalla corsia Q2. La
classificazione pura degli asset `image_ocr_required` è stata estratta in
`mvp_pilot_image_ocr_readiness.py`; il summary conserva payload, blocker,
diagnostica e workflow invariati. Il test offline copre immagini bloccanti,
di supporto e con metadata mancanti. Test mirato, `py_compile`, JSON e
`git diff --check` sono passati; nessun dato reale, claim o profilo canonico è
stato modificato. La prossima sessione deve ricalcolare un solo candidato Q2.

## Nota di sessione 2026-09-03 - nuova selezione

La procedura agent-session ha verificato che lo stato precedente era chiuso e
che i candidati Q2 gia' classificati risultano coperti nel checkout. E' stato
selezionato `mvp-demo-readiness-helper-v1`: isolare il calcolo puro della
readiness da `mvp_demo_descriptor.py`, mantenendo invariati payload, status,
diagnostica e workflow. Implementazione e test offline condividono lo stesso
confine; il routing intenzionale e' `medium/mmr_implementer` con modello
`gpt-5.6-terra`. Chiusura sessione: il leaf
`mvp_demo_descriptor_readiness.py` e' stato estratto, con payload, status,
diagnostica, provenance e workflow invariati. Gli 8 test mirati, `py_compile`,
JSON e `git diff --check` sono passati; nessun dato reale, claim o profilo
canonico e' stato modificato. Il prompt e il task router vietano ora di
chiudere un task runtime eseguibile con solo planning o documentazione.

## Nota di sessione 2026-09-03 - selezione corrente

Il planner ha selezionato `local-processing-progress-reporter-v1` dalla
traccia Q2: il throttling e il parsing del progresso del runner locale saranno
isolati in un leaf dedicato, con test offline sullo stesso confine. L'obiettivo
e' behavior-preserving: manifest, sequenza degli step, callback e output
restano invariati. Il fallback diretto del parent e' registrato nel planner
per assenza di un subagent callable. Chiusura sessione 2026-09-03: estratto
`local_processing_progress.py` e mantenuti invariati callback, frequenze,
manifest e sequenza degli step. I 19 test mirati, `py_compile`, JSON e
`git diff --check` sono passati; nessun dato reale o profilo canonico e' stato
modificato. La prossima sessione deve ricalcolare un solo candidato Q2.

## Nota di sessione 2026-09-03

Il precedente incremento dei golden test diagnostici CLI è chiuso. È stato
selezionato e delegato il micro-incremento Q2
`q2-diagnostic-formatters-extraction-v1`: estrarre i formatter diagnostici in
un leaf di sola stampa, accorpando implementazione e test perché condividono
confine e quality gate. Il planner è stato chiuso dopo la restituzione
dell’implementazione e la verifica dei test; nessun dato reale, claim o
profilo canonico è coinvolto.

Correzione di processo: il prompt e il playbook del router ora stabiliscono che
la delega non è un risultato. Il parent deve attendere la restituzione,
verificare diff/status nel worktree condiviso, eseguire il quality gate e
aggiornare il planner prima di rispondere; un diff runtime vuoto lascia la
sessione aperta o bloccata.

Chiusura sessione 2026-09-03: il leaf diagnostico è stato estratto in
`memoria_cli_diagnostic_formatters.py`; `memoria_cli.py` conserva gli alias
pubblici compatibili. I 42 test diagnostici, `py_compile`, JSON e `git diff
--check` sono passati. Nessun dato reale o profilo canonico è stato modificato.

## Incremento storico - Q2 Golden test dei formatter diagnostici CLI

Q2 - Golden test dei formatter diagnostici CLI.

Obiettivo operativo corrente: aggiungere test offline con confronto esatto di
stdout, stderr e return code per il gruppo di formatter diagnostici già
delimitato dalla review architetturale, senza modificare runtime o output.

Stato corrente: completato il 2026-09-03 come prerequisito verificabile per la
futura estrazione di `memoria_cli_diagnostic_formatters.py`.

Perimetro: cinque casi mirati per status line, inventory text/Markdown e
profiles status text/Markdown, usando fixture temporanee già previste dalla
suite. Restano fuori estrazione del modulo, parser, handler, resolver, schema,
workflow, dati esterni, claim, profili canonici e pubblicazione.

Stop condition corrente: soddisfatta; confronti golden stabili aggiunti e test
mirati passanti, senza modificare contratti runtime o output di produzione.

Chiusura sessione 2026-09-03: aggiunti cinque confronti integrali di stdout,
stderr vuoto e return code in `test_memoria_diagnostic_cli.py`; il gate
combinato conta 48 test passanti. La review architetturale del 2026-09-02
resta il vincolo per la sessione successiva: il modulo futuro sarà un leaf di
sola stampa e gli helper condivisi non saranno duplicati.

## Incremento storico - Q2 Isolamento del renderer Markdown dei profili candidati

Obiettivo operativo corrente: estrarre il solo rendering Markdown da
`candidate_person_profiles.py` in un modulo dedicato, mantenendo invariati
payload, estrazione, CLI, schema, workflow e import pubblico esistente.

Stato storico: selezionato il 2026-09-02. T34 era allora considerata chiusa;
la priorità T34b è stata introdotta il 2026-09-10 prima della ripresa di Q2,
con fixture offline e test mirati.

Stop condition corrente: renderer unico isolato, output invariato e test
`tests.test_candidate_person_profiles_from_documents` passanti; nessun dato esterno o profilo
canonico modificato.

Chiusura sessione 2026-09-02: renderer estratto in
`candidate_person_profiles_markdown.py`; `candidate_person_profiles.py` conserva
l'import pubblico. I sei test mirati passano e non risultano modifiche a
payload, ledger, readiness, CLI, schema, workflow, dati esterni o profili
canonici. La prossima sessione deve ricalcolare un solo candidato Q2 dall'audit
Q1.

## Chiusura T34

T34 - Migrazione controllata dei profili legacy: chiusa il 2026-09-02. Le
evidenze operative della migrazione restano nel data root esterno; la roadmap
non mantiene ulteriori preflight o applicazioni canoniche pendenti.

## Incremento chiuso precedente

Q2b - Pulizia delle copie private legacy dei renderer funding package.

Obiettivo operativo della sessione precedente: rimuovere le copie private duplicate dei renderer
da `mvp_funding_package.py`, mantenendo `mvp_funding_package_markdown.py` come
unica implementazione autorevole e preservando output, import, CLI, schema e
workflow.

Stato corrente: selezionato il 2026-09-01. L'estrazione precedente e' verificata;
resta da rimuovere il codice privato legacy duplicato. La policy di fallback del
controller e' attiva per questo micro-slice `medium` delimitato.

Perimetro corrente: due responsabilita' pure di rendering, test mirati offline e nessun
dato esterno, profilo canonico, nuova fonte o pubblicazione.

Stop condition corrente: responsabilita' estratta, test mirati passanti e
contratti pubblici invariati — verificata.

Chiusura sessione 2026-09-02: rimosse da `mvp_funding_package.py` le due copie
private legacy dei renderer Markdown. Il modulo
`mvp_funding_package_markdown.py` resta l'implementazione autorevole; gli
import/alias pubblici, l'output e il workflow restano invariati. Test mirato,
validazione JSON e `git diff --check` completati.

## Nota storica - Q1 audit di modularita'

Obiettivo operativo: ricostruire l'artefatto audit Q1 mancante usando soltanto
evidenze versionate e metriche leggere del repository, così da rendere
verificabile la successiva selezione di un solo candidato Q2.

Stato: selezionato il 2026-09-01 dopo la verifica del blocco Q2.

Perimetro: sola discovery/documentazione; nessuna modifica runtime, nessun
refactor, nessun dato esterno e nessuna decisione storica.

Chiusura audit Q1 2026-09-01: ricostruito e verificato
`memoria-engine-modularity-audit.md` con metriche leggere, responsabilità,
rischi, quattro candidati e test minimi. È stato selezionato come prossimo Q2
`mvp-demo-reconciliation-renderer`, limitato al rendering Markdown della
riconciliazione in `mvp_demo_descriptor.py`; l'implementazione è rinviata alla
sessione successiva.

Esito sessione 2026-09-01: discovery Q2 non verificabile. Il riferimento
`memoria-engine-modularity-audit.md`, dichiarato presente nell'evidenza Q1,
non esiste nel checkout e non risulta nella storia Git; senza quell'artefatto
non e' possibile selezionare responsabilita', rischio e test minimi di un solo
candidato senza introdurre un'ipotesi non auditabile. Nessun codice runtime,
dato esterno, profilo canonico o decisione storica e' stato modificato. Il
prossimo passo e' ripristinare/verificare l'audit Q1 e ricalcolare la selezione.

## Incremento precedente - T34 - Revisione residui

T34 - Revisione residui: confronti di date del lotto 2.

Obiettivo: preparare il confronto documentale dei 16 `CandidateProfileUpdate`
pending relativi alle date del lotto T34-2, mantenendo provenance e decisioni
separate per profilo. Gli altri 46 update pending e i 38
`CandidateNewProfile` restano fuori scope. Nessuna ProfilePatch verra' applicata
e nessun profilo canonico verra' modificato.

Selezione sessione 2026-08-31: T34 resta la priorita' immediata secondo la
roadmap tecnica e il decision log. Il lotto 2 e' chiuso come intake; la coda
successiva e' la revisione dei 16 confronti di date, con esito accettato,
rifiutato o pending motivato soltanto dopo verifica della provenance.

Chiusura revisione date T34-2 2026-08-31: verificati i 16 casi presenti negli
artefatti, con 15 decisioni `accepted` per compatibilita' documentale e 1 caso
`pending` motivato per il conflitto Bonfanti sulla data di morte. Generate 15
operazioni di `ProfilePatch` preview in 9 run isolate; nessuna patch canonica,
fusione o modifica ai profili reali e' stata eseguita. Restano 45
`CandidateProfileUpdate` pending e 38 `CandidateNewProfile`.

Worklist manuale T34 2026-08-31: generata nel data root esterno la coda
`intake-t34-manual-review-queue-20260831`, con 84 elementi (46
`CandidateProfileUpdate` e 38 `CandidateNewProfile`). La worklist contiene
provenance, documento, claim, valore candidato, valore legacy e campi vuoti per
decisione e nota; non registra decisioni e non modifica profili canonici. Il
prossimo lavoro e' compilarla manualmente per blocchi, lasciando pending i
conflitti non risolti.

Blocco 1 revisione T34 2026-08-31: accettate esplicitamente 10 date compatibili
su 8 profili, con 10 operazioni `ProfilePatch` preview generate. Nessuna patch
canonica e' stata applicata. Il prossimo blocco riguarda le date di morte con
contesto incompleto o conflittuale, da sottoporre singolarmente all'utente.

Blocco 2 revisione T34 2026-08-31: registrate 7 decisioni esplicite sulle date
di morte; 5 hanno prodotto operazioni `ProfilePatch` preview e 2 hanno
mantenuto il valore legacy senza operazioni (Mereu e Poletti). Nessuna patch
canonica e' stata applicata. Il prossimo blocco riguarda le date di nascita
compatibili residue.

Blocco 3 revisione T34 2026-08-31: accettate esplicitamente 3 date di nascita
compatibili (Ottonelli, Poletti e Poli), con 3 operazioni `ProfilePatch`
preview. Nessuna patch canonica e' stata applicata. Il prossimo blocco riguarda
formazioni/ruoli e alias residui.

Blocco 4A revisione T34 2026-08-31: registrate 8 decisioni su
formazioni/ruoli. Accettate 2 aggiunte di ruolo (Marciatori e Minozzi),
mantenute 5 formazioni senza modifica e lasciato pending Guerra; Terzi e'
stato mantenuto sulla 36a Brigata. Generate 2 operazioni `ProfilePatch`
preview; nessuna patch canonica applicata.

Blocco 4B revisione T34 2026-08-31: accettati esplicitamente 6 alias
documentati, con 6 operazioni `ProfilePatch` preview additive su
`/identity/aliases/-`. I nomi canonici restano invariati e nessuna patch
canonica e' stata applicata. Il prossimo blocco riguarda i 38
`CandidateNewProfile` e i conflitti residui.

Blocco 5A revisione T34 2026-08-31: dei primi 10 `CandidateNewProfile`,
7 sono stati scartati come frammenti/luoghi spurii e 3 sono stati mantenuti
`needs_review` come possibili persone. Nessun nuovo profilo e' stato creato;
il prossimo blocco e' la revisione dei successivi 10 candidati.

Blocco 5C revisione T34 2026-08-31: dei successivi 10 `CandidateNewProfile`,
2 sono stati accettati in modalita preview (`Venzi Ernesto` e `Bagni Desildo`)
e 8 sono stati rifiutati come duplicati, luoghi, alias o frammenti. Nessuna
creazione canonica; il prossimo blocco riguarda gli ultimi 8 candidati.

Blocco 5B revisione T34 2026-08-31: dei successivi 10 `CandidateNewProfile`,
9 sono stati accettati in modalita preview e 1 (`Livio Brisighella`) e' stato
rifiutato. Generato il preview di 9 nuovi profili, senza creazione canonica;
il prossimo blocco e' la revisione dei successivi 10 candidati.

Blocco 5D revisione T34 2026-08-31: sugli ultimi 8 `CandidateNewProfile`,
3 sono stati accettati in modalita preview (`Saba Mario`, `Tacconi Rosa` e
`Bergonzoni Lino`), 4 sono stati rifiutati e 1 (`Rosina Forli`) e' stato
mantenuto `needs_review`. Il registro iniziale errato e' stato invalidato e
corretto; nessuna creazione canonica e' stata eseguita.

Checklist finale T34 2026-08-31: verificata la copertura della worklist tramite
ID stabili, registrati i conteggi finali (`accepted`, `rejected`,
`needs_review`), conservata la provenance delle decisioni accettate e validati
JSON e diff. La correzione del mapping errato del primo Blocco 5D e' stata
registrata senza cancellare l'artefatto originale. La chiusura resta
preview-only: nessuna patch canonica, creazione profilo o pubblicazione.

Avvio T34 Bassi del 2026-08-30: eseguita una ricerca dettagliata isolata per
`person:purocielo:bassi-giancarlo`. Il connettore ha restituito un hit nominale
singolo con contenuto biografico, ma l'acquisizione ha prodotto `0 SourceDocument`
e nessun file/sidecar. Il risultato resta quindi candidato di ricerca e non
alimenta ancora `CandidateProfileUpdate`; il profilo canonico Bassi e' invariato.

Chiusura batch T34 lotto 2 del 2026-08-30: completate 20 invocazioni isolate
orchestrate in un unico batch, con 16 esiti `ok` e 4 `no_results`. Gli esiti
`ok` hanno prodotto 0 `SourceDocument` acquisiti; i 4 `no_results` sono Panov
Sergio, Sadavich Carlo, Il Toscano e Bonfanti Adolfo. Sono stati mantenuti
output e provenance separati per profilo. Nessun CandidateProfileUpdate,
ProfilePatch o profilo canonico e' stato modificato.

Esito verifica del 2026-08-30: le 20 run finali sono presenti nel data root
esterno. I 16 esiti `ok` non contengono `SourceDocument`: 9 sono corrispondenze
nominali singole candidate (Bagni, Bassi, Bergonzoni, Bianchi, Bordini, Boschi,
Comi, Costa e Gherardi), mentre 7 restano ambigui (Brini duplicato; Gianni,
Giorgio, Michele, Nicola e Stefano con più hit; Willi con risultato William).
I 4 `no_results` sono Panov Sergio, Sadavich Carlo, Il Toscano e Bonfanti Adolfo.
Tutti gli esiti restano candidati di ricerca o residui legacy: nessun claim,
CandidateProfileUpdate, ProfilePatch o profilo canonico è stato modificato.

## Stato

**Chiuso il 2026-08-29: la golden run canonica a tre casi e' promossa come demo
revisionabile/non pubblicabile; la revisione umana del racconto ha prodotto
verdetto `approved_for_layout` e l'entrypoint e' stato allineato ai testi
approvati dei blocchi 3 e 5. Il prossimo gate e' il layout interno non
pubblicabile, senza bando, importo o pubblicazione. Il brief e il wireframe
interni sono stati prodotti e verificati; T33 e' quindi chiuso senza
pubblicazione, dati copiati o modifiche canoniche.**

Il prossimo micro-incremento selezionato dopo la chiusura di T33 e del
precedente Q2 e' un refactor behavior-preserving limitato a una sola
responsabilita'. L'implementazione resta da delegare; non cambia output, CLI,
schema, workflow o dati esterni.

Esito review del 2026-07-18: il pacchetto precedente e' risultato troppo
tecnico e il perimetro Andreoli/Balboni troppo ridotto per rappresentare la
potenza del motore. La golden run resta valida come prova tecnica interna. La
presentazione viene ricostruita come oggetto separato, usando la coorte pilota
di 5 profili e il patrimonio disponibile di 57 profili senza presentarli come
schede complete. Entrypoint T33b:
`memoria-bootstrap/docs/funding-demo-t33-presentation-entrypoint.md`.

Riallineamento T33 del 2026-07-18: la proposta di run comparativa e' fermata.
Andreoli, Balboni e Bendini devono confluire in una sola candidata alla nuova
golden run canonica. La run attuale resta l'unica attiva durante review e
validazione; la presentazione non puo' usare la candidata prima della promozione.
Comandi, backup, stop condition e gate sono documentati in
`memoria-bootstrap/docs/funding-demo-t33-three-case-runbook.md`. Nessuna run e'
stata eseguita e nessun file del data root esterno e' stato modificato in questo
sotto-incremento documentale.

Validazione del riallineamento: il dry-run read-only di `memoria mvp demo-build`
sulla run attuale con il nuovo perimetro conferma 1 profilo principale, 2
complementari, 5/5 documenti, 3 famiglie fonte, readiness
`ready_for_internal_demo`, zero errori e zero warning. Il tool T31 accetta ora
descriptor e backup espliciti, cosi' puo' completare la candidata senza toccare
il descriptor attivo; 15 test mirati risultano passanti. Il preflight reale
conferma sorgenti, indice profili, descriptor e summary presenti, candidata
assente e action/plan T31 disponibili.

Correzione operativa del 2026-07-18: il primo tentativo della fase 1 si e'
fermato prima di review queue ed evidence import perche' la run canonica T32 non
conserva il file separato `document_analysis/research_feedback_actions.json`
richiesto dal wrapper `ReportsOnly`. Il runbook usa ora come sorgente la pipeline
pilota originaria `mvp-expand-pilot-preview-profiles-v1-pipeline`, che contiene
il file, gli stessi tre profili, l'action e il piano T31. La directory candidata
parziale non contiene file operativi e puo' essere rigenerata con lo stesso
`RunId`; descriptor attivo ed evidence store restano invariati.

Seconda correzione operativa del 2026-07-18: il passaggio di `$Profiles` come
array attraverso il processo esterno `pwsh.exe` espandeva i profili successivi
come argomenti posizionali; `person:...` veniva quindi interpretato come
`InputRootDir`. Le invocazioni esterne del runbook usano ora
`-ProfileId ($Profiles -join ",")`; il wrapper ricostruisce l'array tramite la
normalizzazione CSV gia' esistente. Anche questo tentativo si e' fermato prima
di creare file candidati, review queue o evidence import.

Fase 1 completata il 2026-07-18: la run
`funding-demo-golden-3cases-v1-pipeline` e' terminata con stato `completed` in
modalita' `ReportsOnly`, `SkipOnline` e `SkipEvidenceImport`. La verifica
read-only conferma 3 profili `ready_for_review`, 83 item di review, package
`ready_for_demo` ma `unreviewed`, evidence import `skipped` e descriptor attivo
ancora puntato a `prova-preview-profili-5-reviewed-01-pipeline`. Il prossimo
passo e' produrre cards e copia compilabile, quindi fermarsi al Gate 1 per
approvazione umana.

Avanzamento Gate 1 del 2026-07-19: prodotte le viste per la review storica
della candidata a tre casi:
`P:\Comune\Me.Mo.Ri.a\risultati\runs\funding-demo-golden-3cases-v1-pipeline\historian_review\review_requests.three_cases.cards.md`
e
`P:\Comune\Me.Mo.Ri.a\risultati\runs\funding-demo-golden-3cases-v1-pipeline\historian_review\review_focus_decisions_table.compilato.md`.
Il builder segnala 15 item focus e i file risultano presenti e leggibili. La
candidata resta al Gate 1: non sono state eseguite conversione, validazione,
fase 2, evidence import, modifica del descriptor attivo o promozione canonica.
Il prossimo passo e' approvazione committente, compilazione storica dei soli
campi ammessi e successiva conversione/validazione secondo runbook.

Riconferma Gate 1 del 2026-07-19: verifica read-only dei materiali conferma
cards e copia compilabile presenti, stato `pending_historian_review` e assenza
degli artefatti di conversione `review_decisions.compilato.json` e
`review_focus_conversion_summary.*`. Il lavoro resta bloccato su approvazione
committente e restituzione della tabella compilata dagli storici.

Tentativo di avvio conversione del 2026-07-19: dopo approvazione committente
dichiarata, il preflight read-only sulla tabella compilabile ha confermato che
`review_focus_decisions_table.compilato.md` contiene ancora tutte le righe con
`selected_action`, `reviewer`, `reviewed_at` e `note` vuoti. La conversione non
e' stata eseguita. Il Gate 1 resta bloccato finche' la tabella non viene
compilata dagli storici almeno con una decisione sostanziale valida per ciascuno
dei tre profili.

Conversione e validazione Gate 1 completate il 2026-07-19: dopo il salvataggio
della tabella compilata, prodotti
`review_decisions.compilato.json`, `review_focus_conversion_summary.json`,
`review_focus_conversion_summary.md`, `review_decisions.validation.json` e
`review_decisions.validation.md` nella run candidata. La validazione riporta
stato `partial_review`, 15 decisioni accettate, 68 pending, 0 invalidi e 0
errori; ciascuno dei tre profili ha 5 decisioni accettate e 0 invalidi. Nessuna
fase 2, evidence import, modifica del descriptor attivo, ProfilePatch o
promozione canonica e' stata eseguita.

Fase 2 T33 completata il 2026-07-19: creato backup
`P:\Comune\Me.Mo.Ri.a\database\evidence.before-funding-demo-golden-3cases-v1-20260719-134908.sqlite`
con WAL assente, quindi rigenerata la stessa candidata
`funding-demo-golden-3cases-v1-pipeline` in modalita' `ReportsOnly` e
`SkipOnline` usando `review_decisions.compilato.json`. L'import evidence
append-only ha letto 248 record, inserito 238 record e riconosciuto 10 gia'
presenti; il riepilogo decisioni resta `partial_review`, 15 accepted, 68
pending, 0 invalidi e 0 errori. Prodotti `verified_facts.preview.*` con 1 fatto
preview e `profile_patch.preview.*` con 1 patch preview; `mvp_package_readiness`
riporta `ready_for_demo` con 0 output mancanti. Il descriptor attivo resta
puntato a `prova-preview-profili-5-reviewed-01-pipeline`; non sono state
eseguite fase 3, fase 4, promozione canonica, applicazione ProfilePatch o
modifiche ai profili canonici.

Fase 3 T33 completata il 2026-07-19: costruito il descriptor candidato
`P:\Comune\Me.Mo.Ri.a\risultati\runs\funding-demo-golden-3cases-v1-pipeline\memoria_mvp_demo.candidate.json`
e la riconciliazione candidata
`P:\Comune\Me.Mo.Ri.a\risultati\runs\funding-demo-golden-3cases-v1-pipeline\mvp_demo_reconciliation_table.md`.
`memoria mvp demo-build` riporta `ready_for_internal_demo`, 1 profilo
principale, 2 complementari, 5/5 documenti coperti, 3 famiglie fonte, 15
decisioni sostanziali, 1 verified fact preview e 1 ProfilePatch preview.
Rigenerato il feedback loop T31 dentro la stessa run e aggiornato solo il
descriptor candidato, con backup
`memoria_mvp_demo.candidate.before-t31-feedback-loop.json`; il loop risulta
`closed_with_auditable_outcome` con outcome `needs_manual_review`. La verifica
`memoria mvp demo --descriptor <candidate>` conferma JSON valido, artefatti
presenti e safety flag `preview_only=true`, `publication_ready=false`,
`applies_profile_patch=false`, `creates_canonical_verified_facts=false` e
`modifies_canonical_profiles=false`. Il descriptor attivo resta puntato a
`prova-preview-profili-5-reviewed-01-pipeline`; non sono state eseguite fase 4,
fase 5, promozione canonica, applicazione ProfilePatch o modifiche ai profili
canonici.

Fase 4 T33 completata il 2026-07-19: rigenerato il pacchetto unico sulla
candidata usando `memoria_mvp_demo.candidate.json` come descriptor demo. Il
primo passaggio del builder ha evidenziato un gate obsoleto ancora tarato sul
perimetro precedente; il controllo e il test `tests.test_mvp_funding_package`
sono stati aggiornati al perimetro T33 a 3 profili e 5 documenti. Dopo la
rigenerazione, `mvp_go_no_go_checklist.*` e `funding_package_index.md`
riportano `go_with_review_blockers`, quality gate `passed`, 3 profili, 5
documenti, 3 famiglie fonte, 0 blocker tecnici e 1 review blocker dovuto alle
68 decisioni pending. Il pacchetto e' pronto per gate finale umano come demo
revisionabile, non pubblicabile. Il descriptor attivo resta puntato a
`prova-preview-profili-5-reviewed-01-pipeline`; non sono state eseguite fase 5,
promozione canonica, applicazione ProfilePatch o modifiche ai profili canonici.

Verifica gate finale T33 del 2026-08-09: aggiunto il comando read-only
`memoria mvp final-gate`, che controlla descriptor candidato, descriptor attivo
opzionale, perimetro 3 profili/5 documenti, copertura multi-fonte, safety flag,
artifact preview e pacchetto go/no-go. L'esito `ready_for_human_approval`
significa solo che il materiale puo' essere portato al gate umano; il report non
autorizza promozione, non modifica `memoria_mvp_demo.active.json`, non applica
ProfilePatch e non crea verified facts canonici. Coperti i casi offline di
candidata pronta, safety flag bloccante e artifact fuori run candidata; test
mirati passanti con 40 test OK.

Promozione canonica T33 autorizzata e completata il 2026-08-09: dopo
approvazione esplicita del gate umano come demo revisionabile/non pubblicabile,
il descriptor candidato a tre casi e' stato copiato su
`P:\Comune\Me.Mo.Ri.a\database\memoria_mvp_demo.active.json`, con backup
preventivo
`P:\Comune\Me.Mo.Ri.a\database\memoria_mvp_demo.active.before-funding-demo-golden-3cases-v1-20260809-170417.json`.
Le verifiche read-only `memoria mvp demo --data-root "P:\Comune\Me.Mo.Ri.a"` e
`memoria mvp status --data-root "P:\Comune\Me.Mo.Ri.a"` confermano la nuova run
canonica `funding-demo-golden-3cases-v1-pipeline`, 1 profilo principale, 2
profili complementari, 5 documenti, 3 famiglie fonte, 12/12 artefatti presenti,
ledger attivo a 3 profili e safety flag `preview_only=true`,
`publication_ready=false`, `applies_profile_patch=false`,
`creates_canonical_verified_facts=false` e `modifies_canonical_profiles=false`.
Nessuna ProfilePatch e' stata applicata, nessun verified fact canonico e' stato
creato e nessun profilo canonico e' stato modificato.

Nota operativa corrente T33: lo stato semplice della demo attiva, i comandi
minimi di verifica e il percorso consigliato per eventuali nuove run candidate
sono raccolti in
`memoria-bootstrap/docs/funding-demo-t33-current-state-operator-note.md`.

Riallineamento documentale T33 del 2026-08-09: gli entrypoint della
presentazione e del pacchetto tecnico sono stati aggiornati per indicare
`funding-demo-golden-3cases-v1-pipeline` come run canonica attiva. La run
precedente resta storica e non deve essere usata come seconda demo attiva.
Nessuna scrittura nel data root esterno, nessuna ProfilePatch applicata, nessun
verified fact canonico creato e nessun profilo canonico modificato.

Riallineamento materiali di supporto T33 del 2026-08-09: checklist readiness,
brief editoriale, scheda casi e roadmap uso fondi indicano ora la golden run
canonica `funding-demo-golden-3cases-v1-pipeline`, con 3 profili, 5 documenti e
review parziale. I conteggi e i percorsi operativi della precedente run a due
casi sono mantenuti solo dove esplicitamente storici. La presentazione esterna
non e' approvata: il prossimo gate resta la prova asciutta del racconto in sei
schermate e la successiva revisione umana. Nessuna scrittura nel data root
esterno e nessuna modifica canonica sono state eseguite.

Correzione identita' e residui T33 del 2026-08-09: una verifica read-only del
descriptor attivo ha confermato il terzo profilo come
`person:purocielo:bendini-ateo`; package entrypoint e scheda casi sono stati
corretti da `bendini-primo`. Il diagramma evidenziale descrive ora 5/5
documenti, 15 decisioni accettate, 68 pending, 1 verified fact preview e 1
ProfilePatch preview non applicata. Il runbook della promozione a tre casi e'
marcato come procedura storica completata e non va rieseguito sulla demo attiva.
Nessun file del data root esterno e' stato modificato.

Prova asciutta presentazione T33 del 2026-08-09: creato
`memoria-bootstrap/docs/funding-demo-t33-presentation-dry-run.md` e riallineato
l'entrypoint della presentazione per distinguere meglio conteggi della coorte
pilota e conteggi della golden run a tre casi. Le sei schermate hanno verdetto
`pass` o `pass con cautela`; la presentazione e' pronta per revisione umana del
racconto, non per uso esterno finale. Nessun bando, importo o finanziatore e'
stato introdotto; nessun file del data root esterno e' stato modificato.

Verifica caso concreto T33 del 2026-08-25: una lettura read-only degli artefatti della golden run ha individuato Andreoli come candidato utilizzabile per il racconto, limitatamente ai collegamenti persona-documento confermati e ai limiti documentati. I dettagli restano negli artefatti esterni della run; nessun fatto storico e stato promosso o copiato nel repository.

Revisioni narrative T33 del 2026-08-25: recepite nella bozza le osservazioni della revisione umana. Il racconto ora include persone, luoghi, eventi e documenti, sostituisce il glossario tecnico con cinque storie e usa Andreoli come unico esempio concreto, limitato a collegamenti confermati e divergenze documentate. La presentazione resta non pubblicabile.

Selezione visuale T33 del 2026-08-26: eseguita lettura read-only dei materiali del caso concreto. Sono state selezionate tre tracce documentali per il futuro layout interno; la seconda scheda istituzionale resta una domanda aperta. Nessuna immagine o dato storico e stato copiato nel repository e la presentazione resta non pubblicabile.

Scaletta visuale T33 del 2026-08-26: creato memoria-bootstrap/docs/funding-demo-t33-andreoli-visual-layout.md per comporre internamente la schermata Andreoli con tre tracce documentali e una domanda aperta. Immagini ed estratti restano nel data root esterno; nessun dato storico e stato copiato nel repository e la presentazione resta non pubblicabile.

Handoff revisione umana T33 del 2026-08-25: creato
`memoria-bootstrap/docs/funding-demo-t33-human-review-handoff.md` come traccia
documentale per la revisione umana del racconto in sei schermate. L'handoff
elenca materiali da leggere, domande per blocco narrativo, esiti ammessi e
blocchi da non superare. Non approva la presentazione, non introduce bando,
importo o finanziatore, non scrive nel data root esterno e non modifica
ProfilePatch, verified facts canonici o profili canonici.

Avanzamento T26 del 2026-07-29: introdotto il backend
`PCloudWorkspaceStorage` in modalita' read-only con HTTP iniettabile e test mock.
Il workspace e' ora risolvibile come provider logico `local` o `pcloud` tramite
manifest e override da `.env`: `MEMORIA_WORKSPACE_PROVIDER`,
`MEMORIA_PCLOUD_APP_NAME`, `MEMORIA_PCLOUD_CLIENT_ID`,
`MEMORIA_PCLOUD_CLIENT_SECRET`, `MEMORIA_PCLOUD_ACCESS_TOKEN`,
`MEMORIA_PCLOUD_API_HOST`, `MEMORIA_PCLOUD_ROOT`, `MEMORIA_PCLOUD_FOLDER_ID` e
ref override dedicati. Il comando `memoria workspace status` mostra il provider
selezionato, host/root/folderid e quali segreti sono configurati, senza stampare
valori sensibili; `memoria workspace pcloud-auth-url` genera l'URL OAuth code
flow per l'app `MemoriaStorage`. Il token richiesto dalle API read-only e'
ottenuto dopo approvazione utente e scambio `oauth2_token`, non coincide con
client id/secret. L'opzione `--list` permette una verifica read-only esplicita.
I test standard restano offline e non eseguono chiamate live pCloud. Nessuna
scrittura cloud, migrazione dati, modifica a dati reali o salvataggio di
credenziali nei repository e' stata eseguita.

Verifica live T26 del 2026-07-29: il codice OAuth approvato dall'utente e'
stato scambiato con successo tramite `oauth2_token`; il bearer e l'host
restituito sono stati salvati soltanto nel `.env` locale, senza stamparli.
`memoria workspace status --list .` conferma l'accesso read-only a
`api.pcloud.com`. La root pCloud e' attualmente vuota ed e' configurata come
path `/`, `folderid 0`. Nessuna cartella o file remoto e' stato creato.

T32 e' chiuso: la golden run e' pronta per demo interna, usa il ledger standard
`mvp_consolidated_review_ledger.json`, non dipende piu' dal sidecar T30 come
ledger attivo, e il rischio del pacchetto repository distribuibile e' trattato
da esclusioni `export-ignore` testate.

Avanzamento T33 del 2026-07-16: creato l'entrypoint documentale del pacchetto
finanziatori in
`memoria-bootstrap/docs/funding-demo-t33-package-entrypoint.md`. L'artefatto
definisce golden run, reading order, walkthrough 7-10 minuti, comandi fallback,
guardrail editoriali e checklist T33, senza copiare dati reali e senza scrivere
nel data root esterno. La verifica read-only `memoria mvp demo --data-root
"P:\Comune\Me.Mo.Ri.a"` conferma `ready_for_internal_demo` e safety flag
preview-only.

Avanzamento T33 del 2026-07-16: creato il diagramma documentale
`memoria-bootstrap/docs/funding-demo-t33-evidence-flow-diagram.md`, collegato
all'entrypoint T33. Il diagramma mostra il percorso
`fonti -> documenti -> evidenze -> riconciliazione -> review -> verified facts
preview -> ProfilePatch preview -> feedback outcome -> pacchetto finanziatori`
usando solo ID e riferimenti ad artefatti, senza copiare dati reali e senza
scrivere nel data root esterno.

Avanzamento operativo T33 del 2026-07-16: autorizzata la scrittura nel data root
esterno per il solo pacchetto finanziatori. Rigenerati nella run canonica
`mvp_funding_dossier.json`, `mvp_funding_dossier.md`,
`mvp_go_no_go_checklist.json`, `mvp_go_no_go_checklist.md` e
`funding_package_index.md`. Il builder del pacchetto e' ora descriptor-aware:
quando riceve `memoria_mvp_demo.active.json` usa il perimetro T33 reale
1 profilo primario, 4 documenti e 3 famiglie fonte, e non i vecchi criteri del
pilota a 3-5 schede. Esito checklist: `go_with_review_blockers`, quindi
finanziabile come demo revisionabile ma non pubblicabile.

Avanzamento T33 del 2026-07-16: creata la scheda caso demo
`memoria-bootstrap/docs/funding-demo-t33-demo-case-card.md` e collegata
all'entrypoint T33. La scheda rende leggibile il caso Andreoli/Balboni con
provenance, 3 famiglie fonte, 4/4 documenti coperti, stati di riconciliazione,
decisione storica, verified facts preview, ProfilePatch preview e feedback
outcome T31, senza scrivere nel data root esterno e senza presentare alcun
output come pubblicabile.

Avanzamento T33 del 2026-07-16: creata la roadmap uso fondi
`memoria-bootstrap/docs/funding-demo-t33-funding-roadmap.md` e collegata
all'entrypoint T33. La roadmap distingue capacita' attuali, sviluppo finanziato
e visione di piattaforma, definisce risultati attesi a 1-2, 3-6 e 6-12 mesi e
mantiene esplicito che il finanziamento scala un metodo con provenance, review
storica e guardrail preview-only, non una pubblicazione automatica.

Avanzamento T33 del 2026-07-16: creata la checklist di readiness esterna
`memoria-bootstrap/docs/funding-demo-t33-external-readiness-checklist.md` e
collegata all'entrypoint T33. La prima versione classificava la presentazione
come `approvabile_con_guardrail` e manteneva bloccata la pubblicazione storica.
La review umana del 2026-07-18 ha superato quel verdetto: la presentazione
esterna e' ora `not_ready_for_external_presentation`, mentre restano invariati
i blocker su decisioni pending, output preview e feedback outcome
`needs_manual_review`. Nessuna scrittura nel data root esterno e nessuna
promozione canonica.

Avanzamento T33 del 2026-07-16: creato il brief editoriale esterno
`memoria-bootstrap/docs/funding-demo-t33-external-brief.md` e collegato
all'entrypoint T33. Il brief completa la rifinitura del dossier per presentazione
esterna con messaggio in 60 secondi, apertura, chiusura, cosa mostrare e cosa
non dire, mantenendo `go_with_review_blockers`, `publication_ready=false` e
`preview_only=true`. Nessuna scrittura nel data root esterno e nessuna
promozione canonica.

Revalidazione T33 del 2026-07-17: eseguita verifica read-only
`memoria mvp demo --data-root "P:\Comune\Me.Mo.Ri.a"` dalla CLI Python. Il
descriptor e' presente e JSON valido, la run resta
`ready_for_internal_demo`, 1 profilo principale, 1 profilo di contrasto,
4 documenti e 3 famiglie fonte sono dichiarati, gli artefatti T30/T31/T33
risultano presenti e i safety flag restano:
`preview_only=true`, `publication_ready=false`,
`applies_profile_patch=false`, `creates_canonical_verified_facts=false` e
`modifies_canonical_profiles=false`. Nessuna scrittura nel data root esterno,
nessuna patch applicata, nessun fatto canonico creato.

Descrittore:

```text
P:\Comune\Me.Mo.Ri.a\database\memoria_mvp_demo.active.json
```

Run canonica storica T32:

```text
prova-preview-profili-5-reviewed-01-pipeline
```

Chiusura T32 del 2026-07-16:

- `memoria mvp demo` conferma `ready_for_internal_demo`, artefatti T30/T31
  presenti e safety flag preview-only;
- il walkthrough asciutto e' documentato in
  `memoria-bootstrap/docs/funding-demo-t32-walkthrough-dry-run.md`;
- il trattamento sidecar e' chiuso in
  `memoria-bootstrap/docs/funding-demo-t32-sidecar-treatment.md`;
- il rischio distribuibile e' chiuso con `.gitattributes`, che esclude dagli
  archivi `memoria-engine/ricerche/person_profiles/**`,
  `memoria-engine/ricerche/caduti_purocielo.csv` e
  `memoria-engine/ricerche/mvp/**`;
- `tests.test_packaging` verifica che queste esclusioni restino presenti;
- nessun profilo canonico e' stato modificato, nessuna patch e' stata
  applicata, nessun verified fact canonico e' stato creato.

## Motivazione

T33 deve trasformare la golden run pronta per demo interna in un pacchetto breve
e presentabile a finanziatori, senza presentare output preview come schede
pubblicabili e senza allargare il perimetro storico.

```text
fonti eterogenee
  -> evidenze tracciabili
  -> riconciliazione multi-fonte
  -> decisione dello storico
  -> verified fact e patch preview
  -> feedback per nuova ricerca
  -> esito tracciato
```

I gap metodologici obbligatori sono coperti in modalita' preview-only:

- **merge multi-fonte**, con provenance e divergenze visibili;
- **feedback loop chiuso**, non limitato alla generazione di query candidate;
- **rientro dell'esito nella memoria di ricerca**, senza promozione automatica
  a fatto storico.

## Scope T33

T33 deve:

- preparare un dossier finanziatori breve collegato alla golden run;
- preparare script del walkthrough e comandi di fallback;
- produrre un diagramma del percorso fonti-documenti-evidenze-review-feedback;
- preparare una scheda del caso demo con provenance leggibile e stato preview;
- dichiarare limiti, capacita' attuali, sviluppo finanziato e visione;
- mantenere esplicita la distinzione fra preview, decisione e pubblicazione.

## Fuori scope T33

- nessun OCR o scansione massiva;
- nessuna chiamata live a fonti non controllata;
- nessuna rigenerazione massiva di pipeline;
- nessuna patch applicata ai profili canonici;
- nessun driver pCloud;
- nessun Q2 salvo blocco diretto del pacchetto finanziatori;
- nessuna espansione oltre il perimetro demo.

## Criteri di uscita

- dossier finanziatori breve collegato alla golden run: **completato per
  preview con dossier generato e brief editoriale esterno**;
- script del walkthrough e comandi di fallback disponibili: **completato**;
- diagramma del percorso fonti-documenti-evidenze-review-feedback:
  **completato**;
- scheda del caso demo con provenance leggibile: **completata per preview**;
- roadmap dell'uso dei fondi e risultati attesi: **completata per preview**;
- distinzione esplicita fra capacita' attuali, sviluppo finanziato e visione:
  **completata per preview**;
- checklist di readiness approvata per presentazione esterna:
  **non soddisfatta dopo la prima review umana**; T33b e' aperto, mentre
  `go_with_review_blockers` resta invariato per la pubblicazione storica;
- nessuna affermazione storica non supportata o output preview presentato come
  pubblicabile.

## Stato T33b

La parte tecnica T33 e' completa per preview:

- entrypoint del pacchetto collegato alla golden run;
- dossier generato nel data root autorizzato;
- diagramma fonti-documenti-evidenze-review-feedback;
- scheda caso demo con provenance leggibile;
- roadmap uso fondi e distinzione attuale/finanziato/visione;
- checklist readiness esterna;
- brief editoriale esterno;
- validazione read-only `memoria mvp demo`, riconfermata il 2026-07-17.

La prima approvazione umana non e' stata concessa. T33b ha ora prodotto il
contratto iniziale della presentazione in sei schermate e la separazione
esplicita fra prova tecnica e racconto finanziatori. Restano da svolgere
impaginazione e nuova prova umana. I blocker storici restano attivi:
`go_with_review_blockers`, `publication_ready=false`, `preview_only=true`.

## Priorita' degli incrementi successivi

Da T33:

1. T26-T28 cloud solo se richiesti o se diventano necessari per la fase
   successiva.
2. Q2 solo come micro-refactor behavior-preserving con rischio concreto.

T26-T28 cloud restano in hold fino alla chiusura del pacchetto finanziatori.

## Documenti autorevoli

- `roadmap/00-roadmap-master.md`;
- `roadmap/01-mvp-roadmap.md`;
- `roadmap/02-technical-roadmap.md`;
- `funding-demo-golden-path.md`;
- `decision-log.md`.

## Evidenza di chiusura

Avanzamento T30:

- autorizzato ed eseguito incremento operativo T30 con scrittura limitata nel
  data root esterno ai soli artefatti preview della golden run;
- aggiunto a `memoria mvp demo-build` il supporto a
  `--output-aligned-ledger`, che crea un sidecar preview del ledger consolidato
  riallineato al perimetro T30 senza modificare il ledger originale, profili
  canonici, raw documenti, OCR o fonti originali;
- nota metodologica vincolante: `--output-aligned-ledger` e' una variazione
  temporanea T30 per sbloccare la demo interna, non il flusso ordinario di
  arricchimento schede; T32 non puo' avanzare finche' lo stesso risultato non
  viene rigenerato dal percorso standard
  `documenti/CSV/DOCX -> person linking -> candidate_evidence_claims ->
  evidence store -> consolidated ledger`;
- creato il sidecar autorizzato:
  `P:\Comune\Me.Mo.Ri.a\risultati\runs\prova-preview-profili-5-reviewed-01-pipeline\mvp_consolidated_review_ledger.t30-preview.json`;
- il sidecar aggiunge 2 claim candidati `unreviewed` e marcati
  `t30_preview_candidate`: uno da `legacy_csv:a4ac96061a2381b5` tramite
  `t30_preview_alignment_from_candidate_document_person_link`, uno da
  `local_docx:4c2ad1d2ab937913` tramite
  `t30_preview_alignment_from_existing_claim`;
- creati/aggiornati gli artefatti autorizzati:
  `P:\Comune\Me.Mo.Ri.a\database\memoria_mvp_demo.active.json` e
  `P:\Comune\Me.Mo.Ri.a\risultati\runs\prova-preview-profili-5-reviewed-01-pipeline\mvp_demo_reconciliation_table.md`;
- `memoria mvp demo-build` sulla run canonica con sidecar T30 conferma
  `Readiness: ready_for_internal_demo`, `Readiness errors: 0`,
  `Readiness warnings: 0`, famiglie coperte
  `legacy_csv`, `local_docx`, `partigiani_italia` e documenti coperti `4/4`;
- `memoria mvp demo` legge ora il descrittore attivo con
  `Status: ready_for_internal_demo`, artefatti presenti e safety flag:
  `preview_only=true`, `applies_profile_patch=false`,
  `creates_canonical_verified_facts=false`,
  `modifies_canonical_profiles=false`;
- la tabella di riconciliazione preview contiene 22 righe, mantiene le
  divergenze visibili e mostra contributi da `legacy_csv`, `local_docx` e
  `partigiani_italia`;
- test mirati passanti:
  `.\.venv\Scripts\python.exe -m unittest tests.test_mvp_demo_descriptor tests.test_memoria_diagnostic_cli`
  (`38 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- aggiunto alla readiness T30 di `memoria mvp demo-build` il campo
  `alignment_plan`, derivato dalla diagnostica per-documento e limitato a passi
  preview-only verso il ledger consolidato;
- il piano distingue ora i prossimi riallineamenti operativi senza applicarli:
  `produce_candidate_claims`, `attach_existing_claims_to_demo_profile`,
  `attach_document_to_demo_profile` e fallback `add_reconciliation_row`;
- `memoria mvp demo-build` stampa righe `ALIGNMENT_STEP`, e la tabella
  Markdown di riconciliazione preview include la sezione
  `Piano riallineamento preview`;
- prova read-only reale sulla run candidata conferma due passi T30:
  `ALIGNMENT_STEP 1` produce claim candidati per
  `legacy_csv:a4ac96061a2381b5`; `ALIGNMENT_STEP 2` riconduce al profilo demo i
  claim esistenti per `local_docx:4c2ad1d2ab937913`;
- test mirati passanti:
  `.\.venv\Scripts\python.exe -m unittest tests.test_mvp_demo_descriptor tests.test_memoria_diagnostic_cli`
  (`37 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- verificato in sola lettura che restano assenti
  `P:\Comune\Me.Mo.Ri.a\database\memoria_mvp_demo.active.json` e
  `P:\Comune\Me.Mo.Ri.a\risultati\runs\prova-preview-profili-5-reviewed-01-pipeline\mvp_demo_reconciliation_table.md`;
- aggiunta alla diagnostica T30 di `memoria mvp demo-build` la causa sintetica
  `blocking_reason` per ciascun documento e ciascuna famiglia fonte T29;
- `FAMILY_STATUS` e `DOCUMENT_STATUS` mostrano ora `blocked_by`, distinguendo
  blocchi operativi diversi senza dover aprire il JSON: claim candidati
  mancanti, claim esistenti fuori perimetro demo, documenti fuori perimetro o
  righe di riconciliazione mancanti;
- la tabella Markdown di riconciliazione preview include la colonna `Blocco`
  nelle sezioni `Famiglie T29` e `Documenti T29`;
- prova read-only reale sulla run candidata conferma il blocco T30 attuale:
  `legacy_csv` e' `blocked_by=candidate_claims_missing`,
  `local_docx` e' `blocked_by=claims_outside_demo_scope`,
  `partigiani_italia` e' `blocked_by=covered`;
- test mirati passanti:
  `.\.venv\Scripts\python.exe -m unittest tests.test_mvp_demo_descriptor tests.test_memoria_diagnostic_cli`
  (`37 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- verificato in sola lettura che restano assenti
  `P:\Comune\Me.Mo.Ri.a\database\memoria_mvp_demo.active.json` e
  `P:\Comune\Me.Mo.Ri.a\risultati\runs\prova-preview-profili-5-reviewed-01-pipeline\mvp_demo_reconciliation_table.md`;
- aggiunta al payload T30 di `memoria mvp demo-build` la diagnostica
  `source_family_diagnostics`, che riepiloga per ciascuna famiglia T29 lo stato
  di copertura, il numero di documenti selezionati, coperti e mancanti;
- `memoria mvp demo-build` stampa ora righe `FAMILY_STATUS` prima delle righe
  `DOCUMENT_STATUS`, rendendo immediato il blocco di merge multi-fonte senza
  dover leggere tutto il JSON;
- la tabella Markdown di riconciliazione preview include ora anche la sezione
  `Famiglie T29`; corretto il rendering Markdown delle celle numeriche per
  preservare il valore `0` invece di mostrarlo come cella vuota;
- prova read-only reale sulla run candidata conferma il quadro per famiglia:
  `legacy_csv` e `local_docx` sono `coverage=missing_reconciliation` con un
  documento selezionato e zero documenti coperti ciascuna; `partigiani_italia`
  e' `coverage=covered` con due documenti selezionati e due coperti;
- test mirati passanti:
  `.\.venv\Scripts\python.exe -m unittest tests.test_mvp_demo_descriptor tests.test_memoria_diagnostic_cli`
  (`37 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- verificato in sola lettura che restano assenti
  `P:\Comune\Me.Mo.Ri.a\database\memoria_mvp_demo.active.json` e
  `P:\Comune\Me.Mo.Ri.a\risultati\runs\prova-preview-profili-5-reviewed-01-pipeline\mvp_demo_reconciliation_table.md`;
- aggiunta al payload T30 di `memoria mvp demo-build` la diagnostica
  per-documento `document_diagnostics`, con famiglia fonte, stato di
  riconciliazione, presenza nel perimetro profili demo e stato dei claim
  candidati;
- `memoria mvp demo-build` stampa ora righe `DOCUMENT_STATUS` per ciascun
  documento T29, evitando di incrociare manualmente le liste di documenti
  coperti, mancanti, senza claim o con claim fuori perimetro;
- la tabella Markdown di riconciliazione preview include la sezione
  `Documenti T29` quando la readiness espone errori o warning;
- prova read-only reale sulla run candidata conferma il quadro operativo T30:
  `legacy_csv:a4ac96061a2381b5` ha
  `reconciliation=missing_reconciliation_row`, e'
  `present_in_selected_profiles` ma ha `claims=no_candidate_claims`;
  `local_docx:4c2ad1d2ab937913` ha
  `reconciliation=missing_reconciliation_row`, e'
  `present_in_selected_profiles` ma ha
  `claims=claims_outside_selected_profiles`; i due documenti
  `partigiani_italia` sono `covered` con claim nel perimetro selezionato;
- test mirati passanti:
  `.\.venv\Scripts\python.exe -m unittest tests.test_mvp_demo_descriptor tests.test_memoria_diagnostic_cli`
  (`37 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- verificato in sola lettura che restano assenti
  `P:\Comune\Me.Mo.Ri.a\database\memoria_mvp_demo.active.json` e
  `P:\Comune\Me.Mo.Ri.a\risultati\runs\prova-preview-profili-5-reviewed-01-pipeline\mvp_demo_reconciliation_table.md`;
- arricchita la readiness T30 di `memoria mvp demo-build` con
  `next_actions` diagnostiche calcolate dal blocco corrente, esposte nel
  payload del descrittore preview, nella tabella Markdown di riconciliazione e
  nell'output CLI;
- le azioni distinguono ora il prossimo riallineamento operativo: aggiungere
  claim dalle famiglie fonte mancanti, produrre claim per documenti selezionati
  senza claim, ricondurre al profilo demo claim gia' presenti fuori perimetro,
  oppure collegare documenti T29 assenti dal perimetro;
- prova read-only reale sulla run candidata conferma `Readiness:
  blocked_for_internal_demo` e suggerisce esplicitamente: aggiungere claim da
  `legacy_csv` e `local_docx`, produrre claim per
  `legacy_csv:a4ac96061a2381b5`, ricondurre al profilo demo i claim gia'
  presenti fuori perimetro per `local_docx:4c2ad1d2ab937913`;
- test mirati passanti:
  `.\.venv\Scripts\python.exe -m unittest tests.test_mvp_demo_descriptor tests.test_memoria_diagnostic_cli`
  (`37 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- nessun output scritto nel data root esterno; `memoria mvp demo-build` e'
  stato eseguito senza `--output-descriptor` e senza
  `--output-reconciliation`;
- arricchita la diagnostica T30 di `memoria mvp demo-build` distinguendo i
  documenti selezionati mancanti dalla riconciliazione in:
  presenti nei profili demo selezionati, assenti dai profili demo selezionati,
  senza claim candidati nel ledger, oppure con claim solo fuori dai profili demo;
- la prova read-only reale sulla run candidata conferma il blocco operativo:
  `legacy_csv:a4ac96061a2381b5` e' presente nei profili demo selezionati ma
  non ha claim candidati nel ledger, mentre `local_docx:4c2ad1d2ab937913` e'
  presente nei profili demo selezionati ma i claim candidati esistenti sono
  fuori dal perimetro Andreoli/Balboni;
- la stessa prova reale resta correttamente bloccata con
  `Readiness: blocked_for_internal_demo`, copertura documenti `2/4`, famiglie
  coperte `partigiani_italia` e famiglie mancanti `legacy_csv`, `local_docx`;
- test mirati passanti:
  `.\.venv\Scripts\python.exe -m unittest tests.test_mvp_demo_descriptor tests.test_memoria_diagnostic_cli`
  (`37 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- verificato in sola lettura che restano assenti
  `P:\Comune\Me.Mo.Ri.a\database\memoria_mvp_demo.active.json` e
  `P:\Comune\Me.Mo.Ri.a\risultati\runs\prova-preview-profili-5-reviewed-01-pipeline\mvp_demo_reconciliation_table.md`;
- reso simmetrico l'output di `memoria mvp demo-build`: oltre ai
  `MISSING_DOCUMENT`, ora stampa anche i `COVERED_DOCUMENT`;
- la prova read-only reale mostra ora esplicitamente che i due documenti coperti
  sono `partigiani_italia:b45553cd6b1673d8` e
  `partigiani_italia:b6b3c9e526723a27`, mentre restano mancanti
  `legacy_csv:a4ac96061a2381b5` e `local_docx:4c2ad1d2ab937913`;
- test CLI passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_memoria_diagnostic_cli`
  (`32 tests`, `OK`);
- test builder passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_mvp_demo_descriptor`
  (`4 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- corretto `memoria mvp demo-build`: una run con readiness
  `blocked_for_internal_demo` ora termina con exit code `1`;
- il comando valuta la readiness prima di scrivere e non crea
  `--output-descriptor` o `--output-reconciliation` quando il gate e' bloccato;
- rinominata nell'output CLI la voce ambigua `Famiglie fonte` in
  `Famiglie coperte nel descriptor`, per distinguere copertura reale e
  perimetro selezionato;
- aggiunto test CLI che passa output espliciti a una run bloccata e verifica
  che nessun file venga scritto;
- test CLI passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_memoria_diagnostic_cli`
  (`32 tests`, `OK`);
- test builder passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_mvp_demo_descriptor`
  (`4 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- prova read-only reale ripetuta: `memoria mvp demo-build` sulla run candidata
  ora esce con codice `1`, stampa `Readiness: blocked_for_internal_demo` e
  conferma `nessun output e' stato scritto`;
- verificato in sola lettura che restano assenti
  `P:\Comune\Me.Mo.Ri.a\database\memoria_mvp_demo.active.json` e
  `P:\Comune\Me.Mo.Ri.a\risultati\runs\prova-preview-profili-5-reviewed-01-pipeline\mvp_demo_reconciliation_table.md`;
- arricchito il gate `readiness` con famiglie fonte selezionate, famiglie
  coperte, famiglie mancanti, documenti sorgente coperti e documenti sorgente
  mancanti;
- `memoria mvp demo-build` stampa ora gli ID mancanti utili a riallineare la
  run canonica senza aprire il JSON;
- test builder passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_mvp_demo_descriptor`
  (`4 tests`, `OK`);
- test CLI passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_memoria_diagnostic_cli`
  (`31 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- prova read-only reale ripetuta:
  `.\.venv\Scripts\memoria.exe mvp demo-build --data-root "P:\Comune\Me.Mo.Ri.a" --run-id "prova-preview-profili-5-reviewed-01-pipeline"`;
- risultato della prova reale dettagliato: famiglie selezionate
  `legacy_csv`, `local_docx`, `partigiani_italia`; famiglie coperte
  `partigiani_italia`; famiglie mancanti `legacy_csv`, `local_docx`;
- documenti T29 mancanti nella riconciliazione della run candidata:
  `legacy_csv:a4ac96061a2381b5` e `local_docx:4c2ad1d2ab937913`;
- documenti T29 coperti nella riconciliazione della run candidata: `2/4`;
- verificato in sola lettura che il dry-run non ha creato
  `P:\Comune\Me.Mo.Ri.a\database\memoria_mvp_demo.active.json` ne'
  `P:\Comune\Me.Mo.Ri.a\risultati\runs\prova-preview-profili-5-reviewed-01-pipeline\mvp_demo_reconciliation_table.md`;
- aggiunto gate `readiness` al builder `mvp_demo_descriptor`;
- il descriptor ora distingue una run `ready_for_internal_demo` da una
  `blocked_for_internal_demo` in base ai criteri minimi T30 osservabili nella
  riconciliazione;
- errori bloccanti rilevati: nessuna riga di riconciliazione nel perimetro,
  meno di due famiglie fonte riconciliate, profilo principale senza righe;
- warning rilevati: documenti selezionati T29 senza righe di riconciliazione;
- `memoria mvp demo-build` stampa `Readiness`, errori e warning nel dry-run;
- test builder passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_mvp_demo_descriptor`
  (`4 tests`, `OK`);
- test CLI passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_memoria_diagnostic_cli`
  (`31 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- prova read-only reale ripetuta:
  `.\.venv\Scripts\memoria.exe mvp demo-build --data-root "P:\Comune\Me.Mo.Ri.a" --run-id "prova-preview-profili-5-reviewed-01-pipeline"`;
- risultato della prova reale aggiornato: `Readiness:
  blocked_for_internal_demo`, errore
  `multi_source_reconciliation_requires_at_least_two_source_families`, warning
  `selected_documents_without_reconciliation_rows`;
- verificato in sola lettura che il dry-run non ha creato
  `P:\Comune\Me.Mo.Ri.a\database\memoria_mvp_demo.active.json` ne'
  `P:\Comune\Me.Mo.Ri.a\risultati\runs\prova-preview-profili-5-reviewed-01-pipeline\mvp_demo_reconciliation_table.md`;
- aggiunto comando CLI preview-only `memoria mvp demo-build`;
- `demo-build` legge una run esistente e prepara il payload del descrittore
  demo e la sintesi di riconciliazione usando il builder
  `mvp_demo_descriptor`, ma non scrive nulla se non sono passati
  `--output-descriptor` e/o `--output-reconciliation`;
- `memoria mvp status` include ora il dry-run `memoria mvp demo-build` nel
  walkthrough operativo;
- test mirato CLI passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_memoria_diagnostic_cli`
  (`31 tests`, `OK`);
- test builder passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_mvp_demo_descriptor`
  (`3 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- prova help installabile passante:
  `.\.venv\Scripts\memoria.exe mvp demo-build --help`;
- prova read-only sul data root esterno eseguita senza output path:
  `.\.venv\Scripts\memoria.exe mvp demo-build --data-root "P:\Comune\Me.Mo.Ri.a" --run-id "prova-preview-profili-5-reviewed-01-pipeline"`;
- risultato della prova reale: `20` righe di riconciliazione, `10` decisioni
  sostanziali, `8` verified facts preview e `2` ProfilePatch preview letti
  dalla run candidata;
- la stessa prova evidenzia il blocco T30 ancora aperto: con il perimetro
  documentale T29, la run candidata espone solo `partigiani_italia` come
  famiglia fonte nella riconciliazione, quindi il merge multi-fonte
  `legacy_csv`/`local_docx`/`partigiani_italia` non e' ancora soddisfatto;
- verificato in sola lettura che
  `P:\Comune\Me.Mo.Ri.a\database\memoria_mvp_demo.active.json` e
  `P:\Comune\Me.Mo.Ri.a\risultati\runs\prova-preview-profili-5-reviewed-01-pipeline\mvp_demo_reconciliation_table.md`
  non sono stati creati da questo dry-run;
- aggiunto builder preview-only
  `caduti_fonti_report.document_analysis.mvp_demo_descriptor`;
- il builder prepara `MemoriaMvpDemoDescriptor` e
  `mvp_demo_reconciliation_table.md` da una sola run canonica gia' esistente,
  leggendo il ledger consolidato e gli artefatti `historian_review`;
- il builder seleziona il perimetro T29/T30:
  `person:purocielo:andreoli-dino`, contrasto
  `person:purocielo:balboni-william`, e i quattro documenti candidati;
- la tabella di riconciliazione espone `claim`, `fonte`, `metodo`,
  `review_status` e compatibilita' (`corroborated`, `divergent`,
  `single_source`);
- il payload mantiene safety flags espliciti:
  `preview_only=true`, nessuna decisione applicata, nessun verified fact
  canonico creato, nessuna ProfilePatch applicata e nessuna modifica ai
  profili canonici;
- se non vengono passati output path, il builder restituisce solo il payload e
  non crea `memoria_mvp_demo.active.json` ne' la tabella markdown;
- test mirato passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_mvp_demo_descriptor`
  (`3 tests`, `OK`);
- regressione diagnostica passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_memoria_diagnostic_cli`
  (`30 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- nessuna scrittura nel data root esterno eseguita in questo incremento;
- `memoria mvp demo` disponibile nella CLI Python installabile;
- il comando legge in sola lettura il descrittore
  `<data-root>/database/memoria_mvp_demo.active.json`;
- se il descrittore manca, il comando segnala il path atteso senza crearlo;
- se il descrittore esiste, mostra `contract_version`, `status`,
  `preview_only`, `publication_status`, `run_id`, `run_dir`, profili,
  documenti, famiglie fonte, artefatti e safety flags;
- `memoria mvp status` include `memoria mvp demo` nel walkthrough read-only;
- test mirati passanti:
  `.\.venv\Scripts\python.exe -m unittest tests.test_memoria_diagnostic_cli`
  (`30 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- prova read-only sul data root esterno eseguita:
  `.\.venv\Scripts\memoria.exe mvp demo`;
- risultato della prova reale: descrittore non ancora presente in
  `P:\Comune\Me.Mo.Ri.a\database\memoria_mvp_demo.active.json`, nessun file
  creato o modificato;
- T30 resta aperto: mancano ancora creazione/riallineamento della run canonica,
  descrittore reale nel data root e tabella di riconciliazione multi-fonte.

Evidenza T29:

- `funding-demo-t29-contract.md` presente;
- caso principale selezionato: `person:purocielo:andreoli-dino`;
- caso di contrasto leggero selezionato: `person:purocielo:balboni-william`;
- documenti candidati identificati per ID senza copiarli nei repository:
  `legacy_csv:a4ac96061a2381b5`, `local_docx:4c2ad1d2ab937913`,
  `partigiani_italia:b45553cd6b1673d8`,
  `partigiani_italia:b6b3c9e526723a27`;
- famiglie fonte selezionate: `legacy_csv`, `local_docx`,
  `partigiani_italia`;
- criterio di riconciliazione multi-fonte definito;
- contratto del descrittore
  `<data-root>/database/memoria_mvp_demo.active.json` definito;
- artifact map e walkthrough 7-10 minuti definiti;
- feedback trigger candidato identificato per T31;
- gap tecnici puntuali T30-T32 elencati;
- validazioni read-only T29 eseguite:
  `memoria mvp status`, `memoria review status`,
  `memoria review decisions`, `memoria review work`,
  `memoria consolidate status`;
- nessuna pipeline, OCR, ricerca live o scrittura nel data root eseguita.

Evidenze baseline gia' disponibili:

- `memoria data-root` funziona;
- `memoria inventory` funziona senza opzioni;
- `memoria doctor` conferma data root e repository sibling;
- `memoria inventory --section risultati` produce un riepilogo leggero;
- `memoria inventory --section documenti_processati` produce un riepilogo
  leggero;
- `memoria inventory --section all` produce riepilogo delle sezioni supportate;
- `memoria inventory --output markdown` produce markdown leggibile;
- `pytest` passa nelle validazioni precedenti;
- il data root esterno resta esterno:

```text
P:\Comune\Me.Mo.Ri.a
```

- nessun dato reale e' stato copiato nei repository Git.

Evidenza T4:

- `daily-agent-procedure.md` presente;
- `agent-session-prompt.md` presente;
- `current-next-increment.md` trasformato in documento operativo;
- `02-technical-roadmap.md` con milestone ID, dipendenze, criteri di ingresso e
  criteri di uscita.

Evidenza T5:

- `mvp-demo-scoping-read-only.md` presente;
- perimetro demo MVP read-only descritto;
- criteri di selezione di un set piccolo e controllato definiti;
- decisione metodologica registrata nel decision log.

Evidenza T6:

- `memoria-sources/registry/camalanca_fonti.yaml` presente;
- `memoria-sources/source_profiles/` presente;
- `memoria-sources/source_strategies/` presente;
- `memoria-sources/source_result_logic/` presente;
- `memoria-sources/source_detail_logic/` presente;
- `memoria-engine` risolve il catalogo fonti da `../memoria-sources` come
  posizione primaria;
- fallback legacy su `memoria-engine/ricerche` mantenuto;
- piano residui post-migrazione documentato.

Evidenza T7:

- wrapper PowerShell principali puntano a
  `..\memoria-sources\registry\camalanca_fonti.yaml`;
- `scripts/memoria.ps1` cerca `memoria-sources` prima dei fallback legacy;
- registry e strategie in `memoria-sources` usano path relativi al nuovo
  catalogo;
- `memoria-engine/ricerche/SOURCE_CATALOG_LEGACY.md` marca i duplicati
  `source_*` come fallback transitorio;
- documentazione operativa aggiornata sui path source;
- test mirati e validazioni registry passano.

Evidenza T8:

- `memoria-engine/ricerche/source_profiles` rimosso;
- `memoria-engine/ricerche/source_strategies` rimosso;
- `memoria-engine/ricerche/source_result_logic` rimosso;
- `memoria-engine/ricerche/source_detail_logic` rimosso;
- test e loader aggiornati per usare `memoria-sources`;
- `SOURCE_CATALOG_LEGACY.md` aggiornato come marker di rimozione;
- scansione `ricerche/source_*` senza risultati;
- suite estesa T8 passante.

Evidenza T9:

- `knowledge-residuals-classification.md` presente;
- `places/` classificato come knowledge di dominio versionabile;
- `military_glossaries/` classificato come glossario di dominio versionabile;
- destinazioni `memoria-knowledge/places/` e
  `memoria-knowledge/glossary/military/` confermate;
- loader, wrapper e test da aggiornare identificati;
- decisione di ownership registrata nel decision log.

Evidenza T10:

- `memoria-knowledge/places/places.index.jsonld` presente;
- `memoria-knowledge/places/ca-di-malanca.jsonld` presente;
- `memoria-knowledge/places/purocielo.jsonld` presente;
- `memoria-knowledge/glossary/military/de.basic.jsonld` presente;
- `memoria-engine` risolve i default knowledge per luoghi e glossari militari
  da `../memoria-knowledge`;
- wrapper diretti aggiornati sui default knowledge;
- fallback legacy mantenuto solo fino alla rimozione T11;
- test mirati T10 passanti.

Evidenza T11:

- `memoria-engine/ricerche/places` rimosso;
- `memoria-engine/ricerche/military_glossaries` rimosso;
- `memoria-engine/ricerche` non contiene piu' i residui knowledge migrati;
- riferimenti runtime legacy a `ricerche/places` e
  `ricerche/military_glossaries` assenti;
- documentazione operativa aggiornata: i cataloghi vivono in
  `memoria-knowledge`;
- test mirati T11 passanti.

Evidenza T12:

- `person-profile-seed-audit.md` presente;
- `person_profiles/` classificato come profili reali/preview, non fixture
  sintetica e non knowledge generica;
- `caduti_purocielo.csv` classificato come seed legacy reale, dismesso per
  nuovi profili operativi;
- `mvp/` classificato come perimetro MVP preview-only: metodo in bootstrap,
  artefatti operativi nel data root esterno;
- riferimenti runtime e documentali da aggiornare identificati;
- decisione di ownership registrata nel decision log;
- nessuna migrazione fisica dei file eseguita in T12.

Evidenza T13:

- `profile-seed-default-hardening.md` presente;
- CLI Python principali richiedono `--csv` o `--profiles-index` espliciti;
- `person_profiles.py` richiede `--output-dir` esplicito;
- wrapper PowerShell principali richiedono `-ProfilesIndex` esplicito;
- `run_caduti_fonti_report.ps1` richiede `-Csv` esplicito;
- `scripts/memoria.ps1` non ricade piu' su
  `memoria-engine\ricerche\person_profiles`;
- scansioni mirate senza default runtime legacy residui;
- test mirati T13 passanti: `46 tests`, `OK`.

Evidenza T13b:

- `memoria profiles status` disponibile nella CLI Python diagnostica;
- il comando risolve l'indice profili ordinario da
  `<data-root>\ricerche\person_profiles\purocielo.index.jsonld`;
- nessun fallback verso `memoria-engine\ricerche\person_profiles`;
- output con path risolto, conteggi profili, file mancanti e distribuzione di
  `profile_status`, `review_status`, `publication_status`;
- `profile-status-cli.md` presente;
- `cli-discovery-report.md` aggiornato;
- verifica read-only sul data root esterno passante:
  `57` profili indicizzati, `57` caricati, `0` file mancanti;
- suite mirata CLI/profili passante: `64 tests`, `OK`;
- suite completa `pytest` passante: `649 passed`.

Evidenza T14:

- `llm-prompts-classification.md` presente;
- `llm_prompts/` classificato come contratti e regole operative LLM
  preview-only;
- ownership primaria proposta: `memoria-rules`;
- destinazione proposta:
  `memoria-rules/llm_prompts/chunk_classification/`;
- riferimenti runtime, test, wrapper e documentazione da aggiornare identificati;
- decisione metodologica registrata nel decision log;
- nessuna migrazione fisica eseguita in T14;
- nessun dato reale copiato nei repository;
- nessun OCR, extraction, JSON-LD o pipeline lanciato.

Evidenza T15:

- `memoria-rules/llm_prompts/chunk_classification/README.md` presente;
- `memoria-rules/llm_prompts/chunk_classification/chunk_classification.gemma3-4b.prompt.md`
  presente;
- `memoria-rules/llm_prompts/chunk_classification/chunk_classification.schema.json`
  presente;
- `memoria-engine` espone un resolver per contratti LLM chunk classification che
  preferisce `../memoria-rules`;
- fallback legacy verso `memoria-engine\ricerche\llm_prompts` mantenuto solo per
  la transizione e rimosso in T16;
- `tests.test_llm_chunk_classifier` aggiornato sul resolver e passante:
  `15 tests`, `OK`;
- nessun dato reale copiato nei repository;
- nessun OCR, extraction, JSON-LD o pipeline lanciato.

Evidenza T16:

- `memoria-engine/ricerche/llm_prompts` rimosso;
- `llm_chunk_classifier.py` risolve i contratti LLM solo da
  `../memoria-rules/llm_prompts/chunk_classification/`;
- `tests.test_llm_chunk_classifier` verifica che lo schema non provenga da
  `ricerche`;
- riferimenti runtime/documentali al path legacy assenti o esplicitamente
  storici;
- test mirati LLM chunk classifier passanti: `15 tests`, `OK`;
- nessun dato reale copiato nei repository;
- nessun OCR, extraction, JSON-LD o pipeline lanciato.

Evidenza T17:

- `profile-editorial-status-contract.md` presente;
- collocazione canonica dei campi decisa: `metadata.profile_status`,
  `metadata.review_status`, `metadata.publication_status`;
- distinzione tra stato scheda/profilo e `search_hints[].review_status`
  documentata;
- valori iniziali per profili seed/preview non revisionati definiti;
- T18 preparato come dry-run read-only prima di qualunque scrittura sui profili
  reali;
- nessun profilo reale modificato;
- nessun OCR, extraction, JSON-LD o pipeline lanciato.

Evidenza T18:

- `profile-editorial-status-dry-run.md` presente;
- dry-run read-only sui profili canonici completato tramite
  `memoria profiles status`;
- indice profili canonico risolto da
  `<data-root>\ricerche\person_profiles\purocielo.index.jsonld`;
- profili indicizzati: `57`;
- profili caricati: `57`;
- file profilo mancanti: `0`;
- profili privi di `metadata.profile_status`: `57`;
- profili privi di `metadata.review_status`: `57`;
- profili privi di `metadata.publication_status`: `57`;
- profili privi di tutti e tre i campi editoriali canonici: `57`;
- oggetto `metadata` presente in tutti i profili caricati;
- campi `search_hints[].review_status` osservati: `279`, documentati come
  fuori dal piano di patch;
- piano di patch limitato a `metadata` documentato;
- strategia di backup e rollback per eventuale incremento applicativo
  successivo documentata;
- test CLI da aggiornare o aggiungere elencati;
- nessun profilo reale modificato;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Evidenza Q1:

- `memoria-engine-modularity-audit.md` presente;
- moduli Python piu' grandi elencati per righe;
- peso per area documentato:
  `document_analysis` `25455` righe, root package `12008` righe,
  `connectors` `7414` righe;
- responsabilita' principali dei moduli critici documentate;
- rischi principali dei moduli critici documentati;
- candidati micro-refactor ordinati per rischio e valore;
- test minimi identificati per ogni candidato;
- primo Q2 consigliato: estrarre parser Markdown table/card da
  `document_analysis/mvp_review_focus_table.py`;
- nessun codice spostato;
- nessun comportamento esterno modificato;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Evidenza Q2 `mvp_review_focus_table`:

- helper interno `mvp_review_markdown.py` creato;
- parsing Markdown table/card isolato fuori da
  `document_analysis/mvp_review_focus_table.py`;
- `mvp_review_focus_table.py` mantiene funzioni pubbliche e CLI invariate;
- output Markdown e conversione decisioni preservati dai test mirati;
- test baseline pre-refactor passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_mvp_review_focus_table`;
- test post-refactor passanti:
  `.\.venv\Scripts\python.exe -m unittest tests.test_mvp_review_focus_table`
  (`11 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Evidenza Q2 `mvp_pilot_summary` rendering diagnostico:

- helper interno `mvp_pilot_summary_markdown.py` creato;
- rendering di scorecard pacchetto MVP, stato ingest documentale e diagnostica
  segnale MVP isolato fuori da
  `document_analysis/mvp_pilot_summary.py`;
- `mvp_pilot_summary.py` mantiene payload `MvpPilotSummary`, funzione pubblica
  `render_mvp_pilot_summary_markdown`, builder e CLI invariati;
- test mirato nuovo `tests.test_mvp_pilot_summary_rendering` aggiunto per
  proteggere i blocchi diagnostici renderizzati;
- test baseline pre-refactor passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_document_research_pipeline`
  (`11 tests`, `OK`);
- test post-refactor passanti:
  `.\.venv\Scripts\python.exe -m unittest tests.test_mvp_pilot_summary_rendering tests.test_document_research_pipeline`
  (`12 tests`, `OK`);
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Evidenza Q2 `local_processing_runner` manifest/log:

- helper interno `local_processing_manifest.py` creato;
- costruzione dei record step manifest, record skipped, rendering
  `run_summary.md` e calcolo durata isolati fuori da
  `document_analysis/local_processing_runner.py`;
- `local_processing_runner.py` mantiene API pubblica, sequenza step, nomi step,
  stati, path manifest/log e righe log osservabili invariati;
- test mirato nuovo `tests.test_local_processing_manifest` aggiunto per
  proteggere shape dei record manifest e linee summary osservabili;
- test baseline pre-refactor passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_local_document_processing_runner`
  (`16 tests`, `OK`);
- test post-refactor passanti:
  `.\.venv\Scripts\python.exe -m unittest tests.test_local_processing_manifest tests.test_local_document_processing_runner`
  (`19 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Evidenza Q2 `export_obsidian_vault` rendering MVP vault:

- helper interno `export_obsidian_vault_markdown.py` creato;
- rendering Markdown del vault MVP pilota isolato fuori da
  `caduti_fonti_report.export_obsidian_vault`;
- `export_obsidian_vault.py` mantiene CLI, API pubbliche, selezione profili,
  scrittura file, preservazione note editoriali e shape del vault invariati;
- test mirato nuovo `tests.test_export_obsidian_vault_markdown` aggiunto per
  proteggere shape Markdown osservabile del renderer MVP documenti;
- test baseline pre-refactor passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_export_obsidian_vault`
  (`8 tests`, `OK`);
- test post-refactor passanti:
  `.\.venv\Scripts\python.exe -m unittest tests.test_export_obsidian_vault_markdown tests.test_export_obsidian_vault`
  (`9 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- suite completa passante:
  `.\.venv\Scripts\python.exe -m pytest`
  (`654 passed`);
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Evidenza Q2 `bundesarchiv_invenio_executor` parser PrimeFaces/tree:

- helper interno `bundesarchiv_invenio_parsing.py` creato;
- dataclass `InvenioCandidate`, parsing JSF update, parsing nodi
  PrimeFaces/tree, fallback pannelli Treffer e deduplica semantica isolati fuori
  da `connectors/bundesarchiv_invenio_executor.py`;
- `bundesarchiv_invenio_executor.py` mantiene API pubblica, wrapper
  `_extract_tree_node_candidates`, wrapper `_extract_panel_hit_candidates`,
  raccolta response da page/debug, scrittura diagnostica, selettori, timing e
  richieste Ajax invariati;
- test mirato esteso `tests.test_bundesarchiv_invenio_executor` per proteggere
  il helper di parsing senza Playwright;
- test baseline pre-refactor passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_bundesarchiv_invenio_executor`
  (`2 tests`, `OK`);
- test post-refactor passanti:
  `.\.venv\Scripts\python.exe -m unittest tests.test_bundesarchiv_invenio_executor`
  (`3 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- suite completa passante:
  `.\.venv\Scripts\python.exe -m pytest`
  (`655 passed`);
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Evidenza T19:

- `cli-operativa-cross-platform-plan.md` presente;
- CLI Python `memoria` confermata come superficie canonica futura
  cross-platform;
- `scripts/memoria.ps1` classificato come wrapper compat/Windows e superficie
  pratica per l'MVP finanziatori, non come destinazione architetturale
  definitiva;
- futuro wrapper Linux classificato come facciata sottile, senza duplicazione
  della logica operativa;
- confine dei wrapper sottili documentato;
- priorita' dei primi workflow da portare o esporre via bridge Python
  documentata: review read-only, review decisioni preview, consolidamento
  preview, sources online/offline, wrapper MVP workspace;
- criteri di compatibilita' definiti per output, selezione run, file sessione,
  data-root, flag operativi ed exit code;
- contratti di sessione da preservare documentati:
  `memoria_review_session.active.json`,
  `memoria_consolidate_session.active.json` e
  `memoria_sources_online_session.active.json`;
- nessuna migrazione funzionale richiesta per l'MVP finanziatori;
- `cli-discovery-report.md` aggiornato con rimando al piano T19;
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Evidenza Q2 `candidate_claims` diagnostica/skipped claim:

- helper interno `candidate_claim_diagnostics.py` creato;
- diagnostica funnel claim isolata fuori da
  `document_analysis/candidate_claims.py`;
- `candidate_claims.py` mantiene API pubbliche, CLI, costruzione claim,
  skipped claim, deduplica e rendering Markdown invariati;
- test mirato nuovo aggiunto in `tests.test_document_candidate_claims` per
  proteggere conteggi di contesto, motivi skip, azioni consigliate e stati
  editoriali della diagnostica;
- test baseline pre-refactor passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_document_candidate_claims`
  (`11 tests`, `OK`);
- test post-refactor passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_document_candidate_claims`
  (`12 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- suite completa passante:
  `.\.venv\Scripts\python.exe -m pytest`
  (`656 passed`);
- nessun cambio a `claim_id`, `review_status`, motivi di skip o payload
  diagnostici;
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Evidenza Q2 `candidate_claims` skipped claim helper:

- helper interno `candidate_claim_skips.py` creato;
- costruzione degli skipped claim e degli skipped structured document isolata
  fuori da `document_analysis/candidate_claims.py`;
- selezione dei candidate link per skipped entity e raccomandazione next action
  isolate nello stesso helper puro;
- `candidate_claims.py` mantiene API pubbliche, CLI, costruzione claim,
  deduplica, diagnostica funnel e rendering Markdown invariati;
- test mirato nuovo aggiunto in `tests.test_document_candidate_claims` per
  proteggere candidate profile ids, candidate link ids, identificativi skipped,
  azioni consigliate e stati editoriali;
- test baseline pre-refactor passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_document_candidate_claims`
  (`12 tests`, `OK`);
- test post-refactor passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_document_candidate_claims`
  (`13 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- suite completa passante:
  `.\.venv\Scripts\python.exe -m pytest`
  (`657 passed`);
- nessun cambio a motivi di skip, candidate profile ids, candidate link ids,
  `review_status`, `publication_status` o identificativi skipped;
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Evidenza Q2 `german_docs_downloader` rendering manifest:

- helper interno `german_docs_manifest.py` creato;
- rendering Markdown del manifest German Docs isolato fuori da
  `document_analysis/german_docs_downloader.py`;
- `german_docs_downloader.py` mantiene download, Playwright, registrazione
  sidecar, manifest JSON, CLI e path output invariati;
- test mirato nuovo aggiunto in `tests.test_german_docs_downloader` per
  proteggere rendering del contesto archivistico, nodi Delo, documenti ed
  excerpt lunghi;
- test baseline pre-refactor passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_german_docs_downloader`
  (`7 tests`, `OK`);
- test post-refactor passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_german_docs_downloader`
  (`8 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- suite completa passante:
  `.\.venv\Scripts\python.exe -m pytest`
  (`658 passed`);
- nessun cambio a download, Playwright, registrazione sidecar, manifest JSON,
  CLI, path output o output Markdown osservabile;
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Evidenza Q2 `mvp_consolidated_review_ledger` rendering Markdown:

- helper interno `mvp_consolidated_review_ledger_markdown.py` creato;
- rendering Markdown del Consolidated Review Ledger MVP isolato fuori da
  `document_analysis/mvp_consolidated_review_ledger.py`;
- `mvp_consolidated_review_ledger.py` mantiene consolidamento summary,
  lettura evidence store, scrittura JSON/Markdown, CLI e path output invariati;
- test mirato nuovo aggiunto in `tests.test_mvp_consolidated_review_ledger`
  per proteggere front matter, sezioni vuote e warning del renderer;
- test baseline pre-refactor passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_mvp_consolidated_review_ledger`
  (`8 tests`, `OK`);
- test post-refactor passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_mvp_consolidated_review_ledger`
  (`9 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- suite completa passante:
  `.\.venv\Scripts\python.exe -m pytest`
  (`659 passed`);
- nessun cambio a consolidamento ledger, evidence store, CLI, path output,
  JSON prodotto o output Markdown osservabile;
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Evidenza Q2 `mvp_review_dashboard` rendering Markdown:

- helper interno `mvp_review_dashboard_markdown.py` creato;
- rendering Markdown della Review Dashboard MVP isolato fuori da
  `document_analysis/mvp_review_dashboard.py`;
- `mvp_review_dashboard.py` mantiene build dashboard, caricamento input,
  sintesi verified facts/profile patch/sandbox, scrittura JSON/Markdown, CLI e
  path output invariati;
- test mirato nuovo aggiunto in `tests.test_mvp_review_dashboard` per
  proteggere front matter, file di lavoro, conteggi oggetti e warning del
  renderer;
- test baseline pre-refactor passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_mvp_review_dashboard`
  (`5 tests`, `OK`);
- test post-refactor passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_mvp_review_dashboard`
  (`6 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- suite completa passante:
  `.\.venv\Scripts\python.exe -m pytest`
  (`660 passed`);
- nessun cambio a build dashboard, sintesi preview, CLI, path output, JSON
  prodotto o output Markdown osservabile;
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Evidenza Q2 `mvp_historical_review_targets` rendering Markdown:

- helper interno `mvp_historical_review_targets_markdown.py` creato;
- rendering Markdown dei Target storici revisionabili MVP isolato fuori da
  `document_analysis/mvp_historical_review_targets.py`;
- `mvp_historical_review_targets.py` mantiene selezione target da review queue,
  lettura evidence store read-only, match decisioni storiche, scrittura
  JSON/Markdown, CLI e path output invariati;
- test mirato nuovo aggiunto in `tests.test_mvp_historical_review_targets` per
  proteggere front matter, run store, azioni ammesse, contesto, provenance e
  stato vuoto del renderer;
- test baseline pre-refactor passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_mvp_historical_review_targets`
  (`4 tests`, `OK`);
- test post-refactor passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_mvp_historical_review_targets`
  (`5 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- suite completa passante:
  `.\.venv\Scripts\python.exe -m pytest`
  (`661 passed`);
- nessun cambio a selezione target, evidence store read-only, decision matching,
  CLI, path output, JSON prodotto o output Markdown osservabile;
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Evidenza Q2 `mvp_review_session` rendering Markdown:

- helper interno `mvp_review_session_markdown.py` creato;
- rendering Markdown della Sessione revisione MVP isolato fuori da
  `document_analysis/mvp_review_session.py`;
- `mvp_review_session.py` mantiene build sessione, calcolo stati profilo,
  focus review, template decisioni, copertura ledger/evidence store, scrittura
  JSON/Markdown, CLI e path output invariati;
- test mirato nuovo aggiunto in `tests.test_mvp_review_session` per proteggere
  front matter, warning, stato vuoto e copertura ledger del renderer;
- test baseline pre-refactor passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_mvp_review_session`
  (`5 tests`, `OK`);
- test post-refactor passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_mvp_review_session`
  (`6 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- suite completa passante:
  `.\.venv\Scripts\python.exe -m pytest`
  (`662 passed`);
- nessun cambio a build sessione, focus review, template decisioni, copertura
  ledger/evidence store, CLI, path output, JSON prodotto o output Markdown
  osservabile;
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Evidenza Q2 `mvp_review_decisions` rendering Markdown:

- helper interno `mvp_review_decisions_markdown.py` creato;
- rendering Markdown del riepilogo Decisioni review queue MVP isolato fuori da
  `document_analysis/mvp_review_decisions.py`;
- `mvp_review_decisions.py` mantiene validazione decisioni, copertura file
  decisioni, sintesi sessione storici, conteggi, scrittura JSON/Markdown, CLI e
  path output invariati;
- test mirato nuovo aggiunto in `tests.test_mvp_review_decisions` per
  proteggere copertura file decisioni, candidate, contesto, vincoli e stati
  vuoti del renderer;
- test baseline pre-refactor passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_mvp_review_decisions`
  (`5 tests`, `OK`);
- test post-refactor passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_mvp_review_decisions`
  (`6 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- suite completa passante:
  `.\.venv\Scripts\python.exe -m pytest`
  (`663 passed`);
- nessun cambio a validazione decisioni, copertura file decisioni, sintesi
  sessione storici, CLI, path output, JSON prodotto o output Markdown
  osservabile;
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Evidenza Q2 `mvp_review_queue` rendering Markdown:

- helper interno `mvp_review_queue_markdown.py` creato;
- rendering Markdown della Review queue MVP isolato fuori da
  `document_analysis/mvp_review_queue.py`;
- `mvp_review_queue.py` mantiene build queue, template decisioni, scrittura
  JSON/Markdown, CLI e path output invariati;
- test mirato nuovo aggiunto in `tests.test_mvp_review_queue` per proteggere
  dettagli documento, contesto, motivi, vincoli e stati vuoti del renderer;
- test baseline pre-refactor passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_mvp_review_queue`
  (`2 tests`, `OK`);
- test post-refactor passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_mvp_review_queue`
  (`3 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- suite completa passante:
  `.\.venv\Scripts\python.exe -m pytest`
  (`664 passed`);
- nessun cambio a build queue, template decisioni, CLI, path output, JSON
  prodotto o output Markdown osservabile;
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Evidenza T20:

- `memoria review discover` disponibile nella CLI Python installabile;
- `memoria review status` disponibile nella CLI Python installabile;
- `memoria review work` disponibile nella CLI Python installabile;
- i tre comandi sono read-only: non creano sessioni, non applicano decisioni,
  non creano `verified_facts` e non modificano profili JSON-LD;
- `review discover` legge superficialmente `<data-root>\risultati\runs` e
  seleziona le run candidate usando artefatti review gia' esistenti;
- `review status` mostra la sessione attiva se
  `<data-root>\database\memoria_review_session.active.json` esiste, altrimenti
  ricade su discovery read-only;
- `review work` mostra la worklist della sessione attiva esistente e rimanda ai
  comandi PowerShell per le decisioni preview;
- test mirati CLI passanti:
  `.\.venv\Scripts\python.exe -m unittest tests.test_memoria_diagnostic_cli`
  (`21 tests`, `OK`);
- help CLI verificato:
  `.\.venv\Scripts\memoria.exe review --help`;
- help comando verificato:
  `.\.venv\Scripts\memoria.exe review discover --help`;
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- suite completa passante:
  `.\.venv\Scripts\python.exe -m pytest`
  (`667 passed`);
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Evidenza T21:

- `memoria consolidate discover` disponibile nella CLI Python installabile;
- `memoria consolidate status` disponibile nella CLI Python installabile;
- i due comandi sono read-only: non creano sessioni consolidate, non rigenerano
  ledger, non scrivono nello store, non creano `verified_facts` e non modificano
  profili JSON-LD;
- `consolidate discover` legge superficialmente `<data-root>\risultati\runs` e
  seleziona le run consolidabili usando artefatti preview gia' esistenti;
- `consolidate status` mostra la sessione attiva se
  `<data-root>\database\memoria_consolidate_session.active.json` esiste,
  altrimenti ricade su discovery read-only;
- test mirati CLI passanti:
  `.\.venv\Scripts\python.exe -m unittest tests.test_memoria_diagnostic_cli`
  (`24 tests`, `OK`);
- help CLI verificato:
  `.\.venv\Scripts\memoria.exe consolidate --help`;
- help comando verificato:
  `.\.venv\Scripts\memoria.exe consolidate discover --help`;
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- suite completa passante:
  `.\.venv\Scripts\python.exe -m pytest`
  (`670 passed`);
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Evidenza T22:

- `memoria sources online discover` disponibile nella CLI Python installabile;
- `memoria sources online status` disponibile nella CLI Python installabile;
- `memoria sources offline discover` disponibile nella CLI Python installabile;
- `memoria sources offline status` disponibile nella CLI Python installabile;
- i quattro comandi sono read-only: non creano sessioni sources, cartelle
  intake, run, download, store, OCR, pipeline o modifiche ai profili JSON-LD;
- `sources online discover` legge superficialmente il registry fonti da
  `memoria-sources` con fallback compatibili, l'indice profili pilota dal data
  root e mostra fonti candidate;
- `sources online status` mostra la sessione attiva se
  `<data-root>\database\memoria_sources_online_session.active.json` esiste,
  altrimenti ricade su discovery read-only;
- `sources offline discover/status` mostrano un riepilogo superficiale di
  `documenti_da_processare` e `documenti_processati` senza scansione profonda;
- test mirati CLI passanti:
  `.\.venv\Scripts\python.exe -m unittest tests.test_memoria_diagnostic_cli`
  (`27 tests`, `OK`);
- help CLI verificato:
  `.\.venv\Scripts\memoria.exe sources --help`;
- help comandi verificati:
  `.\.venv\Scripts\memoria.exe sources online discover --help` e
  `.\.venv\Scripts\memoria.exe sources offline discover --help`;
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- suite completa passante:
  `.\.venv\Scripts\python.exe -m pytest`
  (`673 passed`);
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Evidenza T23:

- `scelta-architetturale-cloud-workspace.md` allineato alla roadmap tecnica;
- roadmap master aggiornata: il workspace operativo resta fuori dai repository
  Git, ma il path `P:\Comune\Me.Mo.Ri.a` e' ora backend locale compatibile, non
  vincolo architetturale unico;
- roadmap MVP aggiornata: il backend puo' essere locale o cloud purche' i dati
  reali restino fuori da Git;
- roadmap tecnica aggiornata con sequenza T23-T28:
  decisione cloud workspace pluggable, `WorkspaceStorage` locale, manifest
  provider-aware, pCloud read-only, pCloud write diagnostico e cache;
- decision log aggiornato con la scelta `WorkspaceStorage` pluggable;
- pCloud classificato come primo backend cloud candidato;
- la prima verifica pCloud prevista e' read-only via REST su cartelle esistenti,
  usando `listfolder` e salvando `folderid` dove utile;
- nessun driver cloud implementato;
- nessuna chiamata reale a pCloud eseguita;
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Evidenza T24:

- `memoria-engine/code/caduti_fonti_report/workspace_storage.py` presente;
- interfaccia Python `WorkspaceStorage` disponibile;
- `LocalWorkspaceStorage` implementa `exists`, `list_dir`, `read_bytes`,
  `write_bytes`, `mkdir` e `stat`;
- `memoria doctor` usa `LocalWorkspaceStorage` per verificare data root,
  cartelle richieste e repository sibling senza cambiare output osservabile;
- test unitari offline del driver local presenti in
  `memoria-engine/tests/test_workspace_storage.py`;
- test CLI mirati confermano `doctor` e i comandi diagnostici esistenti;
- test mirati passanti:
  `.\.venv\Scripts\python.exe -m unittest tests.test_workspace_storage tests.test_memoria_diagnostic_cli`
  (`31 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- suite completa passante:
  `.\.venv\Scripts\python.exe -m pytest`
  (`677 passed`);
- nessun driver pCloud implementato;
- nessuna chiamata cloud eseguita;
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Evidenza T25:

- `memoria-workspace/manifest.yml` supporta `workspace.provider`;
- il provider attivo e' `local`, con `workspace.root` sul backend locale
  compatibile `P:\Comune\Me.Mo.Ri.a`;
- il manifest descrive `providers.pcloud` come candidato read-only bloccato da
  supporto API, usando `credentials_ref` e senza salvare segreti;
- `resolve_data_root` legge il nuovo formato provider-aware;
- `--data-root` e `MEMORIA_DATA_ROOT` restano prioritari;
- il fallback legacy `data_root.windows_path` resta supportato;
- `memoria-workspace/EXTERNAL_DATA_ROOT.md` documenta il nuovo ordine di
  risoluzione;
- test mirati passanti:
  `.\.venv\Scripts\python.exe -m unittest tests.test_memoria_diagnostic_cli`
  (`30 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- verifica read-only del resolver passante:
  `.\.venv\Scripts\memoria.exe data-root`;
- suite completa passante:
  `.\.venv\Scripts\python.exe -m pytest`
  (`679 passed`);
- nessun driver pCloud implementato;
- nessuna chiamata cloud eseguita;
- nessun segreto salvato nel manifest;
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Evidenza T26a:

- `memoria review decisions` disponibile nella CLI Python installabile;
- il comando e' read-only: non crea sessioni, non registra decisioni, non
  modifica profili, `verified_facts`, store o artefatti canonici;
- se esiste una sessione review attiva, legge il summary decisioni collegato
  alla sessione;
- se non esiste una sessione attiva, usa la run candidata consigliata dalla
  discovery review read-only;
- output sintetico con run, path del summary decisioni, conteggio decisioni,
  decisioni storiche sostanziali e distribuzioni per `selected_action`,
  `decision_status` e `subject_kind`;
- help comando verificato:
  `.\.venv\Scripts\memoria.exe review decisions --help`;
- test mirati CLI passanti:
  `.\.venv\Scripts\python.exe -m unittest tests.test_memoria_diagnostic_cli`
  (`27 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- suite completa passante:
  `.\.venv\Scripts\python.exe -m pytest`
  (`684 passed`);
- nessun driver pCloud implementato;
- nessuna chiamata cloud eseguita;
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Evidenza T26b:

- `memoria mvp status` disponibile nella CLI Python installabile;
- il comando compone una vista read-only del walkthrough MVP demo locale;
- output sintetico con stato profili, review, decisioni review,
  consolidamento, registry fonti e intake offline;
- output con i comandi read-only gia' disponibili:
  `profiles status`, `review discover/status/work/decisions`,
  `consolidate status`, `sources online/offline status`;
- il comando non genera report, non crea run, non crea sessioni, non registra
  decisioni, non avvia OCR/pipeline e non modifica il data root;
- help comando verificato:
  `.\.venv\Scripts\memoria.exe mvp status --help`;
- test mirati CLI passanti:
  `.\.venv\Scripts\python.exe -m unittest tests.test_memoria_diagnostic_cli`
  (`28 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- suite completa passante:
  `.\.venv\Scripts\python.exe -m pytest`
  (`685 passed`);
- nessun driver pCloud implementato;
- nessuna chiamata cloud eseguita;
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Evidenza Q2 `memoria_cli` resolver data-root/manifest:

- helper interno `memoria-engine/code/caduti_fonti_report/workspace_resolver.py`
  creato;
- `DataRootResolution`, `DataRootResolutionError` e `resolve_data_root` isolati
  fuori da `memoria_cli.py`;
- `memoria_cli.py` mantiene re-export/import compatibile di `resolve_data_root`
  per i test e gli usi esistenti;
- risoluzione `--data-root`, `MEMORIA_DATA_ROOT`, manifest provider-aware e
  fallback legacy preservata;
- nessun cambio a comandi, output CLI, exit code, schema o workflow;
- test mirati passanti:
  `.\.venv\Scripts\python.exe -m unittest tests.test_memoria_diagnostic_cli`
  (`30 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- suite completa passante:
  `.\.venv\Scripts\python.exe -m pytest`
  (`679 passed`);
- nessun driver pCloud implementato;
- nessuna chiamata cloud eseguita;
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Evidenza Q2 `workspace_resolver` test dedicati:

- `memoria-engine/tests/test_workspace_resolver.py` creato;
- i test diretti di `resolve_data_root` sono stati spostati fuori da
  `tests.test_memoria_diagnostic_cli`;
- `tests.test_memoria_diagnostic_cli` resta focalizzato sui comandi CLI e sui
  bridge read-only;
- nessun codice runtime modificato;
- nessun cambio a comandi, output CLI, exit code, schema o workflow;
- test mirati passanti:
  `.\.venv\Scripts\python.exe -m unittest tests.test_workspace_resolver tests.test_memoria_diagnostic_cli`
  (`30 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- suite completa passante:
  `.\.venv\Scripts\python.exe -m pytest`
  (`679 passed`);
- nessun driver pCloud implementato;
- nessuna chiamata cloud eseguita;
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Evidenza Q2 `LocalWorkspaceStorage` path boundary:

- `memoria-engine/tests/test_workspace_storage.py` esteso con copertura sui
  path assoluti;
- path assoluti interni al workspace root accettati e normalizzati;
- path assoluti esterni al workspace root rigettati senza scritture;
- nessun codice runtime modificato;
- nessun cambio a comandi, output CLI, exit code, schema o workflow;
- test mirato passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_workspace_storage`
  (`5 tests`, `OK`);
- test mirati di contorno passanti:
  `.\.venv\Scripts\python.exe -m unittest tests.test_workspace_storage tests.test_workspace_resolver tests.test_memoria_diagnostic_cli`
  (`35 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- suite completa passante:
  `.\.venv\Scripts\python.exe -m pytest`
  (`681 passed`);
- nessun driver pCloud implementato;
- nessuna chiamata cloud eseguita;
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Evidenza Q2 `LocalWorkspaceStorage` directory entries:

- `memoria-engine/tests/test_workspace_storage.py` esteso con copertura sugli
  entry directory restituiti da `list_dir`;
- verificati path logico, flag `is_dir`/`is_file` e `size` assente per le
  cartelle;
- nessun codice runtime modificato;
- nessun cambio a comandi, output CLI, exit code, schema o workflow;
- test mirato passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_workspace_storage`
  (`6 tests`, `OK`);
- test mirati di contorno passanti:
  `.\.venv\Scripts\python.exe -m unittest tests.test_workspace_storage tests.test_workspace_resolver tests.test_memoria_diagnostic_cli`
  (`36 tests`, `OK`);
- test packaging passante:
  `.\.venv\Scripts\python.exe -m unittest tests.test_packaging`
  (`18 tests`, `OK`);
- suite completa passante:
  `.\.venv\Scripts\python.exe -m pytest`
  (`682 passed`);
- nessun driver pCloud implementato;
- nessuna chiamata cloud eseguita;
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

## Prossimo incremento candidato

T33 è chiuso. La golden run a tre casi
`funding-demo-golden-3cases-v1-pipeline` e' ora il descriptor demo attivo, come
demo revisionabile e non pubblicabile. La prova asciutta della presentazione in
sei schermate e' completata e l'handoff di revisione umana e' pronto; il
prossimo sotto-incremento candidato e' la revisione umana effettiva del racconto
e dei blocchi narrativi, mantenendo separati coorte pilota, tre casi e
patrimonio disponibile e senza introdurre bando, importo, finanziatore o
pubblicazione.

Possibili candidati successivi, da non avviare in questa sessione:

- verifica live read-only T26 su una cartella pCloud esistente, solo con
  credenziali nel `.env` locale e autorizzazione esplicita;
- T27 scrittura diagnostica pCloud solo dopo esito soddisfacente del read-only
  e con cartella diagnostica remota autorizzata;
- implementazione del candidato Q2 selezionato, solo dopo validazione dello
  scope e con comportamento invariato.

## Traccia parallela qualita'

La roadmap tecnica ora include la traccia Q - Qualita' e refactor continuo.

Questa traccia puo' procedere in parallelo agli incrementi T solo per audit
modulari o micro-refactor behavior-preserving, con test mirati e stop condition
esplicita. Non autorizza refactor ampi o cambi di CLI, schemi, workflow o
pipeline senza decisione dedicata.

Discovery Q2 del 2026-08-29: dopo la chiusura del refactor sui duplicati
documentali è stato selezionato un solo candidato tecnico residuo, da validare
prima dell'implementazione: isolare `_pilot_package_status_and_action` da
`memoria-engine/code/caduti_fonti_report/document_analysis/mvp_pilot_summary.py`
in un helper puro dedicato. I test minimi sono
`tests.test_mvp_pilot_summary_rendering`, con casi per documenti assenti, link
mancanti, segnali da revisionare e stato pronto. Il candidato deve mantenere
invariati `status`, `next_action`, scorecard, payload, Markdown, CLI, schema e
workflow. La discovery è stata read-only; nessun codice runtime o dato esterno
è stato modificato.

## Evidenza T31

Preflight read-only del 2026-07-14:

- azione candidata selezionata per la demo:
  `research-feedback-action:7bdbb2060d955baa`;
- profilo collegato dal piano:
  `person:purocielo:andreoli-dino`;
- documento trigger:
  `legacy_csv:a4ac96061a2381b5`;
- valore/trigger:
  `ANDREOLI DINO`, da `intestazione_pdf`, con indizi collegati a nome,
  formazione, luoghi e date;
- fonti suggerite dall'azione:
  `storia_memoria_bo`, `partigiani_italia`;
- piano fonte-specifico gia' presente nel summary preview:
  `feedback-search-plan:a19b13e6e3cd8b0d`;
- stato del piano:
  `ready_for_review`, `execution_allowed=false`,
  `online_search_started=false`, `manual_review_required=true`;
- tentativi pianificati:
  `storia_memoria_bo` con `nome-cognome` e
  `testo-libero-nome-completo`; `partigiani_italia` con
  `cognome-nome-contains` e `solo-cognome-contains`;
- triage feedback attuale:
  `856` azioni pending, `0` accettate, quindi questa azione non e' ancora una
  decisione storica approvata;
- nessun outcome T31 trovato nella run canonica:
  restano presenti solo `research_feedback_actions_review_table` e
  `research_feedback_actions_review_summary`;
- nessun file del data root esterno modificato e nessuna ricerca avviata.

Avanzamento T31 repository-only del 2026-07-15:

- aggiunto in `memoria-engine` il builder preview-only
  `caduti_fonti_report.document_analysis.feedback_loop_outcome`;
- il builder registra un `FeedbackLoopOutcome` auditabile a partire da
  `FeedbackSearchPlan` e summary di triage storico, con stati ammessi
  `candidate_results`, `no_results`, `needs_manual_review` e
  `blocked_or_dynamic`;
- il loop viene marcato `closed_with_auditable_outcome` solo se l'azione
  risulta approvata per la demo da una decisione di triage `BUONA` o `DUBBIA`
  e l'esito e' registrabile; senza approvazione resta
  `pending_historian_approval`;
- l'artefatto produce una `search_memory_update_preview` collegata a profilo,
  action, piano, fonte, query/esito e run, ma mantiene
  `profile_write_allowed=false`, `claim_promotion_allowed=false`,
  `creates_verified_facts=false` e `applies_profile_patch=false`;
- coperti i casi sintetici `no_results`, mancanza di approvazione storica e
  `candidate_results` senza documento candidato;
- test mirati passanti:
  `.\.venv\Scripts\python.exe -m unittest tests.test_feedback_loop_outcome tests.test_feedback_search_plan tests.test_research_feedback_triage`
  (`13 tests`, `OK`);
- nessun file del data root esterno modificato, nessuna ricerca avviata,
  nessun nuovo claim promosso e nessuna patch applicata.

Chiusura T31 operativa del 2026-07-15:

- aggiunto il tool ripetibile
  `memoria-engine/tools/register_t31_demo_feedback_loop.py`;
- eseguito il tool sul data root autorizzato
  `P:\Comune\Me.Mo.Ri.a`, limitando le scritture agli artefatti preview/audit
  della run canonica;
- creata una tabella triage T31 ridotta alla singola azione
  `research-feedback-action:7bdbb2060d955baa`, marcata `BUONA` per la demo e
  audit-only;
- creato il piano fonte-specifico T31:
  `P:\Comune\Me.Mo.Ri.a\risultati\runs\prova-preview-profili-5-reviewed-01-pipeline\document_analysis\feedback_search_plan.t31-demo.json`;
- registrato l'esito:
  `P:\Comune\Me.Mo.Ri.a\risultati\runs\prova-preview-profili-5-reviewed-01-pipeline\historian_review\feedback_loop_outcome.t31-demo.json`;
- stato esito: `closed_with_auditable_outcome`;
- outcome: `needs_manual_review`, con `execution_mode=manual_review_session`;
- query/sessione: `nome-cognome; nom="Dino"; cog="Andreoli"` e
  `testo-libero-nome-completo; s="Dino Andreoli"`;
- il descrittore attivo
  `P:\Comune\Me.Mo.Ri.a\database\memoria_mvp_demo.active.json` punta ora agli
  artefatti T31 e contiene `t31_feedback_loop`;
- backup descrittore creato:
  `P:\Comune\Me.Mo.Ri.a\database\memoria_mvp_demo.active.before-t31-feedback-loop.json`;
- verifica read-only `memoria mvp demo --data-root "P:\Comune\Me.Mo.Ri.a"`
  conferma la presenza degli artefatti T31 e le safety flag:
  `applies_profile_patch=false`, `creates_canonical_verified_facts=false`,
  `modifies_canonical_profiles=false`;
- nessun claim promosso, nessuna patch applicata, nessun profilo canonico
  modificato, nessun dato reale copiato nei repository Git.

Nota storica: dopo T31 il prossimo passo era T32. T32 e' ora chiuso; T33 e'
l'incremento corrente.

## Motivazione rispetto alla roadmap

T12 ha seguito:

- roadmap master: stabilizzare la baseline post-migrazione prima di nuovi task
  funzionali;
- roadmap MVP: preparare una demo minima tracciabile senza trasformarla in
  pipeline massiva;
- roadmap tecnica: audit dei residui persona/seed prima di qualunque migrazione
  fisica o cambio runtime.

T13 ha ridotto il rischio residuo sui default legacy verso profili e CSV reali,
ma l'esperienza utente non deve regredire verso wrapper con path espliciti. Il
recupero T13b ristabilisce l'intento della CLI `memoria`: risolvere il data root
e offrire controlli read-only semplici. T14 ha proseguito la rimozione
controllata dei residui in `memoria-engine/ricerche` classificando
`llm_prompts`. T15 sposta i contratti LLM versionabili in `memoria-rules`
mantenendo comportamento invariato e fallback legacy controllato. T16 puo'
chiudere il ciclo rimuovendo o rendendo non operativo il residuo legacy
`llm_prompts`. I test CLI hanno poi evidenziato un gap: la CLI puo' mostrare lo
stato editoriale quando presente, ma i profili canonici attuali non espongono
ancora campi di stato scheda/profilo. T17 colma questo gap di contratto prima di
qualunque modifica ai dati reali. T18 ha completato il dry-run di
inizializzazione senza scrivere nel data root. Q1 ha individuato i moduli piu'
grandi e ha raccomandato un primo Q2 circoscritto sui parser Markdown di
`mvp_review_focus_table`, completato con comportamento invariato. I Q2
successivi hanno isolato il rendering diagnostico di `mvp_pilot_summary`, i
record manifest/log di `local_processing_runner`, il rendering MVP vault di
`export_obsidian_vault` e i parser PrimeFaces/tree di
`bundesarchiv_invenio_executor`, sempre con helper interni e test mirati. T19 ha
chiuso la pianificazione cross-platform: la direzione e' `memoria` Python come
superficie canonica futura, con PowerShell mantenuto per l'MVP finanziatori e
wrapper Linux futuro come facciata sottile. In assenza di una nuova decisione
funzionale esplicita, questa sessione prosegue con la traccia Q2 gia'
autorizzata, scegliendo un micro-refactor behavior-preserving su
`candidate_claims.py`, ultimo candidato rilevante rimasto dall'audit Q1. Il
micro-refactor ha isolato la diagnostica funnel claim in un helper puro,
mantenendo invariati output e workflow. Questa sessione completa lo stesso
confine Q2 su `candidate_claims.py` isolando la costruzione degli skipped claim,
seconda responsabilita' pura indicata dall'audit Q1.
Questa sessione prosegue la traccia Q2 con un micro-refactor altrettanto
limitato su `german_docs_downloader.py`, isolando solo il rendering Markdown del
manifest, gia' coperto dai test del downloader.
Questa sessione prosegue la stessa traccia Q2 su
`mvp_consolidated_review_ledger.py`, isolando solo il rendering Markdown del
ledger in un helper dedicato e mantenendo invariati consolidamento, CLI e output
osservabile.
Questa sessione prosegue la stessa traccia Q2 su `mvp_review_dashboard.py`,
isolando solo il rendering Markdown della dashboard in un helper dedicato e
mantenendo invariati build, CLI, JSON e output Markdown osservabile.
Questa sessione prosegue la stessa traccia Q2 su
`mvp_historical_review_targets.py`, isolando solo il rendering Markdown dei
target storici revisionabili in un helper dedicato e mantenendo invariati build,
lettura evidence store, CLI, JSON e output Markdown osservabile.
Questa sessione prosegue la stessa traccia Q2 su `mvp_review_session.py`,
isolando solo il rendering Markdown della sessione review in un helper dedicato
e mantenendo invariati build, focus review, template decisioni, CLI, JSON e
output Markdown osservabile.
Questa sessione prosegue la stessa traccia Q2 su `mvp_review_decisions.py`,
isolando solo il rendering Markdown del riepilogo decisioni in un helper
dedicato e mantenendo invariati validazione, sintesi sessione storici, CLI, JSON
e output Markdown osservabile.
Questa sessione prosegue la stessa traccia Q2 su `mvp_review_queue.py`,
isolando solo il rendering Markdown della review queue in un helper dedicato e
mantenendo invariati build queue, template decisioni, CLI, JSON e output
Markdown osservabile.
Questa sessione apre e chiude T20, primo bridge operativo read-only previsto da
T19: `memoria` Python espone ora `review discover/status/work` per orientarsi
sulle run e sulla worklist MVP senza sostituire i comandi PowerShell
decisionali usati per l'MVP finanziatori.
Questa sessione apre e chiude T21, secondo bridge operativo read-only previsto
da T19: `memoria` Python espone ora `consolidate discover/status` per
orientarsi sugli artefatti consolidati preview senza rigenerare ledger, scrivere
nello store o sostituire i comandi PowerShell preview usati per l'MVP
finanziatori.
Questa sessione apre e chiude T22, terzo bridge operativo read-only previsto da
T19: `memoria` Python espone ora `sources online/offline discover/status` per
orientarsi su registry fonti, sessione sources online e intake offline senza
avviare rete, download, OCR, pipeline o scritture nel data root.
Questa sessione apre e chiude T23: il workspace operativo viene riclassificato
come risorsa logica pluggable. `P:\Comune\Me.Mo.Ri.a` resta backend locale
compatibile per MVP e workflow validati, mentre pCloud diventa il primo backend
cloud candidato, da introdurre solo con incrementi read-only/mock prima di
qualunque scrittura o migrazione reale.
Questa sessione apre e chiude T24: il motore espone ora un contratto
`WorkspaceStorage` e un driver `LocalWorkspaceStorage`; `memoria doctor` usa il
driver local per le verifiche diagnostiche mantenendo invariato il comportamento
osservabile. pCloud resta in attesa della risoluzione del problema API aperto
con il supporto.
Questa sessione apre e chiude T25: il manifest workspace diventa
provider-aware, con provider attivo `local`, descrizione pCloud senza segreti e
resolver CLI aggiornato. Il backend pCloud resta non implementato e in hold
finche' l'accesso API non viene chiarito.
Questa sessione apre e chiude un Q2 behavior-preserving su `memoria_cli.py`:
la risoluzione data-root/manifest viene spostata in `workspace_resolver.py`,
riducendo la responsabilita' della CLI senza cambiare API pubblica, output o
workflow.
Questa sessione apre e chiude un Q2 test-only su `workspace_resolver`: i test
del resolver vengono isolati dal test della CLI diagnostica, migliorando la
tracciabilita' del confine introdotto senza toccare runtime o comportamento.
Questa sessione apre e chiude un Q2 test-only su `LocalWorkspaceStorage`:
rafforza la garanzia che il driver locale resti confinato al workspace root
anche quando riceve path assoluti, senza anticipare T26 o introdurre accessi
cloud.
Questa sessione apre e chiude un Q2 test-only su
`LocalWorkspaceStorage.list_dir`: rende esplicito nei test il contratto degli
entry directory locali, utile per mantenere stabile la diagnostica del workspace
e confrontare in futuro backend alternativi senza introdurre pCloud ora.
Questa sessione apre e chiude T26a, scelto esplicitamente come avanzamento MVP
non-cloud mentre T26 resta in hold: `memoria review decisions` rende visibile
dalla CLI Python lo stato delle decisioni umane review gia' registrate negli
artefatti preview, senza applicare nuove decisioni e senza spostare il workflow
decisionale PowerShell usato per la demo finanziatori.
Questa sessione apre e chiude T26b, secondo avanzamento MVP non-cloud:
`memoria mvp status` compone una vista unica e read-only del walkthrough demo
locale, rendendo provabile il percorso profili -> review -> decisioni ->
consolidamento -> fonti senza generare nuovi artefatti e senza attendere T26
pCloud.

## Vincoli

- Per workflow operativi sui dati reali, il perimetro massimo autorizzato e'
  `P:\Comune\Me.Mo.Ri.a` con le sue sotto-cartelle.
- Scrivere nel data root esterno solo quando serve all'incremento corrente
  documentato, riportando file toccati, validazioni e impatto.
- Non scrivere dati reali fuori da `P:\Comune\Me.Mo.Ri.a`.
- Non cancellare o sovrascrivere massivamente, modificare profili canonici,
  applicare patch o promuovere fatti canonici senza incremento dedicato,
  backup e audit trail.
- Non copiare dati reali nei repository Git.
- Non lanciare OCR.
- Non elaborare JSON-LD.
- Non generare schede.
- Non fare pipeline end-to-end.
- Non fare refactor ampio senza decisione nel decision log.
- Per refactor continuo usare `playbooks/09-continuous-refactor.md` e la traccia
  Q della roadmap tecnica.
- Eseguire un solo incremento piccolo e verificabile per sessione.

## Comandi di validazione

Per incrementi solo documentali:

```powershell
Get-Content memoria-bootstrap\docs\current-next-increment.md
Get-Content memoria-bootstrap\docs\roadmap\02-technical-roadmap.md
Get-Content memoria-bootstrap\docs\funding-demo-golden-path.md
Get-Content memoria-bootstrap\docs\funding-demo-t29-contract.md
Get-Content memoria-bootstrap\docs\decision-log.md
```

Per incrementi che modificano `memoria-engine`:

```powershell
cd memoria-engine
.\.venv\Scripts\python.exe -m pytest
```

Per incrementi mirati sui profili persona:

```powershell
cd memoria-engine
.\.venv\Scripts\python.exe -m unittest tests.test_packaging tests.test_person_profiles tests.test_profiles_runner tests.test_feedback_search_plan tests.test_mvp_document_intake_preflight
```

Per verifiche read-only della CLI:

```powershell
cd memoria-engine
$env:MEMORIA_DATA_ROOT = "P:\Comune\Me.Mo.Ri.a"
.\.venv\Scripts\memoria.exe data-root
.\.venv\Scripts\memoria.exe inventory
.\.venv\Scripts\memoria.exe doctor
.\.venv\Scripts\memoria.exe profiles status
.\.venv\Scripts\memoria.exe mvp demo
```

Per verifiche T31/T32 mirate:

```powershell
cd memoria-engine
.\.venv\Scripts\python.exe -m py_compile tools\register_t31_demo_feedback_loop.py
.\.venv\Scripts\python.exe -m unittest tests.test_feedback_loop_outcome tests.test_feedback_search_plan tests.test_research_feedback_triage tests.test_packaging
.\.venv\Scripts\memoria.exe mvp demo --data-root "P:\Comune\Me.Mo.Ri.a"
```

## Criteri di accettazione del prossimo incremento

- `memoria mvp demo` mostra la run canonica e tutti gli artefatti T30/T31
  presenti;
- i safety flag restano preview-only e non pubblicabili;
- CLI Python, wrapper PowerShell e guide non puntano a run diverse;
- i riferimenti operativi obsoleti, inclusi vecchi vincoli di autorizzazione
  non piu' coerenti con il decision log, sono allineati;
- il walkthrough 7-10 minuti e' verificato almeno in asciutto;
- il pacchetto repository distribuibile non contiene dati reali;
- il sidecar T30 resta dichiarato come ponte temporaneo preview-only da
  sostituire con il flusso standard, senza bloccare la prova interna.

## Aggiornamenti da fare a fine incremento

- Aggiornare questa sezione `Stato` quando l'incremento cambia o viene chiuso.
- Spostare il prossimo candidato nella sezione `Incremento corrente`.
- Registrare in `decision-log.md` solo le decisioni architetturali o
  metodologiche nuove.
- Aggiornare roadmap o playbook solo se cambia il processo operativo.
- Riportare nel riepilogo finale i file modificati e le validazioni eseguite.

Template verbale revisione umana T33 del 2026-08-26: creato memoria-bootstrap/docs/funding-demo-t33-human-review-response-template.md e collegato all'handoff. Il template raccoglie esito, blocchi narrativi, correzioni richieste e conferme di guardrail, ma non registra alcuna decisione reale, non approva la presentazione, non introduce bando/importo/finanziatore e non modifica artefatti canonici.

Preflight revisione umana T33 del 2026-08-28: creato memoria-bootstrap/docs/funding-demo-t33-human-review-preflight.md e collegato a handoff e template. Il preflight verifica materiali, sei blocchi narrativi, esiti ammessi e guardrail prima della revisione umana effettiva; non registra verdetti reali, non approva layout o pubblicazione, non introduce bando/importo/finanziatore e non modifica artefatti canonici.

Revisione umana effettiva T33 del 2026-08-28: Marco Fabbri (Author) ha approvato i sei blocchi narrativi e confermato i guardrail, con verdetto approved_for_layout. I blocchi Cinque storie e Limiti hanno ricevuto formulazioni aggiornate registrate nel verbale datato; il prossimo candidato e' allineare meccanicamente l'entrypoint ai due testi approvati, ripetere una breve prova asciutta e poi preparare il layout interno non pubblicabile. Il verdetto non autorizza pubblicazione, bando, importo, finanziatore o modifiche canoniche.
Allineamento entrypoint T33 del 2026-08-29: recepiti meccanicamente in `funding-demo-t33-presentation-entrypoint.md` i testi approvati dal verbale umano per i blocchi 3, Cinque storie, e 5, Limiti e non pubblicabilita'. La prova asciutta breve `funding-demo-t33-presentation-alignment-dry-run-2026-08-29.md` conferma coerenza narrativa e guardrail: presentazione non pubblicabile, nessun bando/importo/finanziatore, nessuna nuova fonte, nessuna scrittura nel data root esterno e nessuna modifica canonica. Il prossimo candidato e' preparare il layout interno non pubblicabile.

Semplificazione procedura agent Windows del 2026-08-29: rimossa la guida
dedicata e concentrate in `AGENTS.md` cinque regole essenziali su patch, retry,
escalation e JSON. La priorita' T33 e il prossimo candidato restano invariati.

Brief layout interno T33 del 2026-08-29: creato funding-demo-t33-internal-layout-brief.md con ordine delle sei schermate, composizione Andreoli e preflight. Il brief resta interno, revisionabile e non pubblicabile; non introduce dati reali, bando, importo, finanziatore o modifiche canoniche.

Verifica brief layout interno T33 del 2026-08-29: confermati collegamento dall'entrypoint, coerenza con la scaletta Andreoli e il verbale `approved_for_layout`, presenza dei testi approvati dei blocchi 3 e 5 e guardrail di non pubblicabilita'. Incremento chiuso senza dati reali, scritture nel data root esterno, approvazione di claim o modifiche canoniche.

Wireframe layout interno T33 del 2026-08-29: prodotto `funding-demo-t33-internal-layout-wireframe.md` con sei schermate, gerarchia testuale, composizione Andreoli a tre tracce, domanda aperta e checklist. L'artefatto e' una base interna di impaginazione, non una slide finale e non pubblicabile; verifiche JSON, riferimenti/guardrail e diff passate.

Q2 memoria-engine del 2026-08-29: isolata in `mvp_pilot_summary.py` la costruzione delle piste documentali revisionabili per profilo in un helper puro. Ordine, deduplicazione, filtri e output restano invariati; 16 test mirati e 3 test downstream della review queue passano. Nessun dato reale o data root esterno modificato.

Q2 memoria-engine del 2026-08-29: isolata in `mvp_pilot_summary.py` la diagnostica pura dei duplicati documentali, inclusa la priorita' della chiave di identita', il raggruppamento e i conteggi derivati. Payload, blocker, Markdown, CLI, schema e workflow restano invariati; nessun dato reale o data root esterno modificato.

T26 pCloud del 2026-08-29: verifica live read-only riuscita con provider `pcloud`, host `api.pcloud.com`, token configurato e modalita' `read_only`. La root `/` restituisce nessun contenuto e non ha `folderid` esplicito; nessuna scrittura cloud e' stata eseguita. Per completare T26 serve un path o `folderid` di una cartella remota esistente.
T26 pCloud HOLD del 2026-08-29: l'app `MemoriaStorage` risulta vincolata a `Specific app folder`; il campo `Folder access` e' disabilitato. Il supporto pCloud deve convertire l'app a `All folders` o fornire una nuova app equivalente. In attesa della risposta non si eseguono altre operazioni cloud.

Chiusura complessiva T33 del 2026-08-29: completati golden run, dossier, walkthrough,
diagramma evidenziale, scheda caso, roadmap uso fondi, checklist readiness,
revisione umana, allineamento narrativo, brief e wireframe del layout interno.
Il materiale resta revisionabile e non pubblicabile. Il prossimo incremento va
ricalcolato dalla roadmap; T26/pCloud resta separato e in HOLD.

Q2 memoria-engine del 2026-08-29: estratta la decisione pura di stato e prossima
azione del pacchetto pilota in `mvp_pilot_package_status.py`, mantenendo alias,
output, scorecard, payload, Markdown, CLI, schema e workflow invariati. Aggiunti
test mirati per documenti assenti, segnali da revisionare e stato pronto; 5 test
passano. Nessun dato reale o data root esterno modificato.

Q2 memoria-engine del 2026-08-29: estratta la decisione pura di readiness e
prossima azione del profilo pilota in `mvp_pilot_readiness.py`, mantenendo
status, payload, Markdown, CLI, schema e workflow invariati. Aggiunti test
mirati per documenti assenti, link mancanti, segnali da revisionare, claim
assenti e stato pronto; 17 test mirati e downstream passano. Nessun dato reale
o data root esterno modificato.

Selezione Q2 del 2026-08-29: il prossimo micro-incremento e' isolare la
costruzione della readiness per profilo in `mvp_pilot_profile_readiness.py`.
Il perimetro resta behavior-preserving, preview-only e limitato a codice,
test, planner e questa nota; nessun dato reale o data root esterno sara'
modificato.

Discovery fonti online del 2026-08-29: la cartella esterna autorizzata
`P:\Comune\Me.Mo.Ri.a\documenti_da_processare\fonti_online` contiene 30 file
(12 TXT, 3 JPG, 15 sidecar YAML), per circa 364 KB. I file effettivi sono nei
gruppi `storia_memoria_bo_excel`, `partigiani_italia` e `storia_memoria_bo`;
`atlante_stragi` e `fondazione_fossoli` risultano vuoti. I sidecar espongono
identificativi, titoli e URL; nessun OCR, download, import o modifica canonica
e' stato eseguito. Il primo lotto di intake resta da scegliere insieme.

Chiusura Q2 del 2026-08-29: `q2-pilot-profile-readiness-builder` ha estratto
la costruzione della readiness per profilo in un helper puro. I 7 test mirati,
la validazione JSON e il diff check sono passati; output, CLI, schema,
workflow e dati esterni sono rimasti invariati.

Intake operativo `intake-balboni-online-v1` del 2026-08-29: run locale e run
documentale completate nel data root esterno con 13 documenti, OCR/rete/import
store disabilitati. Prodotti 3 link candidati, 2 claim grezzi e 61 entita'; il
profilo canonico Balboni e' stato escluso per seed legacy. Nessuna modifica
canonica eseguita; la run resta da revisionare.

Priorità roadmap del 2026-08-29: su richiesta dell'utente, T34 diventa il
prossimo percorso operativo per ricostruire e migrare in modo controllato tutti
i 57 profili legacy. La priorità non autorizza ancora modifiche canoniche:
prima servono audit di copertura, candidati preview, revisione umana, mappa
vecchio→nuovo, dry-run, backup e audit di applicazione.

T34 fase 1 del 2026-08-29: audit read-only dell'indice profili e della cartella
`fonti_online` completato. Tutti i 57 profili risultano legacy; 5 hanno una
directory soggetto con documenti disponibili (Andreoli, Balboni, Bendini,
Guazzaloca e Pasciuti), mentre 52 non hanno copertura nella cartella esaminata.
Nessun candidato, profilo canonico o dato operativo è stato modificato.

T34 lotto 1 del 2026-08-29: per Balboni sono stati generati 2
`CandidateProfileUpdate` preview-only e `pending`, collegati a claim
documentali e al documento di Partigiani d'Italia. Entrambe le proposte sono
Revisione T34 lotto 1: l'utente conferma 36a Brigata Bianconcini Garibaldi;
si genera solo ProfilePatch preview con provenance, senza modifica canonica.
Applicazione Balboni completata dopo dry-run: una formazione aggiunta al profilo
canonico, backup e audit presenti nella run; nessun conflitto o salto.
T34 Andreoli: con il matching dei profili legacy e dei nomi invertiti, l'intake
circoscritto ha prodotto 1 link documento-persona e 18 `CandidateProfileUpdate`
pending, tutti collegati al documento `storia_memoria_bo:e12f29badf406b9d`.
Nessuna ProfilePatch o modifica canonica è stata eseguita.
Revisione Andreoli completata: l'utente ha confermato nascita, morte e
formazione. Il dry-run ha dato 3 operazioni applicabili; la patch è stata
applicata con backup e audit, senza conflitti né salti.
Bendini: intake circoscritto e linker legacy completati; generate 14
`CandidateProfileUpdate` pending con provenance. Le tre varianti della formazione
e i valori compositi legacy di nascita/morte richiedono revisione umana prima
di generare una ProfilePatch.
Bendini: registrate le tre conferme utente su nascita, morte e formazione;
generata la ProfilePatch preview e completato il dry-run con 3 operazioni
applicabili, 0 conflitti e 0 salti. L'applicazione canonica resta separata.
Bendini applicato: le tre decisioni confermate sono state scritte nel profilo
canonico con backup e audit; nessun conflitto o salto.
Guazzaloca: intake circoscritto e linker disambiguato completati; generate 11
proposte pending. Le proposte principali riguardano nascita, morte e formazione;
tre estrazioni spurie sulla formazione sono da escludere in revisione.
Guazzaloca: confermati dall'utente nascita, morte e formazione; generate le
decisioni e la ProfilePatch preview. Dry-run passato con 3 operazioni applicabili,
0 conflitti e 0 salti; applicazione canonica ancora separata.
Guazzaloca applicata: le tre decisioni confermate sono state scritte nel profilo
canonico con backup e audit; nessun conflitto o salto.
Decisione operativa T34: i prossimi profili saranno lavorati in lotti massimi di
20; intake e candidati saranno batch, mentre revisione, backup, audit e patch
resteranno separati e revisionabili per profilo.

Chiusura sessione 2026-08-30 - T34 lotto 2: la CLI `run_profiles_meta_search.ps1`
ha interrogato tutti i 20 profili legacy selezionati sulla fonte `Storia e
Memoria di Bologna`, con un run separato per profilo e acquisizione esplicita
abilitata. Esito: 16 risultati `ok`, 4 `no_results` (Panov Sergio, Sadavich
Carlo, Il Toscano, Bonfanti Adolfo), 0 documenti dettagliati acquisiti. I
risultati `ok` sono ricerche preliminari: diversi nomi legacy sono generici e
le pagine restituite non sono ancora associate con certezza alla persona. Per
questo non sono stati generati aggiornamenti candidati ne' applicate modifiche
canoniche. Il lotto resta aperto al gate di disambiguazione e revisione umana;
il seed legacy non viene cancellato o riscritto.

Lezioni operative T34 da riusare nei prossimi lotti:

- la CLI richiede l'ID completo del profilo, ad esempio
  `person:purocielo:panov-sergio`, non il solo slug;
- la ricerca live esplicita richiede `-ExecuteFirstPlannedAttempt`;
- `run_mvp_workspace_pipeline.ps1` non accetta `ResultsDir` e determina in
  autonomia la cartella `risultati`;
- i job PowerShell isolati non ereditano la directory corrente: usare percorsi
  assoluti per gli script;
- una ricerca `ok` non equivale a un documento acquisito: con nomi generici
  possono restare risultati ambigui e `SourceDocument=0`;
- le cartelle profilo devono esistere prima dell'acquisizione;
- l'esecuzione parallela va mantenuta separata per profilo, per preservare
  provenance, revisione e audit distinti.
T34 Andreoli: intake circoscritto completato, ma il documento risulta
`claim_allowed=false` e il link al profilo non è stato risolto; nessuna proposta
o modifica canonica viene generata prima della revisione manuale.
`formation.name` con azione `conflict_or_revision`; il profilo canonico resta
invariato e il lotto è fermo al gate di revisione umana.

Chiusura micro-incremento 2026-08-30 - T34 fix runner: il runner calcolava
`registry` come repository root quando riceveva
`memoria-sources/registry/camalanca_fonti.yaml`; questo attivava il fallback
legacy e lasciava i report con `SourceDocument=0`. Il calcolo ora riconosce il
registry condiviso e risolve `memoria-engine`, mantenendo attivi detail logic e
claim candidati. Verifica live su Bassi Giancarlo: 1 risultato, 1
`SourceDocument`, 11 claim candidati, 1 documento acquisito; tutto resta
`unreviewed` e non sono state applicate modifiche canoniche.

Prossimo passo candidato T34: rilanciare il lotto già definito di 20 profili
con il root corretto, conservando output e provenance separati per profilo; poi
triage umano dei candidati, senza `ProfilePatch` automatico.

Chiusura lotto T34-2 2026-08-30: rilancio completato in 20 run isolate con il
root corretto. Esito: 11 profili con `candidate_results`, 9 `no_results`, 20
SourceDocument di report (11 dettagli con claim e 9 riferimenti senza claim),
119 claim candidati totali e 20 artefatti acquisiti. Tutti i claim restano
`unreviewed`; nessuna ProfilePatch, fusione o modifica canonica è stata
eseguita.

Chiusura candidate preview T34-2 2026-08-30: generati 20 file separati
`CandidateProfileUpdate` dai report del lotto, con 119 proposte complessive e
6 anteprime `CandidateNewProfile`. Le proposte restano pending/unreviewed;
non è stato generato né applicato alcun `ProfilePatch`.

Inventario review T34-2: 91 proposte nel bucket `da_accettare_facilmente`, 16
`da_confrontare` e 12 `da_discutere`; tutte dispongono di document ID e URL.
I 12 conflitti includono date di nascita/morte discordanti, ordine o alias del
nome e appartenenze a brigate non equivalenti. Le 6 `CandidateNewProfile`
(persone menzionate nei documenti) restano soltanto suggerimenti da verificare.
Nessuna decisione `accepted` o `rejected` è stata registrata.

Revisione esplicita T34-2: su autorizzazione dell'utente sono state registrate
91 decisioni `accepted` per il solo bucket `da_accettare_facilmente`. Sono state
generate 20 `ProfilePatch` preview separate, con 36 operazioni complessive,
ma nessuna patch è stata applicata ai profili canonici. Restano da esaminare
16 proposte `da_confrontare`, 12 `da_discutere` e 6 `CandidateNewProfile`.

Primo caso non facile - Bonfanti Adolfo: il documento dettagliato conferma la
nascita del 17 settembre 1907, già presente nel profilo ma con una nota di
incertezza; la morte è invece 14 ottobre 1944 nella fonte contro 12 ottobre
1944 nel profilo legacy. Proposta: accettare soltanto la normalizzazione della
data di nascita e mantenere la data di morte come conflitto da confrontare,
senza applicare patch.

Decisioni review T34-3: accettate esplicitamente le precisazioni della morte
per Mazzanti Ivo (`11 ottobre 1944`, mantenendo il luogo legacy) e Minozzi
Sergio (`20 ottobre 1944, Bologna`). Le rispettive ProfilePatch restano
preview-only. Mereu Antonio e Poletti Livio restano pending per conflitto di
data.

Revisione facile T34-3: accettate 109 proposte `da_accettare_facilmente` con
decisioni `user-explicit`. Generate 20 `ProfilePatch` preview separate con 45
operazioni complessive; nessuna patch è stata applicata. Restano 17 proposte
`da_confrontare`, 18 `da_discutere` e 17 `CandidateNewProfile`.

Chiusura lotto T34-3 2026-08-30: processati 20 profili in run isolate sulla
fonte `storia_memoria_bo`. Esito: 14 `candidate_results`, 6 `no_results`, 20
documenti acquisiti, 144 `CandidateProfileUpdate` e 17 `CandidateNewProfile`
preview. Tutti i candidati restano `pending/unreviewed`; nessuna ProfilePatch o
modifica canonica è stata applicata.
Chiusura lotto finale T34-4: processati i 13 profili residui in run isolate.
Generate 108 CandidateProfileUpdate e 15 CandidateNewProfile preview, distribuiti in 78 proposte facili, 11 da confrontare e 19 da discutere. Le decisioni facili sono state registrate con revisore user-explicit e hanno prodotto 30 operazioni di ProfilePatch preview; tutto resta pending/unreviewed e nessuna patch o modifica canonica e stata applicata.

Coda decisionale T34-4: i 11 casi `da_confrontare` sono compatibilita' di data
con luogo o contesto gia' presente nel legacy; la regola operativa proposta e'
preservare il valore completo, senza sostituirlo con la sola data. I 19 casi
`da_discutere` includono date discordanti, alias e appartenenze; nessuna decisione
e' stata registrata per questi casi e i 15 CandidateNewProfile restano sospesi.

Decisione T34-4 sui confronti: confermata dall'utente la preservazione del valore
legacy completo per tutti gli 11 casi compatibili. Registrate 11 decisioni
`accepted` con `target_value` uguale al valore corrente e generate le rispettive
ProfilePatch preview; nessuna modifica canonica applicata.

Coda T34-4 dei casi da discutere: 6 alias/nominativi aggiuntivi, 6 appartenenze
o funzioni di brigata e 7 date non conciliabili o insufficientemente dettagliate.
Gli alias possono essere valutati come aggiunta mantenendo il nome canonico; le
appartenenze richiedono scelta tra integrazione e mantenimento; le date richiedono
conferma puntuale. Nessuna decisione e' stata registrata in questa fase.

Confronto T34-4: i 6 alias hanno confidenza 0.95 e citazione diretta; le 6
appartenenze hanno confidenza 0.8 ma in alcuni casi competono con ruolo o brigata
gia' presenti; le 7 date hanno confidenza 0.9, con 4 valori legacy assenti o
incompleti e 3 conflitti espliciti (Ungania nascita, Ungania morte, Vignuzzi morte).
Il confronto non ha promosso alcun candidato a fatto canonico.

Decisione alias T34-4: accettati i 6 nominativi aggiuntivi come alias con
operazione `add` su `/identity/aliases/-`; il nome canonico legacy resta invariato.
Generate sei ProfilePatch preview separate, senza applicazione canonica.

Confronto appartenenze T34-4: Serotti, Toni e Villa ripetono la 36a Brigata gia'
presente nel legacy e non giustificano una sostituzione. Proni aggiunge una
funzione diversa (vice comandante rispetto a motorista); Vignuzzi aggiunge la
funzione di ispettore di battaglione; Terzi presenta il conflitto 66a Jacchia
contro 36a Brigata. Nessuna decisione e' stata registrata per questi sei casi.

Decisione ruoli T34-4: accettate le aggiunte per Proni (vice comandante di
compagnia) e Vignuzzi (ispettore di battaglione), con operazioni additive su
`/formations/-`. I valori legacy restano invariati; Serotti, Toni, Villa e Terzi
restano senza decisione.

Decisione duplicati T34-4: per Serotti, Toni e Villa registrata la scelta
`rejected`/nessuna modifica, poiche' la 36a Brigata e' gia' presente nei valori
legacy. Le preview risultano prive di operazioni; Terzi resta pending per il
conflitto tra 66a Jacchia e 36a Brigata.

Riapertura date T34-4: cinque casi sono candidati a integrazione preservando il
contesto legacy: Serotti nascita (valore legacy illeggibile), Saba morte (giorno
non reperito), Soldati morte (data da aggiungere mantenendo il luogo), Ungania
morte (data non reperita) e Villa morte (dettaglio cronologico non reperito).
Restano due conflitti da non risolvere automaticamente: Ungania nascita
(`21 giugno 1920` contro `1 marzo 1925`) e Vignuzzi morte (`12 dicembre 1944`
contro `ottobre 1944, Brisighella`).

Decisione date T34-4: confermati i cinque casi integrativi. Generate cinque
ProfilePatch preview con date accettate; per Soldati il target conserva anche
`Fornazzano/Casola Valsenio`. Ungania nascita e Vignuzzi morte restano pending.

Confronto conflitti duri T34-4: Ungania nascita propone `21 giugno 1920` con
confidenza 0.9 contro `1 marzo 1925, Palazzuolo sul Senio` proveniente da fonte
biografica derivata. Vignuzzi morte propone `12 dicembre 1944` con confidenza
0.9 contro `ottobre 1944, Brisighella` nel legacy. In entrambi i casi la scelta
richiede esplicita sostituzione, mantenimento oppure registrazione del conflitto;
nessuna patch e' stata generata.

Decisione conflitti duri T34-4: l'utente ha scelto la fonte per entrambi i casi.
Generate due ProfilePatch preview con sostituzione delle date legacy; le fonti,
i claim e le decisioni restano tracciati e nessuna modifica canonica e' stata
applicata.

Inventario residui T34: restano 27 CandidateProfileUpdate pending nel lotto 2,
33 nel lotto 3 e 1 nel lotto 4 (Terzi, appartenenza 66a/36a). Nel lotto 2 la
coda comprende 15 confronti di date e 12 casi da discutere; nel lotto 3 15
confronti di date e 18 casi da discutere. Restano inoltre 38 CandidateNewProfile
senza decisione. Il prossimo lavoro deve procedere per coda di revisione, senza
applicare patch canoniche.

Stato migrazione T34 salvato a fine sessione 2026-08-30: i 57 profili legacy
sono stati sottoposti a intake/ricerca in lotti da massimo 20. Sono stati
prodotti 371 `CandidateProfileUpdate` e 38 `CandidateNewProfile`. Le decisioni
registrate sono 307 `accepted` e 3 `rejected` senza modifica; restano 61 update
pending e 38 nuovi profili da valutare. Le patch preview generate sono auditabili
per run e profilo, ma nessuna modifica canonica e' stata applicata.

Decisioni di questa sessione: alias aggiunti in modo non sostitutivo; ruoli
aggiuntivi separati dai valori legacy; duplicati chiusi senza operazioni; cinque
date integrate preservando il contesto; due conflitti di data risolti a favore
della fonte esplicita. Resta pending il conflitto di Terzi tra 66a Jacchia e
36a Brigata. Prima della pubblicazione restano revisione dei residui, decisione
sui nuovi profili, backup, dry-run, audit e applicazione esplicita delle patch.
migrazione T34 chiusa in preview-only 2026-08-31: tutte le decisioni della
worklist sono state classificate. Generati i registri finali e una raccolta di
10 operazioni `ProfilePatch` preview; restano 2 conflitti `needs_review`
(Brini Adelmo e Bagni Alfonso). Nessuna modifica canonica o pubblicazione e'
stata eseguita.
## Nota roadmap 2026-09-17 - intake immagini e OCR strutturato

Sono stati consolidati nella roadmap tecnica i requisiti post-MVP per un
workflow CLI Python end-to-end: discovery/intake idempotente, OCR per lotto,
trascrizione Markdown strutturata con provenance di pagina/regione, trattamento
distinto di tabelle, diagrammi e cartine, quindi candidati per review e possibile
arricchimento dei profili. L'OCR e i report Markdown attuali non ricostruiscono
ancora semanticamente tabelle o mappe. Restano obbligatori incertezza esplicita,
revisione umana e preview-only: nessuna promozione automatica o modifica canonica.

Riferimento: `memoria-bootstrap/docs/roadmap/02-technical-roadmap.md`, sezione
"Post-MVP - Intake immagini, OCR strutturato e collegamento ai profili".
L'implementazione va selezionata come un singolo micro-incremento successivo;
questo aggiornamento registra requisiti, non introduce capacità runtime.

## Nota di sessione 2026-09-17 - intake immagini CLI preview-first

Implementato `memoria documents register --root ... --source-id ...
--archival-reference ...`: la modalità predefinita scansiona ricorsivamente le
immagini supportate e mostra cosa registrerebbe senza scrivere file. Solo
`--apply` crea i sidecar mancanti; quelli già presenti sono saltati e gli
originali restano invariati. I test coprono preview read-only, applicazione,
input vuoto/inesistente e rerun idempotente (28 test mirati passati). Questo
passo non esegue OCR: il prossimo incremento dovrà collegare il processamento
OCR alla CLI, mantenendo output e limiti dichiarati nella roadmap.

## Nota di sessione 2026-09-17 - OCR batch dalla CLI

Implementato `memoria documents process --root ... --output-dir ...`: senza
`--apply` il comando mostra in sola lettura immagini registrate, output OCR
attesi e motivi di salto, senza avviare Tesseract o scrivere file. Con `--apply`
delega al runner OCR batch locale esistente e riporta risultati o errori per
documento. I test offline coprono preview, delega esplicita e root inesistente;
non sono stati modificati runner, dipendenze, profili, claim o dati esterni.

## Integrazione requisiti roadmap 2026-09-17 - Markdown con layout di pagina

Il deliverable futuro non è limitato a OCR o testo estratto: per ogni immagine
o pagina dovrà essere prodotto un Markdown che ricostruisce in modo
semplificato pagine, blocchi, titoli, paragrafi, colonne/ordine di lettura,
liste, didascalie e tabelle quando rilevabili, con riferimenti alle regioni
originali. Strutture inferite e incertezze vanno marcate; il testo illeggibile
non va inventato. La ricostruzione della pagina non interpreta mappe né la
semantica dei simboli.

La roadmap richiede inoltre una valutazione comparativa di pipeline OCR/layout
e LLM locali, anche multimodali, come opzioni senza selezionare ora modello o
stack. Le opzioni locali dovranno poter operare offline, tutelare la privacy e
registrare modello/versione/configurazione, provenance e dati per la
riproducibilità. Il confronto considera fedeltà del layout, copertura delle
regioni, tabelle, qualità, costo/risorse e revisione umana; i criteri offline
includono fixture con scansioni multi-colonna, header/footer, tabelle, layout
misto e testo degradato, con Markdown atteso. È un aggiornamento di requisiti:
nessun benchmark o cambiamento runtime è stato eseguito.

## Nota di sessione 2026-09-17 - evidenze layout line-level OCR

Completato `ocr-line-layout-evidence-v1`: `ProcessedDocumentText` conserva in
`ocr_layout_lines` le righe estratte dal TSV Tesseract, con ID stabili di riga,
pagina e regione, testo, coordinate, confidence media e `review_status:
unreviewed`. I candidati di nota e riferimento restano output separati e
collegano la riga/regione che li ha originati. TSV assente o fallito produce una
lista vuota e mantiene i metadati OCR compatibili.

Correzione quality gate in corso: le righe e i candidati riportano anche
`source_document_id`; `read_order` è marcato `inferred` con base
`page_top_then_left_then_tsv_hierarchy`, quindi non dichiara un ordine di lettura
verificato né una struttura semantica. La suite OCR e la compilazione passano;
il planner resta `in_progress` fino al secondo gate indipendente.

## Nota di sessione 2026-09-17 - export Markdown OCR per pagina

Completato `ocr-page-markdown-export-v1`: `memoria documents markdown --root
... --output-dir ...` mostra i file candidati in preview read-only e scrive
solo con `--apply`. L'export crea un file per pagina nel percorso sanificato
`source_document_id/page_id.md`, conserva documento e file sorgente, motore,
lingua, regione, bounding box, confidence, revisione e ordine inferito con la
sua base. Il testo OCR resta letterale in fence sicure e non viene interpretato
come Markdown, titolo, tabella o claim. JSON non validi, layout vuoti,
collisioni e output esistenti sono riportati per documento senza sovrascrittura.

Correzione quality gate: la scrittura in apply usa creazione esclusiva. Se un
file compare tra il preflight e l'apertura, l'export lo segnala come esistente e
ne conserva il contenuto; il planner resta in attesa del secondo gate.

## Nota di sessione 2026-09-17 - quality gate OCR e retry limitati

Completato `ocr-quality-gated-retry-v1`: il runner controlla testo e TSV prima
di registrare `ProcessedDocumentText`. Un candidato degradato puo' attivare al
massimo un PSM alternativo e una derivata temporanea preprocessata con il PSM
piu' promettente. Se nessun candidato passa, restituisce un errore prima della
scrittura e conserva gli output esistenti. Il payload scelto registra una sintesi
di `ocr_fallback_attempts`; il Markdown salta documenti gia' rifiutati e righe
senza testo alfanumerico. Nel pilot le soglie sono: almeno 2 token alfanumerici,
una riga TSV alfanumerica, confidence media >= 35 e quota low-confidence <= 75%.
Sono euristiche tecniche, non giudizi archivistici: vanno calibrate con fixture
di scansioni rappresentative prima di fissarle.
Il gate decide soltanto la registrazione del JSON OCR `ProcessedDocumentText`;
un `*.metadata.json` separato conserva metadati indipendenti e non costituisce
un output OCR vuoto.

## Nota di sessione 2026-09-17 - valutazione Qwen locale per OCR

Inserita in roadmap una valutazione dedicata di Qwen3-VL 8B locale e delle
varianti `instruct`/`thinking`, senza selezione preventiva dello stack. Il pilot
con `qwen3-vl:8b` ha saturato il context 4096 sull'immagine intera ad alta
risoluzione; con crop ridotto e context piu' ampio il budget e' stato comunque
consumato dai token di thinking e la risposta finale e' rimasta vuota o
incompleta. Prossimo lavoro candidato: benchmark offline contro Tesseract su
fixture con riferimento, testo degradato e tabella/layout misto; valutare
prompt letterali nella lingua sorgente, budget e modalita' thinking,
dimensionamento/crop/tiling, accuratezza, copertura, completezza,
non-invenzione, struttura e risorse/latency CPU-GPU. Registrare tag/digest,
versione/configurazione Ollama, hash del prompt e trasformazioni per rendere i
risultati riproducibili.

## Debito tecnico CLI - dispatcher PowerShell duplicato

La roadmap tecnica registra come debito la coesistenza della CLI Python
installabile `memoria` e dell'implementazione autonoma `scripts/memoria.ps1`,
che non inoltra tutti i comandi. La CLI Python deve diventare l'unica autorita'
dei comandi. Dopo aver inventariato e migrato i comportamenti PowerShell mancanti
e verificato la parita' con test, l'implementazione autonoma PowerShell va
rimossa immediatamente; l'eventuale `.ps1` residuo e' soltanto un launcher
sottile che inoltra ogni argomento alla CLI Python. Nessun periodo di doppia
implementazione e' ammesso.

## Nota di sessione 2026-09-19 - preflight campione OCR bloccato

Preflight eseguito solo sui nomi nella cartella
`P:\Comune\Me.Mo.Ri.a\documenti_da_processare\foto\T314 R1275\test`:
risultano due TIFF e due sidecar `.document.yaml`. Nessuna scansione e' stata
aperta o elaborata e nessun contenuto dei sidecar e' stato inferito. Non e'
stata individuata una trascrizione umana verificata; prima di proseguire e'
stato chiesto all'utente di indicare il file o percorso del riferimento umano.

## Nota di sessione 2026-09-19 - run Tesseract su due immagini

Su chiarimento dell'utente, la trascrizione umana non e' un prerequisito per la
revisione qualitativa degli output. Run batch completato con Tesseract 5.5.3,
lingua `ita`: 2 immagini processate, 0 errori. Report `ocr_batch_report.json`,
`ocr_batch_report.md` e log `ocr_batch.log` sono esclusivamente in
`C:\Users\info\AppData\Local\Temp\memoria-ocr-review-20260919`.

Entrambi gli output hanno `ocr_quality_status=low_confidence`. `00028`: 425
caratteri, 65 parole, confidence 62.80 e 22 parole low-confidence; propone
etichette tedesche ma contiene caratteri corrotti. `00026`: 3.111 caratteri,
1.002 parole, confidence 36.99 e 691 parole low-confidence; il testo e' quasi
tutto rumore. Per `00026` i retry default e PSM12 sono stati rifiutati;
`temporary_preprocessed` PSM12 e' stato selezionato ma resta `low_confidence`.
Il gate `accepted` nel report non indica qualita' attendibile. Tesseract ha
solo `eng`, `ita`, `ita_old` e `osd`, non `deu`. Originali e sidecar sono
rimasti intatti; nessun output e' stato scritto su `P:`. Non sono stati usati
LLM o claim, non sono state calcolate metriche di accuratezza e non sono stati
eseguiti test. Prossimo passo: review condivisa degli output; valutare in
seguito OCR con modello multilingue senza pre-caricare un'implementazione.

## Nota di sessione 2026-09-19 - confronto Tesseract deu e PP-OCRv5

Tesseract 5.5.3 e' stato eseguito con `deu`, OEM1, PSM6 e `tessdata-dir` sotto
Temp. Il runner quality-gated ha riportato 0 processati e 2 errori dopo 3
retry, per `no_alphanumeric_tsv_lines`, bassa confidence e low-confidence
diffusa. I raw text sono comunque disponibili in
`%TEMP%\memoria-ocr-review-20260919-tesseract-deu\raw\T314-1275-00026.txt`
e `...00028.txt`: `00028` ha righe tedesche leggibili, `00026` e' rumoroso.

PP-OCRv5 e' stato eseguito su CPU con MKLDNN=false, detector mobile,
recognition Latin e auto-resize del lato massimo da 6192 a 4000. `00026`:
49 righe, 2289 caratteri, score medio 0.723182, 48.646 s. `00028`: 59 righe,
531 caratteri, score medio 0.843398, 29.299 s. Il report
`%TEMP%\memoria-ocr-review-20260919-ppocrv5\ppocrv5_report.json` conserva testi,
score per riga, hash delle immagini e hash del manifest dei pesi.

Il setup dell'adapter ha richiesto di correggere il nome interno del modello:
`inference.yml` non corrispondeva al nome della directory. Il rilancio e'
riuscito senza download. Gli output sono candidati per revisione e non misurano
accuratezza. Originali e sidecar sono rimasti intatti; nessuna modifica runtime,
claim o test. Prossimo passo: review condivisa dei due engine; valutare in
seguito OCR multilingue senza pre-caricare un'implementazione.

## Nota di sessione 2026-09-19 - asset OCR in percorsi persistenti

Installati sotto `C:\Users\info\AppData\Local\MeMoRiA\ocr-assets\` il
detector PP-OCRv5 e i recognizer Latin, English ed East Slavic come directory
modello dirette. La directory `tessdata` contiene `deu`, `eng`, `ita`,
`ita_old`, `osd` e `rus`. `TESSDATA_PREFIX` e' stato persistito per l'utente
con `setx` e verificato; `tesseract --list-langs` elenca tutte e sei le lingue.
Gli hash SHA-256 sorgente/destinazione coincidono per i quattro modelli
PP-OCRv5 e i traineddata staged.

Program Files ha negato la scrittura, quindi l'installazione e' stata completata
nel percorso per-utente senza privilegi amministrativi. Dopo la rimozione del
venv temporaneo, `memoria-engine/.venv` continua a importare Paddle 3.3.0 e
PaddleOCR 3.7.0. Rimosse da Temp solo `memoria-ppocr-v5-20260919` (venv, cache
e modelli duplicati) e `tesseract-5.5.3-language-data`; le cartelle Temp con i
report OCR sono rimaste. Non e' stato scaricato nulla e non sono state aggiunte
dipendenze runtime o riportati testi OCR reali.

## Nota di sessione 2026-09-19 - review geometrica OCR affiancata

Tesseract 5.5.3 `deu` ha usato gli asset persistenti e prodotto TSV/hOCR con
token, bounding box e confidence. PP-OCRv5 ha usato i modelli persistenti; il
report JSON e' in
`%TEMP%\memoria-ocr-review-20260919-persistent-layout\ppocrv5\ppocrv5_layout_report.json`.
Lato massimo ridimensionato da 6192 a 4000. `00026`: 49 linee, score medio
0.723182, 46.681 s; output confuso con box larghi e inclinati. `00028`: 59
linee, score medio 0.843398, 28.012 s; etichette circa tra x=694 e 1622 e
valori tra x=2296 e 2816 in fasce successive.

Senza reference umana validata non e' stata misurata accuratezza. I bounding
box OCR non equivalgono a celle tabellari e non preservano gli stili tipografici.
Nessun nuovo modello o test e' stato eseguito; immagini e sidecar sono intatti.

## Nota di sessione 2026-09-19 - pipeline OCR/layout e parsing documentale

Aggiornata la sezione roadmap con tre candidati di confronto offline, senza
selezione: OCR con geometria/layout ed eventuale LLM per formattazione o
correzioni; conversione documentale VLM diretta; parsing end-to-end PP-StructureV3
o Docling. Ogni proposta formattata/corretta deve restare collegata all'OCR
grezzo e alla provenance di token/regione, confidence, motore/modello e
trasformazioni; incertezza esplicita e nessun completamento senza evidenza.
Richieste metriche distinte per accuratezza/coverage, celle/reading order,
invenzioni, formattazione e risorse/latency, disaggregate per lingua e difficolta'
su fixture con reference umana. Specificato che i bbox non attribuiscono
semantica alle celle o recuperano lo stile tipografico; Markdown/Word sono
derivati, non trascrizioni archivistiche verificate. Aggiunti riferimenti alle
documentazioni upstream ufficiali PaddleOCR PP-StructureV3 e Docling senza claim
su qualita' o lingue. Nessun runtime o test applicativo modificato/eseguito.

## Nota di sessione 2026-09-19 - confronto PP-StructureV3 e Docling su 00028

Confronto completato su `T314-1275-00028.tif` (SHA-256
`661d6b0728033fa0526dcb83b9f4451b237a5fe52d986fc9d7a4f62d1779cab8`). Output
permanenti sotto
`C:\Users\info\AppData\Local\MeMoRiA\ocr-review\T314-1275-00028-structure-compare`:
Docling `docling_native.json/.md`; PP-StructureV3
`T314-1275-00028-longedge-2400_0_res.json/.md` e la derivata
`T314-1275-00028-longedge-2400.tif` (1408x2400); sintesi `comparison.md` e
provenance per engine nelle rispettive cartelle.

Docling ha rilevato una tabella 1x1 usando OCR `tesseract-cli` in lingua `deu`
in circa 75 secondi. PP-StructureV3 ha restituito 45 regioni di testo OCR e 2
blocchi di layout con MKL-DNN disabilitato; ha rilevato titolo/corpo e dot
leaders, ma nessuna griglia di celle, con corruzioni di umlaut/caratteri
sostitutivi. Il run a piena risoluzione ha incontrato un bug OneDNN; il risultato
PP riportato usa la derivata ridimensionata. Non e' disponibile una reference
umana, quindi non e' stata dichiarata accuratezza. Originale e sidecar intatti.

## Nota di sessione 2026-09-19 - pilot OCR + LLM locale su 00028

La roadmap ora formalizza il flusso OCR/layout -> pacchetto di evidenze -> LLM
locale -> proposta preview-only tracciabile. Pilot eseguito sul pacchetto
persistente di 00028 con `qwen2.5-coder:1.5b` via Ollama locale, senza download
né servizi remoti. Due risposte estese sono state troncate; la richiesta
compatta ha restituito JSON valido con tutti i 45 ID delle regioni, ciascuno
presente una volta. La struttura proposta è però debole: un solo ID è marcato
heading e i restanti 44 sono raggruppati in un unico paragraph; non ricostruisce
le sezioni né la tabella. Nessuna correzione OCR, accuratezza dichiarata o
test applicativo. Input, risposta grezza, proposta e verifica sono in
`%LOCALAPPDATA%\MeMoRiA\ocr-review\T314-1275-00028-hybrid-reconstruction`.
Audit del percorso sorgente: in `P:\Comune\Me.Mo.Ri.a\documenti_da_processare\foto\T314 R1275\test`
esiste `markdown\test-images-661d6b0728033fa0\tesseract-page-1.md`, output
Tesseract `deu` con stato `unreviewed` e timestamp 2026-09-17; non e' il run GPU.
La variante `documenti\_da\_processare` non esiste e nel percorso verificato
non risultano nuovi artefatti GPU. Nessun output e' attribuito a quel run.
Prossimo passo candidato: rivedere il risultato e restringere il task strutturale
per righe/colonne usando le coordinate OCR come evidenza, poi confrontare la
proposta con l'immagine senza richiedere una trascrizione umana preventiva.
