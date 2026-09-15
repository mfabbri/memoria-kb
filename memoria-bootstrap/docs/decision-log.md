# Decision Log

## 2026-09-15 - Flusso review post-MVP senza assunzione di run preesistente

Decisione: la review CLI deve supportare sia la ripresa di una run esistente
sia l'avvio guidato quando non esiste una sessione attiva. `review discover`
individua le candidate; `review start --preview` seleziona la raccomandata o
una run esplicita; `review work`, `review targets` e `review decide --preview`
accompagnano la revisione senza scritture canoniche.

Per la review multi-profilo si usa una worklist comune con filtri ripetibili
`--profile-id`; l'identità operativa resta l'`item_id` collegato a profilo,
documento e provenance. Il filtro non fonde profili e non sostituisce la
revisione dei singoli target.

Conseguenza: guide e nuovi workflow devono descrivere il percorso con e senza
run preesistente. Nessun comando deve creare fatti, applicare patch, modificare
profili canonici o evidence store durante questa fase preview-only.

## 2026-09-15 - CLI come superficie per modificare JSON operativi

Decisione: evitare, come regola generale, la modifica diretta dei JSON
operativi. Quando un dato o artefatto deve essere cambiato, il percorso
preferito è un comando della CLI `memoria` o del workflow CLI approvato, con
validazione, provenance e audit coerenti.

L'editing diretto resta ammesso solo per fixture e test, import o migrazioni
controllati, oppure eccezioni esplicitamente motivate e verificate. La CLI
read-only non viene considerata sufficiente: se manca il comando operativo,
il lavoro successivo deve prima estendere la CLI entro un micro-incremento
delimitato. Nessuna scrittura canonica è autorizzata da questa decisione.

## 2026-09-15 - CLI Python come superficie operativa unica

Decisione: la direzione generale post-MVP è usare esclusivamente la CLI Python
installabile `memoria` per discovery, raccolta fonti, processazione, review,
consolidamento e produzione degli artefatti preview. I wrapper PowerShell
restano compatibili solo come ponte transitorio durante la migrazione, non come
superficie finale.

Conseguenza: ogni nuovo workflow operativo va introdotto nella CLI Python; la
migrazione dei wrapper esistenti procede per micro-incrementi, mantenendo
contratti, provenance, guardrail preview-only e compatibilità finché il
comando equivalente non è verificato.

## 2026-09-11 - Accettazione residui T34b

Decisione: accettare in modalita' preview i quattro `CandidateNewProfile`
residui (`Marciatori Adriano`, `Saba Mario`, `Tacconi Rosa`, `Bergonzoni
Lino`), registrando le scelte nel set esterno `review_decisions_block5f.json`.

Conseguenza: la revisione umana dei nuovi profili e' completa, ma non sono
stati creati profili canonici. Restano obbligatori dry-run, backup, rollback e
audit prima di qualsiasi applicazione.

## 2026-09-11 - Blocker materializzazione nuovi profili T34b

Il preflight read-only ha verificato che il percorso esistente di
`ProfilePatch` aggiorna profili JSON-LD gia' presenti, ma non definisce la
creazione canonica di un `CandidateNewProfile`. Prima di qualsiasi dry-run
applicativo va quindi definito il contratto di materializzazione, soprattutto
per `Tacconi Rosa`, che non ha un profilo canonico corrispondente trovato nel
data root.

## 2026-09-11 - Contratto preview CandidateNewProfile T34b

Implementato in `memoria-engine` il piano immutabile
`CandidateNewProfileMaterializationPlan`, separato da `ProfilePatch`. Il piano
consente solo preview e dry-run, conserva provenance e hash, distingue
`create_new`, `link_existing` e `blocked_collision` e prepara manifest,
rollback metadata e audit senza scrivere profili canonici.

## 2026-09-11 - Preflight reale T34b

Il nuovo adapter ha letto in sola memoria la coda T34 e il set `block5f`,
producendo quattro piani deterministici preview-only: tre `create_new` e un
`link_existing`. Il preflight ha mantenuto `canonical_write_count=0` e non ha
modificato il data root esterno.

## 2026-09-11 - Dry-run preview T34b

