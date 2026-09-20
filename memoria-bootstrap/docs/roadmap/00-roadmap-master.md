# Roadmap Master Post-Migrazione

Data: 2026-07-18

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

## Sequenza roadmap aggiornata

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
`memoria-bootstrap/docs/ocr-structured-evidence-strategy.md`; la sequenza tecnica e' T35-T40.

## Stato corrente

Focus successivo: **T35 - PP-OCRv5 structured evidence contract e adapter**.
T34b non e' piu' un blocker; la fase esplorativa OCR/layout e' stata tradotta in
una sequenza implementativa T35-T40.

Completato:

- struttura multi-repo;
- data root esterno;
- package installabile e suite test ampia;
- CLI `memoria` con diagnostica e bridge read-only;
- catalogo fonti in `memoria-sources`;
- knowledge in `memoria-knowledge`;
- prompt e contratti LLM in `memoria-rules`;
- evidence/review store e output preview gia' presenti;
- interfaccia `WorkspaceStorage` e driver locale;
- manifest provider-aware.

Capacita' gia' osservabili ma non ancora confezionate in una golden run unica:

- documenti e claim candidati;
- decisioni di review;
- verified facts preview;
- profile patch preview;
- piani di feedback;
- dossier e report MVP distribuiti fra run differenti.

## Focus immediato

T34 preview e' chiusa e T34b e' completata. I set `block5e` e `block5f`
hanno registrato le decisioni umane sui 7 residui: 4 sono `accepted` e 3 sono
`rejected`. Le registrazioni restano preview-only e non modificano profili
canonici.

- T26-T28 cloud restano in hold;
- Q2 e l'apertura post-MVP possono riprendere secondo la selezione roadmap;
- i futuri interventi sui dati canonici richiedono un incremento separato e
  una decisione esplicita.

Decisione T33 del 2026-07-18: il caso principale e' stato dimostrato nella
golden run T30-T32. E' quindi autorizzata un'espansione controllata a tre casi,
purche' produca una sola nuova golden run canonica e tutti gli artefatti tecnici
e di presentazione puntino al medesimo `run_id`.

Documento operativo di riferimento:

```text
memoria-bootstrap/docs/funding-demo-golden-path.md
```

## Fuori scope per la golden run

- produzione massiva di schede;
- pubblicazione automatica;
- risoluzione automatica dei conflitti storici;
- migrazione cloud massiva;
- nuove acquisizioni indiscriminate;
- modifica canonica dei profili reali senza backup, decisione e audit;
- presentazione di output preview come fatti pubblicabili.
