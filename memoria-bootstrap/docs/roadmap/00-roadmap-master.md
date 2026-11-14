# Roadmap Master Post-Migrazione

Data di impianto: 2026-07-18; stato aggiornato al 2026-11-01

Scope: architettura multi-repo Me.Mo.Ri.A in `D:\CaDiMalanca\me.mo.ri.a-kb`.

## Architettura di riferimento

La workspace e' organizzata in repository separati:

- `memoria-bootstrap`: metodo operativo, playbook, roadmap, decisioni e contratti;
- `memoria-engine`: codice installabile e testabile, inclusa la CLI Python `memoria`;
- `memoria-workspace`: descrittore della workspace, senza dati reali versionati;
- `memoria-knowledge`: conoscenza di dominio, glossari, criteri e modelli;
- `memoria-rules`: regole deterministiche di provenance, merge, review e validazione;
- `memoria-sources`: cataloghi, wrapper e metadata delle fonti.

Il workspace operativo reale resta esterno ai repository Git. Il backend locale
compatibile e':

```text
P:\Comune\Me.Mo.Ri.a
```

La destinazione architetturale non e' un drive specifico: il workspace e' una
risorsa logica con backend configurabile. Il backend locale resta la superficie
pratica per l'MVP; provider cloud futuri non devono bloccare la demo.

## Principio MVP

L'MVP non e' produzione automatica di schede pubblicabili definitive.

L'MVP deve dimostrare un percorso verificabile:

```text
documenti grezzi e fonti eterogenee
  -> documenti identificabili
  -> evidenze con provenance
  -> riconciliazione multi-fonte
  -> decisione dello storico
  -> scheda/profilo revisionabile e patch preview
  -> feedback di ricerca
  -> nuova interrogazione o esito documentato
```

Ogni output deve distinguere evidenza, proposta automatica, decisione umana e
stato di pubblicabilita'.

## Criteri obbligatori per l'MVP finanziatori

La demo e' finanziabile solo quando mostra nello stesso caso di studio:

1. almeno due documenti provenienti da fonti o famiglie documentali differenti;
2. una vista unica che mantiene provenance, divergenze e incertezze;
3. almeno una decisione storica esplicita su un claim;
4. almeno un `verified_fact` o equivalente esclusivamente preview;
5. almeno una `ProfilePatch` preview collegata a documento, claim e decisione;
6. almeno un feedback loop chiuso, dalla richiesta di nuova ricerca all'esito;
7. una sola run canonica e ripetibile usata da tutti gli artefatti della demo.

Il merge multi-fonte non significa appiattire le fonti. Significa ricondurre
claim compatibili o conflittuali allo stesso soggetto, conservando sempre il
contributo specifico di ciascun documento.

Il feedback loop non e' dimostrato dalla sola generazione di centinaia di query.
Deve esistere almeno un percorso auditabile:

```text
gap o conflitto
  -> decisione dello storico `request_more_sources` o equivalente
  -> piano di ricerca fonte-specifico
  -> esecuzione controllata
  -> nuovo documento/evidenza oppure `no_results` documentato
  -> aggiornamento della memoria di ricerca del profilo
```

## Decisione di direzione post-MVP — 2026-11-01

**Funding MVP concluso**: T29-T33 (golden run e pacchetto finanziatori) e
T34/T34b (migrazione profili) sono chiusi. T35-T40, T42, T43 e T44 forniscono
la base OCR/review; T41 resta distinto tra pilot empirico chiuso e gate
statistico formale non dimostrato. Le righe storiche sotto descrivono le
priorita' al tempo delle decisioni e non riaprono la golden run.

La sequenza T45-T52 ha completato il software e i percorsi documentati.
**Decisione successiva del 2026-11-14 (prevale sulle precedenti):**
T27/T28 pCloud e T41 OCR sono **sospesi**, senza avvio automatico. La nuova
sequenza di prodotto proposta è T53-T58: baseline del workspace operativo,
deduplicazione multi-attempt, dossier multi-fonte reale, relazioni tipizzate
Person/Place/HistoricalEvent, memoria incrementale e certificazione fonti.
Vedi `docs/current-focus.md` e roadmap tecnica per priorità, dipendenze e gate.
I KPI T49 incompleti si misurano su futuri run reali, non con fixture inventate.
Ogni modifica ai profili canonici resta soggetta a preview, review e audit.
Il gate statistico OCR resta distinto e rinviato; Q2 solo opportunistico.

Non confondere `provisional_auto_validated` con `human_verified` o un fatto
storico. Il cutoff T42 1.0 e' non discriminante; nessuna inferenza sul tasso
futuro di errori. Il data root reale e' esterno a Git.

## Sequenza roadmap aggiornata (storico fino al 2026-09)

1. Stabilizzare il perimetro post-migrazione. **Completato**.
2. Rendere `memoria-engine` installabile, testabile e diagnosticabile.
   **Completato**.
3. Separare codice, workspace, knowledge, rules e sources. **Completato**.
4. Esporre orientamento read-only tramite CLI Python. **Completato per il
   perimetro attuale**.
