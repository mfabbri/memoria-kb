# OCR Structured Evidence Strategy

Data: 2026-09-20

Stato: direzione architetturale selezionata per il post-MVP.

## Scopo

Portare scansioni storiche da immagine a Markdown revisionabile senza confondere
riconoscimento del testo, ricostruzione del layout e interpretazione semantica.
Il Markdown e' un derivato leggibile; l'evidenza primaria resta il testo OCR
collegato a regioni dell'immagine, confidence, motore, modello e trasformazioni.

Flusso guida:

```text
immagine originale
  -> OCR strutturato per regione
  -> OcrPageEvidence
  -> ricostruzione deterministica della struttura
  -> DocumentStructure
  -> Markdown derivato
  -> revisione umana
  -> extraction/claim solo negli step successivi
```

## Evidenze emerse dal codice e dai pilot

1. `document_analysis/ocr_tesseract.py` normalizza lo stdout Tesseract con
   `" ".join(...split())`: il campo testuale piatto perde newline e spaziatura.
   `transcription_registration.py` applica un'ulteriore normalizzazione analoga.
   Le righe TSV mantengono invece geometria separata e sono la base corretta per
   qualunque ricostruzione strutturale.
2. T35 ha aggiornato l'adapter PP-OCRv5: il contratto engine-neutral conserva
   testo, score e geometria per regione (`rec_scores`, poligoni e/o box), oltre
   alla provenance. Le implementazioni successive devono mantenere tali campi;
   non vanno piu' descritti come persi dall'adapter.
3. Il benchmark sintetico PP-OCRv5 del 2026-09-19 ha misurato soprattutto fedelta'
   testuale e non struttura. E' utile per scegliere il recognizer da portare al
   pilot successivo, non dimostra accuratezza archivistica su scansioni reali.
4. Sul campione `T314-1275-00028`, PP-StructureV3 e Docling non hanno ricostruito
   in modo utile la struttura visuale a dot leader; il pilot page-level con
   `qwen2.5-coder:1.5b` ha mantenuto gli ID delle regioni ma non ha ricostruito
   sezioni e righe in modo soddisfacente.
5. `T314-1275-00028` e' meglio modellato come report a sezioni con coppie
   label/valore e dot leader, non come tabella a griglia. `T314-1275-00026` e'
   invece soprattutto un problema di riconoscimento su testo degradato, con
   struttura macroscopica relativamente semplice.

## Decisioni

### 1. Recognizer primario del prossimo pilot

PP-OCRv5 diventa il recognizer primario **del percorso post-MVP corrente** per
le scansioni storiche. La decisione deriva dai benchmark e dai due campioni gia'
analizzati, ma non e' una dichiarazione che PP-OCRv5 sia universalmente il
miglior OCR per ogni archivio o lingua.

Tesseract resta:

- seconda lettura indipendente;
- fallback diagnostico;
- comparatore utile sulle regioni ambigue;
- sorgente legacy da mantenere compatibile finche' la nuova pipeline non e'
  validata.

### 2. Evidenza OCR prima del Markdown

Il nuovo contratto deve conservare almeno:

```text
OcrPageEvidence
  page_id
  source_image_hash
  transform_id
  engine
  model
  language
  regions[]
    region_id
    text
    confidence
    polygon
    bbox
    reading_order_hint
```

`reading_order_hint` e' una proposta derivata dalla geometria, non un fatto
semantico. `polygon` e/o `bbox` devono restare riferibili alle coordinate
originali, direttamente o tramite trasformazione documentata.

Il testo piatto normalizzato puo' restare per compatibilita' e ricerca, ma non e'
la sorgente canonica per ricostruire paragrafi, liste, colonne o tabelle.

### 3. Struttura come oggetto separato

La struttura derivata deve essere un contratto distinto:

```text
DocumentStructure
  page_id
  blocks[]
    block_id
    kind: heading | paragraph | key_value | list | table | marginalia
    source_region_ids[]
    confidence/status
    children[]
```

Ogni blocco deve rinviare alle regioni OCR che lo sostengono. Un renderer
Markdown non deve poter introdurre testo non presente nelle regioni, salvo un
marcatore esplicito come `[illeggibile]` o una correzione revisionata e
tracciata separatamente.

### 4. Layout deterministico prima di modelli generativi

Il primo parser strutturale usa coordinate, allineamento, distanza verticale,
indentazione, punteggiatura e pattern tipografici semplici. I primi due profili
sono:

- `leader_list_report`: sezioni, label, dot leader e valore allineato a destra;
  caso guida `T314-1275-00028`;
- `numbered_report`: titoli, sezioni numerate, paragrafi e continuation line;
  caso guida `T314-1275-00026`.

Non generalizzare subito a tutti i documenti. I profili sono espliciti,
testabili e possono dichiarare `unknown` quando il layout non e' riconosciuto.

### 5. Markdown come view derivata

Il Markdown viene generato da `DocumentStructure`, non direttamente dalla
stringa OCR normalizzata. Deve restare possibile risalire da ogni elemento
strutturale a `source_region_ids` e quindi all'immagine.

Il Markdown e' una trascrizione di lavoro revisionabile, non un documento
archivistico verificato e non una sorgente di claim senza review.

### 6. Immagini degradate: crop/tiling prima del downscale globale

Per scansioni ad alta risoluzione e testo degradato non rendere obbligatorio il
resize globale. Il pilot deve confrontare:

