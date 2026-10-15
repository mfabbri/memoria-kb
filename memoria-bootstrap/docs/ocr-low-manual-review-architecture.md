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
   deterministico.
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