Generati nella run esterna il piano aggregato e il report dry-run dei quattro
nuovi profili. Gli artefatti dichiarano quattro piani, tre `create_new`, un
`link_existing`, zero scritture canoniche e stato
`ready_for_explicit_canonical_authorization`. Nessun profilo o indice e' stato
modificato.

## 2026-09-11 - Applicazione canonica T34b

Con autorizzazione esplicita dell'utente sono stati creati tre profili
canonici minimali (`Marciatori Adriano`, `Tacconi Rosa`, `Bergonzoni Lino`) e
aggiornato l'indice da 57 a 60 voci. `Saba Mario` e' stato collegato al profilo
esistente senza scrittura. Sono stati creati backup, audit JSON/Markdown e
rollback condizionato agli hash; nessun claim o `verified_fact` e' stato
promosso.

## 2026-09-10 - Revisione umana residui T34b

Decisione: registrare le sette scelte umane sui `CandidateNewProfile` residui
nel set esterno `review_decisions_block5e.json`, mantenendo quattro casi in
`needs_review` e rifiutandone tre. Il set resta `preview_only`; non sono stati
creati profili canonici e non sono state applicate patch.

Conseguenza: la migrazione T34b resta aperta per la gestione dei quattro casi
in sospeso e per la verifica di dry-run, backup, rollback e audit prima di
qualsiasi applicazione canonica.

## 2026-07-05 - Architettura multi-repo

Decisione: adottare una Knowledge Workspace Architecture multi-repo per
Me.Mo.Ri.A.

Repository principali:

- `memoria-bootstrap`;
- `memoria-engine`;
- `memoria-workspace`;
- `memoria-knowledge`;
- `memoria-rules`;
- `memoria-sources`.

Il data root reale resta esterno ai repository Git:

```text
P:\Comune\Me.Mo.Ri.a
```

Conseguenza: i repository non devono contenere dati reali o copie massive di
archivi.

## 2026-07-05 - Data root esterno

Decisione: gli incrementi tecnici devono riferirsi ai dati reali tramite
configurazione, non tramite copia.

Ordine di risoluzione baseline:

1. `--data-root`;
2. `MEMORIA_DATA_ROOT`;
3. `../memoria-workspace/manifest.yml`;
4. errore chiaro.

## 2026-07-05 - CLI diagnostica Python

Decisione: non creare una seconda CLI.

I comandi diagnostici read-only vivono nella CLI Python installabile esistente:

```text
caduti_fonti_report.memoria_cli:main
```

Comando installabile:

```text
memoria
```

Comandi baseline:

- `memoria data-root`;
- `memoria inventory`;
- `memoria doctor`.

## 2026-07-05 - CLI PowerShell legacy

Decisione: `scripts/memoria.ps1` resta la superficie dei workflow operativi
legacy/preview.

I workflow PowerShell non vengono migrati nella CLI Python senza una decisione
dedicata.

## 2026-07-05 - Definizione MVP

Decisione: l'MVP e' una dimostrazione del percorso dai documenti grezzi alla
scheda revisionabile.

Non e' una produzione automatica di schede pubblicabili definitive.

## 2026-07-05 - Procedura agent autonoma

Decisione: l'agent deve usare roadmap, stato corrente e decision log per
determinare autonomamente il prossimo incremento piccolo e verificabile.

Regola operativa:

- se l'incremento corrente e' aperto, continuare solo quello;
- se e' chiuso, scegliere il prossimo incremento dalla roadmap tecnica coerente
  con la roadmap MVP;
- aggiornare `current-next-increment.md` prima di iniziare nuovo lavoro;
- non saltare milestone;
- non eseguire task massivi, OCR, pipeline o generazione schede senza incremento
  esplicito.

Conseguenza: l'utente non deve chiedere ogni volta il prossimo passo, salvo
ambiguita' bloccanti.

## 2026-07-06 - Scoping demo MVP read-only

Decisione: la prima demo MVP deve essere definita prima come perimetro e criteri
di selezione, non come esecuzione di pipeline.

Regola metodologica:

- usare un set minimo e controllato;
- non copiare documenti reali nei repository Git;
- riferirsi ai materiali reali solo tramite data root esterno read-only;
- separare evidenza documentale, proposta di lavoro e revisione storica;
- non generare schede definitive.