5. Definire il contratto della golden run finanziatori. **T29, prioritario**.
6. Produrre una run canonica con merge multi-fonte e artefatti coerenti. **T30**.
7. Chiudere almeno un feedback loop storico. **T31**.
8. Correggere incoerenze, test e presentazione della demo. **T32**.
9. Preparare il pacchetto finanziatori e il walkthrough. **T33**.
10. Ricostruire e migrare in modo controllato i 57 profili ancora marcati come
    legacy. **T34, nuova priorità**.
11. Chiudere operativamente la migrazione residua con revisione, dry-run,
    backup, rollback e audit. **T34b, completato**.
12. Riprendere il flusso del prodotto completo: post-MVP/Q2 secondo selezione
    roadmap; storage cloud e nuove fonti restano subordinati alle priorita'.
13. Rendere il flusso di acquisizione immagini, OCR e revisione dei candidati
    utilizzabile dalla CLI Python. La direzione e' ora T35-T40: evidenza
    strutturata PP-OCRv5, high-resolution tiling, struttura deterministica,
    Markdown derivato, reference/metriche, eventuale VLM selettivo e integrazione
    CLI.

Aggiornamento operativo 2026-09-11: T34b ha completato applicazione canonica,
backup, rollback metadata e audit post-run. La migrazione profili e' chiusa;
si puo' riprendere il flusso del prodotto completo.

## Direzione CLI

La superficie canonica futura e' il console script Python installabile
`memoria`, utilizzabile su Windows e Linux. I wrapper OS-specifici devono
progressivamente diventare facciate sottili.

Regola operativa: le modifiche agli artefatti e ai dati JSON operativi devono
passare dalla CLI o da un workflow CLI approvato, non dall'editing manuale dei
file. Fixture, test, import/migrazioni controllati ed eccezioni motivate sono
gli unici casi ammessi, sempre con validazione e audit.

Direzione generale post-MVP: la CLI Python installabile `memoria` deve diventare
l'unica superficie operativa per discovery, raccolta fonti, processazione,
review, consolidamento e produzione degli artefatti preview. I wrapper
PowerShell restano solo un ponte compatibile durante la migrazione; ogni nuovo
workflow va aggiunto alla CLI Python e i wrapper esistenti vanno sostituiti per
micro-incrementi verificabili.

Il flusso per immagini e documenti con elementi grafici deve distinguere
intake e tracciamento dei file, OCR, ricostruzione della struttura e
interpretazione. L'OCR attuale produce testo e diagnostica; un report Markdown
di stato non equivale a una trascrizione Markdown strutturata. Tabelle,
diagrammi e cartine richiedono capacità e verifiche dedicate. L'output può
proporre collegamenti e claim candidati, ma non promuovere fatti né modificare
profili canonici senza revisione umana.

Per l'MVP finanziatori, i workflow PowerShell gia' validati possono restare la
superficie operativa per le azioni preview che scrivono artefatti. La CLI Python
fornisce orientamento e stato read-only. La migrazione completa dei workflow non
deve ritardare T29-T33.

## Direzione OCR strutturato selezionata - 2026-09-20

Dopo i pilot Tesseract, PP-OCRv5, Qwen, PP-StructureV3 e Docling, il post-MVP
non prosegue aggiungendo framework in parallelo. La traiettoria scelta e':

```text
immagine
  -> PP-OCRv5 con regioni/geometria/confidence
  -> OcrPageEvidence
  -> struttura deterministica
  -> DocumentStructure
  -> Markdown derivato e revisionabile
```

Tesseract resta fallback/comparatore. VLM solo su crop ambigui e soltanto dopo
metriche con reference umana. PP-StructureV3 e Docling restano fuori dal
critical path. Il documento autorevole e'
`memoria-bootstrap/docs/ocr-structured-evidence-strategy.md`; la sequenza tecnica e' T35-T42.

## Stato corrente al 2026-11-14

- MVP finanziatori T29-T33 e migrazione legacy T34/T34b chiusi secondo gli
  artifact e il planner; la run canonica reale va comunque verificata sul data
  root esterno quando la si riesegue.
- OCR T35-T40, T42-T44: capacità implementate; T41 pilot provisional chiuso,
  gate formale 5%/95% aperto con campioni e holdout insufficienti.
- T45-T51: software e cicli operativi documentati completati; T49 conserva KPI
  non misurati (claim attribution, conflitti, token/costi, confronto sessioni).
- T52a-c completati. La priorità successiva è T53-T58 (vedi focus operativo).
  T27/T28 pCloud e T41 OCR sospesi; KPI T49 e Q2 non bloccano i pilot reali.
- I 18 profili fonte nel registry sono configurazioni: non equivalgono a 18
  fonti live verificate. Evitare ulteriori adapter legacy.
- Per i nuovi task usare la policy Codex 3.1 e il planner `current-work.json`.

## Fuori scope per la golden run

- produzione massiva di schede;
- pubblicazione automatica;
- risoluzione automatica dei conflitti storici;
- migrazione cloud massiva;
- nuove acquisizioni indiscriminate;
- modifica canonica dei profili reali senza backup, decisione e audit;
- presentazione di output preview come fatti pubblicabili.