- originale/crop in grayscale;
- contrast enhancement non distruttivo;
- thresholding come variante separata, non sostitutiva;
- tile o bande sovrapposte a risoluzione vicina all'originale;
- merge geometrico delle regioni con coordinate riportate alla pagina sorgente.

Ogni trasformazione ha ID, parametri e hash del payload. Il raw originale resta
immutato.

### 7. VLM/LLM come resolver opzionale di ambiguita'

Non usare un VLM page-level per riscrivere l'intera pagina o produrre Markdown
libero. Un VLM puo' entrare solo dopo il baseline deterministico e solo su crop
selezionati, ad esempio quando:

- confidence OCR e' sotto soglia;
- PP-OCRv5 e Tesseract discordano;
- la struttura non puo' associare con sicurezza una continuation o un valore.

Input minimo: crop originale + candidati OCR + provenance. Output vincolato:
testo visibile o `[illeggibile]`, con temperatura zero e senza completamenti
congetturali. Il risultato resta una proposta revisionabile.

### 8. PP-StructureV3 e Docling fuori dal critical path

PP-StructureV3 e Docling restano strumenti di confronto e possono essere
riesaminati per classi documentali specifiche. Non sono dipendenze necessarie
per T35-T40 e non devono bloccare il pilot strutturato.

### 9. Quality gate: processabilita' non accuratezza

Lo stato corrente `ocr_quality_gate_status=accepted` indica che un risultato ha
superato soglie tecniche minime, non che il testo sia storicamente affidabile.
Gli incrementi successivi devono rendere esplicita la semantica di
**processability** e mantenere separati:

- riuscita tecnica del processo;
- confidence del recognizer;
- accuratezza misurata contro reference umana;
- stato di review dello storico.

Qualunque rinomina di campo deve preservare compatibilita' di lettura finche'
gli artefatti legacy sono in uso.

## Sequenza di implementazione

### T35 - PP-OCRv5 structured evidence contract e adapter

Conservare `rec_texts`, `rec_scores`, `rec_polys`/`rec_boxes` in un contratto
engine-neutral con region ID e provenance. Gli ID derivano dall'ordine dei
risultati e non sono ancore persistenti da soli: per riusare annotazioni
associarli all'hash/versione dell'artefatto o del run. Nessuna semantica
Markdown e nessun VLM.

### T36 - High-resolution transform e tiling pilot

Aggiungere trasformazioni tracciate e un pilot crop/tile sui due TIFF guida,
senza downscale globale obbligatorio. Merge delle regioni nella geometria della
pagina originale.

### T37 - Deterministic structure reconstruction + Markdown

Implementare `leader_list_report` e `numbered_report`, `DocumentStructure` e un
renderer Markdown che conserva i riferimenti alle regioni.

### T38 - Reference umana e metriche testuali/strutturali

Preparare una reference verificata per il pilot: pagina 00028 completa e crop
rappresentativi della 00026. Per valutare la scala, ampliare poi a un campione
iniziale complessivo di 30-50 pagine, stratificate per lingua, leggibilita' e
tipologia, con calibrazione e holdout distinti.
Questo campione e' esplorativo, non una garanzia statistica. Verificare anche
casualmente output che il triage non segnala. Misurare separatamente CER/WER o
metriche testuali, coverage, reading order, heading/paragraph, pairing
label-valore, invenzioni e
carico di review.

### T39 - Selective visual ambiguity resolver

Solo se T38 mostra un beneficio plausibile, introdurre un resolver VLM locale
per crop ambigui. Nessuna riscrittura page-level.

### T40 - Integrazione CLI del flusso validato

Portare il percorso validato sotto `memoria documents process` o comando
coerente, mantenendo preview/apply espliciti, provenance, idempotenza e review.
L'extraction storica e i claim consumano soltanto artefatti revisionabili e
tracciabili.

## Strategia per lotti di migliaia di immagini

Procedere per gate: pilot T36 sui due TIFF guida con output, crop e provenance
esposti per revisione condivisa; struttura/Markdown deterministici in T37;
reference e misure in T38; eventuale VLM in T39 solo se il confronto contro la
reference mostra beneficio; integrazione e aumento progressivo del batch in T40.
Prima di aumentare il volume, verificare la reference e mantenere una quota di
audit casuale anche sulle pagine non segnalate. Registrare throughput, latenza
p95, costo per 1000 pagine, minuti di revisione per 100 pagine e backlog.
Usare checkpoint idempotenti, retry limitati e isolamento degli errori. Nessuna
confidence o metrica di processabilita' sostituisce la verifica umana per fatti
pubblicabili, che richiedono fonte tracciabile.

## Stop condition

Non aggiungere nuovi framework OCR/layout prima di avere completato almeno T35,
T36 e il pilot T37 sui due documenti guida. Un nuovo framework entra nella
roadmap solo se risolve un difetto misurato che PP-OCRv5 + geometria + parser
deterministico non coprono.

## Relazione con Me.Mo.Ri.A

Questa strategia mantiene il principio generale:

```text
fonti -> documenti -> evidenze -> riconciliazione -> schede -> revisione umana
```

L'OCR non diventa un'autorita' storica. Trasforma una pagina in evidenza
tracciabile e revisionabile; soltanto gli step successivi possono proporre
entita', claim e aggiornamenti di profilo.