Conseguenza: l'incremento T5 produce documentazione di scoping. L'eventuale
incremento successivo dovra' introdurre un artefatto revisionabile piccolo, prima
di qualunque automazione o trattamento dati.

## 2026-07-06 - Catalogo fonti in memoria-sources

Decisione: i cataloghi dichiarativi delle fonti non appartengono al package
installabile `memoria-engine`, ma al repository `memoria-sources`.

Materiale migrato:

- registry fonti;
- profili di ricerca;
- strategie di ricerca;
- logica risultati;
- logica dettaglio.

Regola tecnica: `memoria-engine` risolve prima `../memoria-sources` e mantiene
`ricerche` come fallback legacy fino alla rimozione controllata dei duplicati.

Conseguenza: gli incrementi successivi devono aggiornare wrapper e
documentazione, poi rimuovere i duplicati legacy solo dopo test completi.

## 2026-07-06 - Residui knowledge in memoria-knowledge

Decisione: luoghi operativi e glossari militari non appartengono al package
installabile `memoria-engine`, ma al repository `memoria-knowledge`.

Materiale classificato:

- `memoria-engine/ricerche/places`;
- `memoria-engine/ricerche/military_glossaries`.

Destinazioni previste:

- `memoria-knowledge/places`;
- `memoria-knowledge/glossary/military`.

Regola tecnica: `memoria-engine` dovra' preferire `../memoria-knowledge` per
questi cataloghi e mantenere eventuali fallback legacy solo durante la
transizione controllata.

Conseguenza: la migrazione fisica e l'aggiornamento dei loader avverranno in un
incremento successivo, con test mirati e senza copiare dati reali dal data root
esterno.

## 2026-07-07 - Profili persona e seed fuori dal package

Decisione: profili persona reali, seed CSV Purocielo e artefatti MVP preview non
devono essere trattati come knowledge generica o fixture del package
installabile.

Materiale classificato:

- `memoria-engine/ricerche/person_profiles`;
- `memoria-engine/ricerche/caduti_purocielo.csv`;
- `memoria-engine/ricerche/mvp`.

Regola tecnica: `memoria-engine` non deve dipendere da questi path come default
operativi impliciti. I profili operativi e gli artefatti di run devono vivere
nel data root esterno o essere passati con parametri espliciti. Nei repository
Git sono ammesse solo fixture sintetiche minime e documentazione metodologica.

Conseguenza: un incremento successivo dovra' rendere espliciti o rimuovere i
default runtime legacy e aggiornare documentazione e test senza copiare dati
reali nei repository.

## 2026-07-07 - CLI come superficie per stato profili

Decisione: l'hardening dei default legacy non deve scaricare sull'utente
l'obbligo ordinario di usare wrapper PowerShell con path espliciti.

Regola operativa: per verifiche read-only di stato profili/schede, la superficie
preferita deve essere la CLI Python installabile `memoria`, che risolve il data
root tramite `--data-root`, `MEMORIA_DATA_ROOT` o manifest e poi individua gli
artefatti attesi nel data root esterno.

Conseguenza: prima di proseguire con nuovi residui, va introdotto un incremento
di recupero T13b per aggiungere un comando CLI di stato profili/schede. Il
comando non deve ricadere su `memoria-engine/ricerche/person_profiles` e deve
restare read-only.

## 2026-07-07 - Traccia parallela di refactor continuo

Decisione: la qualita' e manutenibilita' del codice devono essere preservate con
una traccia parallela di audit e micro-refactor, non solo tramite interventi
funzionali.

Regola metodologica: sono ammessi audit modulari e micro-refactor
behavior-preserving quando hanno scope piccolo, test mirati e stop condition
esplicita. Restano vietati refactor ampi, cambi di CLI, schemi, pipeline o
framework senza decisione dedicata.

Conseguenza: la roadmap tecnica contiene una traccia Q parallela e il playbook
`09-continuous-refactor.md` definisce quando e come applicarla.

## 2026-07-07 - Prompt e contratti LLM in memoria-rules

Decisione: i prompt LLM versionabili e gli schemi che vincolano output
preview-only non appartengono al package installabile `memoria-engine`, ma al
repository `memoria-rules`.

Materiale classificato:

- `memoria-engine/ricerche/llm_prompts/chunk_classification.gemma3-4b.prompt.md`;
- `memoria-engine/ricerche/llm_prompts/chunk_classification.schema.json`.

Regola tecnica: questi artefatti sono contratti e regole operative per
classificazione LLM non promossa a fatto storico. `memoria-engine` potra'
risolverli da `../memoria-rules` e mantenere eventuale fallback legacy solo
durante una transizione controllata.

Conseguenza: un incremento successivo dovra' migrare i contratti in
`memoria-rules/llm_prompts/chunk_classification/`, aggiornare test e
documentazione, poi rimuovere il path legacy solo dopo validazione.

## 2026-07-07 - Stato editoriale profili canonici

Decisione: lo stato editoriale della scheda/profilo deve essere un contratto
esplicito, distinto dallo stato dei singoli hint, claim o output preview.

Osservazione: `memoria profiles status` legge `profile_status`,
`review_status` e `publication_status` a livello scheda/profilo, ma i 57 profili
Purocielo attuali espongono `review_status` solo dentro `search_hints`. La
migrazione non ha rimosso campi editoriali di scheda: quei campi non erano ancora
inizializzati nei profili canonici.

Regola metodologica: prima di modificare il data root esterno va definito il
contratto minimo dei campi editoriali, la loro collocazione e i valori iniziali
ammessi per profili seed/preview non revisionati. L'eventuale inizializzazione
dei profili reali richiedera' un incremento successivo con dry-run, backup e
autorizzazione esplicita.

Conseguenza: la roadmap tecnica introduce T17 per definire il contratto di stato
editoriale profili/schede. Q1 resta nella traccia qualita', ma non sostituisce
questo avanzamento funzionale/metodologico.

Aggiornamento 2026-07-08 T17: la forma canonica scelta per i profili persona e'
`metadata.profile_status`, `metadata.review_status` e
`metadata.publication_status`. I campi top-level possono restare tollerati come
compatibilita' di lettura, ma non sono la forma canonica per i profili canonici.
I valori iniziali per profili seed non revisionati sono `seed_profile`,
`unreviewed` e `not_publishable_without_human_review`.

## 2026-07-08 - CLI Python cross-platform come superficie canonica futura

Decisione: la direzione architetturale della CLI operativa e' rendere il console
script Python installabile `memoria` la superficie canonica cross-platform,
eseguibile su Windows e Linux.

Regola tecnica: i wrapper OS-specifici, inclusi `scripts/memoria.ps1` e un
eventuale wrapper shell Linux, devono diventare facciate sottili. La logica di
dominio, selezione run, review, fonti, report e decisioni non deve essere
duplicata tra PowerShell e shell script.

Compatibilita' MVP: l'MVP da mostrare ai finanziatori puo' restare basato sui
workflow PowerShell gia' validati, per praticita' operativa su Windows e per
ridurre il rischio della demo. Questa scelta e' una compatibilita' temporanea,
non la destinazione architetturale definitiva.

Conseguenza: la roadmap tecnica introduce T19 per pianificare una migrazione
progressiva dei workflow operativi verso `memoria`, partendo da bridge o comandi
Python piccoli e testabili, mantenendo invariati output osservabili, selezione
run, file sessione e risoluzione del data root.

## 2026-07-12 - Workspace operativo pluggable

Decisione: il workspace operativo di Me.Mo.Ri.A non deve dipendere in modo
permanente da un drive locale o di rete concreto.

Il path Windows:

```text
P:\Comune\Me.Mo.Ri.a
```

resta il backend locale compatibile e la superficie pratica per l'MVP gia'
validato, ma non e' la destinazione architetturale unica.

Regola tecnica: introdurre progressivamente un livello `WorkspaceStorage`
pluggable, con path logici del workspace e driver selezionabili tramite
manifest/configurazione:

- `LocalWorkspaceStorage` per il backend locale esistente;
- `PCloudWorkspaceStorage` come primo backend cloud candidato;
- altri provider futuri, ad esempio Google Drive, senza fork della logica
  applicativa.

Regola operativa: pCloud deve entrare prima in modalita' read-only, verificando
via REST cartelle gia' esistenti e relativi `folderid`, senza ricrearle e senza
caricare documenti reali. Solo dopo un incremento dedicato potranno essere
abilitate scritture diagnostiche sintetiche.

Conseguenza: la roadmap tecnica introduce T23-T28 per separare decisione,
interfaccia storage, manifest provider-aware, driver pCloud read-only, scrittura
diagnostica controllata e cache locale. L'MVP PowerShell/local non viene
bloccato dalla traiettoria cloud.

## 2026-07-12 - Golden run finanziatori come priorita' di roadmap

Decisione: dopo la stabilizzazione multi-repo e dei bridge read-only, la
priorita' del progetto e' costruire una sola golden run per la richiesta di
finanziamento.

Regola operativa: T29-T33 prevalgono su T26-T28 cloud e sui micro-refactor Q2.
Cloud, nuove fonti e refactor possono avanzare prima di T33 solo su richiesta
esplicita o se rimuovono un blocco diretto della demo.

Conseguenza: `current-next-increment.md` apre T29 e l'agent non deve scegliere
pCloud o un nuovo Q2 come passo ordinario.

## 2026-07-12 - Merge multi-fonte come criterio obbligatorio MVP

Decisione: una scheda revisionabile derivata da una sola fonte non e'
sufficiente per dimostrare il valore distintivo di Me.Mo.Ri.A.

La golden run deve mostrare almeno due fonti o famiglie documentali differenti
ricondotte allo stesso soggetto, mantenendo per ogni claim documento, fonte,
metodo, confidenza e stato di review. Il merge puo' mostrare conferma,
complementarita' o conflitto; non deve cancellare valori alternativi.

Conseguenza: T29 definisce il caso e T30 produce una tabella o vista esplicita di
riconciliazione multi-fonte.

## 2026-07-12 - Feedback loop chiuso come criterio obbligatorio MVP

Decisione: la sola generazione di feedback action o query candidate non prova il
feedback loop.

Per la demo almeno una lacuna o incertezza deve produrre una decisione dello
storico, un piano fonte-specifico, una ricerca controllata e un esito registrato.
L'esito puo' essere un nuovo documento/claim oppure un `no_results`,
`needs_manual_review` o `blocked_or_dynamic` motivato. In ogni caso deve rientrare
nella memoria di ricerca del profilo senza promozione automatica a fatto.

Conseguenza: T31 e' una milestone autonoma e obbligatoria prima del pacchetto
finanziatori.

## 2026-07-12 - Descrittore unico della demo

Decisione: tutti gli artefatti mostrati nella demo devono riferirsi a una run
canonica dichiarata, invece di selezionare implicitamente run differenti per
review, consolidamento e fonti.

T29 definisce il contratto; T30 introdurra' il descrittore nel data root esterno,
con nome definitivo da confermare, indicativamente:

```text
<data-root>/database/memoria_mvp_demo.active.json
```

Il descrittore non sostituisce store o manifest e non contiene documenti reali:
identifica run, profili, documenti, sessioni e artefatti ufficiali della demo.

## 2026-07-15 - Perimetro di scrittura workspace operativo

Decisione: per gli incrementi operativi autorizzati del progetto, il perimetro
massimo di scrittura sui dati reali e' limitato al workspace esterno:

```text
P:\Comune\Me.Mo.Ri.a
```

e alle sue sotto-cartelle.

Regola operativa: un agent puo' scrivere nel data root esterno solo quando la
scrittura e' necessaria all'incremento corrente, rispetta i criteri di uscita
documentati e resta dentro `P:\Comune\Me.Mo.Ri.a`. Scritture fuori da questo
workspace non sono autorizzate dalla policy di progetto.

La policy non autorizza azioni distruttive o promozioni canoniche implicite.
Restano vietati senza incremento esplicito, backup e audit:

- cancellazioni o sovrascritture massive;
- modifica di profili canonici;
- applicazione di `ProfilePatch`;
- promozione automatica di claim a fatti verificati canonici;
- modifica di documenti raw, OCR o fonti originali fuori dal perimetro
  dichiarato dell'incremento;
- copia di dati reali nei repository Git.

Conseguenza: T31 e gli incrementi successivi possono produrre artefatti
preview/audit nel data root esterno quando servono alla roadmap, ma devono
sempre dichiarare file toccati, validazioni eseguite e impatto sul workflow.
## 2026-07-18 - Espansione controllata della golden run T33 a tre casi

Decisione: sostituire la proposta di run comparativa T33c con una candidata a
nuova golden run canonica comprendente Andreoli, Balboni e Bendini.

Regole:

- l'attuale descriptor resta l'unico attivo durante preparazione e review;
- la candidata non alimenta una presentazione parallela;
- tutti gli artefatti tecnici, editoriali e T31 devono puntare allo stesso
  `run_id` candidato prima della promozione;
- la promozione avviene solo dopo decisioni storiche validate, readiness
  tecnica, backup e approvazione umana;
- dopo la promozione la run precedente resta archiviata ma non attiva;
- non vengono applicate patch, creati fatti canonici o prodotte schede
  pubblicabili.

Conseguenza: golden run tecnica e presentazione finanziatori restano due
oggetti narrativi, ma condividono una sola lineage evidenziale e un solo
descriptor canonico.

## 2026-08-29 - Routing modelli Codex tracciabile v2

Decisione: il parent Codex project-local usa Luna/medium come router/controller e
delega il lavoro sostanziale a custom agent specializzati: Luna per discovery e
documentazione, Terra per implementazione e quality review, Sol per architettura
e migrazioni.

Regola tecnica: non usare `[profiles.*]` nel `.codex/config.toml` di progetto.
Il routing intenzionale e' versionato in `planning/current-work.json`; gli hook
`SessionStart`, `SubagentStart` e `SubagentStop` registrano localmente il model
slug effettivo in `planning/.runtime/model-routing.ndjson`.

Regola di costo/rischio: la dimensione del repository non determina il tier.
Le scritture semplici confinate a docs/planner/config agent possono restare su
Luna; codice runtime passa almeno a Terra; trade-off architetturali passano a Sol.

Conseguenza: e' possibile confrontare route richiesta e modello realmente
eseguito senza salvare chain-of-thought o telemetria provider nel repository.

## 2026-08-29 - Migrazione prioritaria dei profili legacy

Decisione: dopo la chiusura di T33, la ricostruzione controllata dei 57 profili
ancora marcati con `seed.source = ricerche\\caduti_purocielo.csv` diventa la
priorità operativa immediata, prima di cloud e micro-refactor Q2.

La migrazione non consiste nel riscrivere il campo `seed` o nel rinominare i
profili esistenti. Ogni profilo deve essere ricostruito da documenti e fonti
strutturate, con `CandidateProfileUpdate`/`CandidateNewProfile`, provenance,
revisione umana, mappa vecchio→nuovo, dry-run, backup, rollback e audit.

I profili privi di copertura sufficiente restano invariati e vengono elencati
come residui legacy. Nessun claim viene promosso automaticamente e nessun
profilo canonico viene modificato dalla sola selezione di T34.

Decisione operativa: i profili legacy saranno lavorati in lotti massimi di 20.

## 2026-08-30 - Chiusura T34 lotto 2 senza promozione

Il secondo lotto operativo ha interrogato 20 profili tramite la CLI e il
connettore dichiarativo `storia_memoria_bo` di Storia e Memoria di Bologna.
Sono stati registrati 16 esiti `ok` e 4 `no_results`, ma nessun documento di
dettaglio `SourceDocument` e' risultato acquisibile per il lotto. Gli esiti
positivi restano pertanto candidati di ricerca, non evidenze claim-eligible:
la disambiguazione e la revisione umana precedono qualsiasi
`CandidateProfileUpdate`, `ProfilePatch` o modifica canonica. Il lotto viene
chiuso operativamente con stato aperto al gate successivo; i profili canonici
e il seed storico restano invariati.

Lezioni operative registrate: per T34 usare gli ID completi
`person:purocielo:<slug>` e il flag `-ExecuteFirstPlannedAttempt` per le
ricerche live; il wrapper di pipeline non espone `ResultsDir`, i job isolati
richiedono percorsi assoluti e le cartelle profilo vanno create prima
dell'acquisizione. Un esito `ok` senza `SourceDocument` resta un candidato
ambiguo, non un'evidenza; i run paralleli devono mantenere separati output,
provenance, revisione e audit per profilo.
Intake e generazione candidati possono essere batch, ma revisione, provenance,
backup, audit e applicazione restano distinguibili per singolo profilo.

## 2026-08-30 - Regole di riconciliazione T34 emerse dalla migrazione

Decisioni operative durevoli:

- quando il registry viene letto da `memoria-sources/registry/...`, la root del
  repository deve risalire a `memoria-engine`; il fallback non deve sostituire
  la logica di dettaglio delle fonti;
- alias e nominativi alternativi si aggiungono su `/identity/aliases/-` senza
  sostituire il nome canonico;
- ruoli o funzioni di brigata aggiuntivi si aggiungono su `/formations/-`,
  mantenendo i valori legacy gia' presenti;
- un candidato ridondante rispetto al valore legacy produce una decisione di
  nessuna modifica e una patch preview senza operazioni;
- date discordanti e appartenenze conflittuali restano `pending` finche' non
  esiste una decisione umana esplicita e sostenuta dalla provenance;
- le decisioni accettate generano sempre patch preview auditabili; l'eventuale
  applicazione canonica e' un passo separato, con backup e verifica.

Conseguenza: i conteggi, i profili e le decisioni specifiche restano negli
artefatti dei run esterni; questo log conserva soltanto le regole riutilizzabili.

## 2026-09-10 - T34b prima del post-MVP

Decisione: la chiusura operativa della migrazione dei profili legacy diventa la
priorità immediata prima dell'apertura della fase post-MVP, dei micro-refactor
Q2 e della traiettoria cloud.

Motivazione: T34 ha chiuso intake, generazione candidati e revisione preview,
ma non deve essere considerata definitivamente conclusa finché conteggi e
residui non sono riconciliati e non sono stati verificati dry-run, backup,
rollback, audit e l'eventuale applicazione canonica autorizzata.

Vincoli: nessuna ProfilePatch viene applicata dalla sola selezione della
priorità; nessun claim viene promosso automaticamente; i profili senza
copertura sufficiente restano residui legacy espliciti.

## 2026-08-31 - Revisione manuale a blocchi e correzioni auditabili

Decisione: la revisione di worklist di profili procede per blocchi numerati,
ma il riferimento vincolante di ogni scelta e' il `candidate_update_id`, non
il solo nome visualizzato. Prima di registrare un blocco successivo gli ID gia'
decisi vengono esclusi e i conteggi devono essere verificati.

Decisione operativa: un registro prodotto da un mapping errato non viene
cancellato. Viene marcato `invalidated` e sostituito da un artefatto correttivo
che riferisce il registro precedente; le decisioni corrette devono essere
registrate separatamente e restano preview-only.

Conseguenza: la chiusura della revisione significa copertura classificata e
audit completa, non applicazione automatica delle patch o creazione canonica
dei nuovi profili.

## 2026-09-01 - Fallback operativo del controller

Decisione: quando la delega a un subagent non e' disponibile, il controller
puo' eseguire direttamente un micro-incremento `medium` gia' delimitato dal
planner, mantenendo invariati write_set, stop condition e quality gate.

Il fallback non si applica a review, migrazioni, architettura o conflitti di
contratto; questi richiedono ancora l'agente dedicato. Ogni fallback deve essere
registrato nel planner prima dell'esecuzione.

Conseguenza: l'assenza del subagent non blocca i micro-refactor runtime sicuri
e verificabili e non richiede all'utente di esplicitare il modello o l'agente.

## 2026-09-02 - Identificatori univoci dei custom agent Codex

Decisione: gli agenti Me.Mo.Ri.A usano il prefisso `mmr_` in configurazione,
planner e policy (`mmr_scanner`, `mmr_docs_reviewer`, `mmr_docs_editor`,
`mmr_implementer`, `mmr_test_reviewer`, `mmr_architect`). Modelli,
reasoning, sandbox e confini di responsabilita' restano invariati.

Conseguenza: il validator richiede corrispondenza uno-a-uno tra chiave
`[agents.*]`, file TOML, campo `name` e route del planner. Gli hook restano
la fonte di evidenza dell'effettiva delega: una configurazione valida non
sostituisce l'avvio runtime del subagent.
