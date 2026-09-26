# Technical Roadmap

Data: 2026-07-12

## Obiettivo tecnico post-migrazione

Rendere l'architettura multi-repo stabile, installabile e verificabile prima di
aggiungere nuova logica applicativa. Ogni milestone deve essere piccola,
verificabile e allineata alla roadmap MVP.

## Confini repository

- `memoria-bootstrap`: documentazione operativa e decisioni.
- `memoria-engine`: package Python, test e CLI installabile.
- `memoria-workspace`: manifest e descrizione del data root esterno.
- `memoria-knowledge`: conoscenza storica e modelli concettuali.
- `memoria-rules`: regole deterministiche e criteri di validazione.
- `memoria-sources`: descrizione e wrapper delle fonti.

## Workspace operativo

Il workspace operativo resta fuori dai repository Git. Il backend locale
compatibile attuale e':

```text
P:\Comune\Me.Mo.Ri.a
```

La risoluzione locale legacy deve continuare a seguire questo ordine finche'
non viene introdotto il manifest provider-aware:

1. parametro `--data-root`;
2. variabile ambiente `MEMORIA_DATA_ROOT`;
3. `../memoria-workspace/manifest.yml`;
4. errore chiaro se non disponibile.

La destinazione architetturale e' un `WorkspaceStorage` pluggable: il motore
deve lavorare su path logici del workspace, mentre il backend puo' essere
`local`, `pcloud` o un provider futuro. `P:\Comune\Me.Mo.Ri.a` resta quindi
backend locale compatibile, non vincolo architetturale permanente.

## Strategia CLI cross-platform

La CLI Python installabile `memoria` e' l'unica autorita' per i workflow
operativi. Deve restare eseguibile come console script su Windows e Linux,
usando path espliciti, `MEMORIA_DATA_ROOT` o manifest per risolvere il data root.

Debito tecnico CLI: `scripts/memoria.ps1` contiene una superficie PowerShell
autonoma che si sovrappone alla CLI Python e non inoltra tutti i comandi. La
coesistenza di dispatcher con lo stesso nome e' una duplicazione di interfaccia
da rimuovere. Inventariare i comandi e i comportamenti PowerShell, migrare nella
CLI Python quelli ancora mancanti e verificare la parita' con test. Subito dopo
la migrazione completa, eliminare l'implementazione autonoma PowerShell: nella
stessa chiusura il percorso `.ps1` puo' restare soltanto come launcher sottile
che inoltra senza filtri ogni argomento alla CLI Python. Non mantenere un
periodo di doppia implementazione o comandi divergenti.

I wrapper OS-specifici sono ammessi esclusivamente come launcher sottili. La
logica di dominio, selezione run, review, fonti e decisioni deve vivere una
sola volta nella CLI Python. Ogni migrazione deve essere incrementale,
behavior-preserving, verificata offline e mantenere provenance, audit e
guardrail. L'MVP finanziatori non giustifica una seconda implementazione CLI:
anche i workflow Windows gia' validati rientrano nell'inventario di parita'.

## Milestone tecniche

### T1 - Baseline multi-repo validabile

Dipendenze: nessuna.

Collegamento MVP: Incremento MVP 0 - Baseline post-migrazione.

Criteri di ingresso:

- workspace multi-repo presente;
- data root esterno noto;
- vincolo di non copiare dati reali confermato.

Criteri di uscita:

- repository sibling verificati;
- `memoria-workspace` confermato descriptor-only;
- data root esterno raggiungibile in sola lettura;
- checklist post-migrazione aggiornata.

Stato: chiusa.

### T2 - CLI diagnostica installabile

Dipendenze: T1.

Collegamento MVP: Incremento MVP 0 - Baseline post-migrazione.

Criteri di ingresso:

- `memoria-engine` installabile o problemi di packaging documentati;
- entry point CLI esistente identificato;
- decisione presa di non creare una seconda CLI.

Criteri di uscita:

- `memoria data-root` funziona;
- `memoria inventory` funziona senza opzioni;
- `memoria doctor` verifica data root e repository sibling;
- `pytest` passa;
- documentazione CLI aggiornata.

Stato: chiusa.

### T3 - Workspace inventory non invasivo

Dipendenze: T2.

Collegamento MVP: Incremento MVP 0 - Baseline post-migrazione, preparazione
leggera per Incremento MVP 1.

Criteri di ingresso:

- CLI diagnostica installabile disponibile;
- data root risolvibile tramite `--data-root`, `MEMORIA_DATA_ROOT` o manifest;
- vincolo read-only sul data root confermato.

Criteri di uscita:

- `memoria inventory` continua a funzionare senza opzioni;
- `memoria inventory --section risultati` produce un riepilogo leggero;
- `memoria inventory --section documenti_processati` produce un riepilogo leggero;
- `memoria inventory --section all` produce riepilogo delle sezioni supportate;
- `memoria inventory --output markdown` produce markdown leggibile;
- nessuna scansione ricorsiva profonda;
- nessun file del data root modificato;
- `pytest` passa.

Stato: chiusa.

### T4 - Procedura agent autonoma

Dipendenze: T3.

Collegamento MVP: supporta tutti gli incrementi MVP evitando salti di milestone.

Criteri di ingresso:

- roadmap master, MVP e tecnica disponibili;
- `current-next-increment.md` presente;
- decision log presente;
- playbook sviluppatore presente.

Criteri di uscita:

- procedura giornaliera agent documentata;
- prompt riutilizzabile per nuove sessioni disponibile;
- `current-next-increment.md` usa sezioni operative standard;
- roadmap tecnica contiene ID, dipendenze, criteri di ingresso e uscita;
- decisioni nuove registrate se necessario.

Stato: chiusa.

### T5 - MVP demo scoping read-only

Dipendenze: T4.

Collegamento MVP: Incremento MVP 1 - Demo review minima.

Criteri di ingresso:

- processo agent autonomo documentato;
- inventario superficiale disponibile;
- vincoli su data root esterno e dati reali confermati.

Criteri di uscita:

- perimetro demo MVP descritto in documentazione;
- criteri di selezione di un set piccolo e controllato definiti;
- nessun documento reale copiato nei repository;
- nessun OCR, extraction, JSON-LD o pipeline lanciato;
- decisioni metodologiche registrate nel decision log se introdotte.

Stato: chiusa.

### T6 - Migrazione catalogo fonti in memoria-sources

Dipendenze: T5.

Collegamento MVP: supporto tecnico a Incremento MVP 1, separando cataloghi
fonte da codice installabile.

Criteri di ingresso:

- perimetro demo MVP read-only documentato;
- residui post-migrazione in `memoria-engine/ricerche` identificati;
- repository `memoria-sources` disponibile.

Criteri di uscita:

- registry e livelli dichiarativi fonte presenti in `memoria-sources`;
- `memoria-engine` risolve `memoria-sources` come catalogo primario;
- fallback legacy su `ricerche` mantenuto per transizione;
- test mirati passano;
- nessun documento reale copiato nei repository;
- nessun OCR, extraction, JSON-LD o pipeline lanciato.

Stato: chiusa.

### T7 - Hardening wrapper e rimozione duplicati source

Dipendenze: T6.

Collegamento MVP: supporto tecnico a Incremento MVP 1.

Criteri di ingresso:

- catalogo fonte primario in `memoria-sources`;
- fallback legacy ancora presente in `memoria-engine/ricerche`;
- script e documentazione con riferimenti legacy identificati.

Criteri di uscita:

- script PowerShell e documentazione puntano al registry in `memoria-sources`;
- test completi o suite mirata estesa passano;
- duplicati legacy `source_*` rimossi o marcati per rimozione con decisione
  esplicita;
- nessun dato reale copiato nei repository;
- nessun OCR, extraction, JSON-LD o pipeline lanciato.

Stato: chiusa.

### T8 - Rimozione duplicati source legacy

Dipendenze: T7.

Collegamento MVP: supporto tecnico a Incremento MVP 1.

Criteri di ingresso:

- wrapper e documentazione puntano a `memoria-sources`;
- duplicati `source_*` marcati come fallback legacy;
- test mirati T7 passanti.

Criteri di uscita:

- duplicati `memoria-engine/ricerche/source_*` rimossi fisicamente;
- resolver Python continua a usare `memoria-sources`;
- eventuali riferimenti legacy rimasti sono solo test espliciti o documentazione
  storica;
- suite estesa passa;
- nessun dato reale copiato nei repository;
- nessun OCR, extraction, JSON-LD o pipeline lanciato.

Stato: chiusa.

### T9 - Classificazione residui knowledge

Dipendenze: T8.

Collegamento MVP: supporto tecnico a Incremento MVP 1.

Criteri di ingresso:

- duplicati source rimossi da `memoria-engine/ricerche`;
- residui non-source ancora presenti in `memoria-engine/ricerche`;
- piano residui post-migrazione disponibile.

Criteri di uscita:

- `places/` e `military_glossaries/` classificati per ownership;
- destinazione `memoria-knowledge` confermata o alternative motivate;
- loader e riferimenti da aggiornare identificati;
- nessun dato reale copiato dal data root esterno;
- nessun OCR, extraction, JSON-LD o pipeline lanciato.

Stato: chiusa.

### T10 - Migrazione knowledge minima

Dipendenze: T9.

Collegamento MVP: supporto tecnico a Incremento MVP 1.

Criteri di ingresso:

- `places/` e `military_glossaries/` classificati come knowledge versionabile;
- destinazioni `memoria-knowledge/places` e
  `memoria-knowledge/glossary/military` confermate;
- loader e wrapper legacy identificati.

Criteri di uscita:

- seed versionabili copiati da `memoria-engine/ricerche/places` a
  `memoria-knowledge/places`;
- glossari militari copiati da `memoria-engine/ricerche/military_glossaries` a
  `memoria-knowledge/glossary/military`;
- loader e wrapper preferiscono `../memoria-knowledge` mantenendo fallback
  legacy espliciti se necessari;
- test mirati place linking, military glossary e runner passano;
- nessun dato reale copiato dal data root esterno;
- nessun OCR, extraction, JSON-LD o pipeline lanciato.

Stato: chiusa.

### T11 - Rimozione legacy knowledge

Dipendenze: T10.

Collegamento MVP: supporto tecnico a Incremento MVP 1.

Criteri di ingresso:

- seed versionabili presenti in `memoria-knowledge`;
- loader e wrapper preferiscono `../memoria-knowledge`;
- fallback legacy `places/` e `military_glossaries/` ancora presenti in
  `memoria-engine/ricerche`.

Criteri di uscita:

- `memoria-engine/ricerche/places` rimosso o marcato come fallback non
  operativo motivato;
- `memoria-engine/ricerche/military_glossaries` rimosso o marcato come fallback
  non operativo motivato;
- riferimenti runtime a `ricerche/places` e `ricerche/military_glossaries`
  assenti o esplicitamente legacy;
- test mirati place linking, military glossary e runner passano;
- nessun dato reale copiato dal data root esterno;
- nessun OCR, extraction, JSON-LD o pipeline lanciato.

Stato: chiusa.

### T12 - Audit profili persona e seed

Dipendenze: T11.

Collegamento MVP: supporto tecnico a Incremento MVP 1.

Criteri di ingresso:

- residui source e knowledge rimossi o migrati;
- `person_profiles/`, `caduti_purocielo.csv` e `mvp/` ancora presenti in
  `memoria-engine/ricerche`;
- vincoli su dati reali e seed legacy confermati.

Criteri di uscita:

- `person_profiles/`, `caduti_purocielo.csv` e `mvp/` classificati per
  ownership, rischio e destinazione;
- riferimenti runtime, wrapper e documentazione da aggiornare identificati;
- eventuale destinazione `memoria-knowledge`, data root esterno o fixture
  sintetiche motivata;
- nessun dato reale copiato dal data root esterno;
- nessun OCR, extraction, JSON-LD o pipeline lanciato.

Stato: chiusa.

### T13 - Hardening default profili persona e seed

Dipendenze: T12.

Collegamento MVP: supporto tecnico a Incremento MVP 1.

Criteri di ingresso:

- `person_profiles/`, `caduti_purocielo.csv` e `mvp/` classificati per
  ownership, rischio e destinazione;
- riferimenti runtime e documentali legacy identificati;
- vincolo di non copiare dati reali nei repository confermato.

Criteri di uscita:

- default runtime che puntano a `memoria-engine/ricerche/person_profiles` resi
  espliciti o sostituiti da risoluzione tramite data root esterno;
- default runtime che puntano a `memoria-engine/ricerche/caduti_purocielo.csv`
  rimossi o bloccati salvo input esplicito;
- riferimenti documentali aggiornati per distinguere profili operativi, preview
  e fixture sintetiche;
- test mirati su profili persona, runner e wrapper passano;
- nessun dato reale copiato dal data root esterno;
- nessun OCR, extraction, JSON-LD o pipeline lanciato.

Stato: chiusa.

### T13b - CLI stato profili e schede da data root

Dipendenze: T13.

Collegamento MVP: supporto tecnico a Incremento MVP 1, rendendo verificabile lo
stato delle schede/profili senza tornare ai wrapper PowerShell con path manuali.

Criteri di ingresso:

- CLI Python diagnostica `memoria` installabile;
- default legacy verso `memoria-engine/ricerche/person_profiles` rimossi;
- data root risolvibile tramite `--data-root`, `MEMORIA_DATA_ROOT` o manifest;
- profili operativi attesi nel data root esterno, non nel package.

Criteri di uscita:

- comando CLI read-only per stato profili/schede disponibile, ad esempio
  `memoria profiles status` o nome equivalente documentato;
- il comando risolve l'indice profili dal data root esterno senza richiedere
  `-ProfilesIndex` nei casi ordinari;
- nessun fallback verso `memoria-engine/ricerche/person_profiles`;
- output sintetico leggibile con conteggi, path risolto e stato review/pubblicazione
  quando disponibile;
- test mirati CLI passano;
- documentazione CLI aggiornata;
- nessun dato reale copiato nei repository;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Stato: chiusa.

### T14 - Prompt e regole operative

Dipendenze: T13b.

Collegamento MVP: supporto tecnico a Incremento MVP 1.

Criteri di ingresso:

- default profili persona e seed hardenizzati;
- `llm_prompts/` ancora presente in `memoria-engine/ricerche`;
- vincoli su dati reali, prompt operativi e regole deterministiche confermati.

Criteri di uscita:

- `llm_prompts/` classificato per ownership, rischio e destinazione;
- destinazione `memoria-rules`, `memoria-bootstrap`, fixture sintetiche o
  mantenimento legacy motivata;
- riferimenti runtime, wrapper e documentazione da aggiornare identificati;
- nessun dato reale copiato dal data root esterno;
- nessun OCR, extraction, JSON-LD o pipeline lanciato.

Stato: chiusa.

### T15 - Migrazione prompt/rules LLM minima

Dipendenze: T14.

Collegamento MVP: supporto tecnico a Incremento MVP 1, mantenendo prompt e
contratti LLM preview-only in un repository di regole invece che nel package
installabile.

Criteri di ingresso:

- `llm_prompts/` classificato per ownership, rischio e destinazione;
- destinazione `memoria-rules/llm_prompts` confermata;
- riferimenti runtime, test e documentazione legacy identificati.

Criteri di uscita:

- prompt e schema chunk classification versionabili presenti in
  `memoria-rules/llm_prompts/chunk_classification/`;
- `memoria-engine` preferisce `../memoria-rules` per contratti LLM se deve
  leggerli da file;
- test mirati `test_llm_chunk_classifier` aggiornati e passanti;
- fallback legacy verso `memoria-engine/ricerche/llm_prompts` mantenuto solo per
  la transizione, poi rimosso in T16;
- nessun dato reale copiato dal data root esterno;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Stato: chiusa.

### T16 - Rimozione legacy llm_prompts

Dipendenze: T15.

Collegamento MVP: supporto tecnico a Incremento MVP 1.

Criteri di ingresso:

- contratti LLM presenti in `memoria-rules`;
- resolver/test preferiscono `../memoria-rules`;
- fallback legacy `memoria-engine/ricerche/llm_prompts` ancora presente.

Criteri di uscita:

- `memoria-engine/ricerche/llm_prompts` rimosso o marcato come fallback non
  operativo motivato;
- riferimenti runtime/documentali al path legacy assenti o esplicitamente
  storici;
- test mirati LLM chunk classifier passanti;
- nessun dato reale copiato dal data root esterno;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Stato: chiusa.

### T17 - Contratto stato editoriale profili/schede

Dipendenze: T13b, T16.

Collegamento MVP: supporto diretto a Incremento MVP 1, rendendo esplicito lo
stato editoriale delle schede revisionabili senza trasformarle in schede
definitive.

Criteri di ingresso:

- `memoria profiles status` disponibile e testato;
- i profili canonici nel data root esterno sono leggibili in sola lettura;
- gap confermato: i profili hanno `review_status` sui singoli `search_hints`,
  ma non campi di stato editoriale di scheda/profilo;
- nessuna modifica diretta ai 57 profili reali autorizzata in questo incremento.

Criteri di uscita:

- contratto minimo documentato per `profile_status`, `review_status` e
  `publication_status`;
- collocazione dei campi decisa e motivata, ad esempio top-level oppure
  `metadata`;
- distinzione documentata tra stato della scheda/profilo e stato dei singoli
  `search_hints`;
- valori iniziali ammessi definiti per profili seed/preview non revisionati;
- piano di migrazione controllata sul data root esterno preparato come
  incremento successivo, con dry-run e backup espliciti;
- test CLI da aggiornare o aggiungere identificati;
- nessun dato reale modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Stato: chiusa.

### T18 - Dry-run inizializzazione stato editoriale

Dipendenze: T17.

Collegamento MVP: supporto diretto a Incremento MVP 1, preparando una
inizializzazione auditabile degli stati editoriali senza scrittura immediata sui
profili canonici.

Criteri di ingresso:

- contratto T17 documentato;
- CLI `memoria profiles status` disponibile;
- data root esterno accessibile in sola lettura;
- nessuna autorizzazione alla scrittura sui 57 profili reali ancora concessa.

Criteri di uscita:

- dry-run read-only sui profili canonici completato;
- numero di profili privi dei campi editoriali riportato;
- piano di patch per i soli campi `metadata.profile_status`,
  `metadata.review_status`, `metadata.publication_status` definito;
- garanzia documentata che `search_hints`, claim e oggetti annidati non vengano
  modificati dal piano;
- strategia di backup e rollback definita per un eventuale incremento
  applicativo successivo;
- test CLI da aggiornare o aggiungere elencati;
- nessun profilo reale modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Stato: chiusa.

### T19 - Piano CLI operativa cross-platform

Dipendenze: T18.

Collegamento MVP: supporta Incremento MVP 1 senza bloccare la demo PowerShell,
preparando la portabilita' Linux e la riduzione della logica nei wrapper.

Criteri di ingresso:

- CLI Python diagnostica `memoria` disponibile e testata;
- `scripts/memoria.ps1` operativo per review, consolidate e sources;
- MVP finanziatori previsto su Windows/PowerShell per praticita';
- esigenza cross-platform Linux esplicitata.

Criteri di uscita:

- decisione documentata: CLI Python `memoria` come superficie canonica futura;
- wrapper PowerShell classificato come compat/Windows e non come destinazione
  architetturale definitiva;
- possibile wrapper Linux classificato come facciata sottile, non duplicazione
  della logica;
- lista prioritaria dei primi workflow da portare o esporre via bridge Python
  definita, ad esempio `review discover/status/start/work`;
- criteri di compatibilita' definiti: output, selezione run, file sessione e
  path data-root invariati rispetto ai workflow PowerShell;
- nessuna migrazione funzionale obbligatoria per l'MVP finanziatori;
- nessun dato reale copiato nei repository;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Stato: chiusa.

### T20 - Bridge CLI Python review read-only

Dipendenze: T19.

Collegamento MVP: supporta Incremento MVP 1 rendendo orientamento e
visualizzazione del lavoro di review accessibili dalla CLI Python canonica,
senza bloccare o sostituire i workflow PowerShell dell'MVP finanziatori.

Criteri di ingresso:

- piano T19 chiuso;
- CLI Python diagnostica `memoria` disponibile;
- workflow PowerShell `review discover/status/work` documentati e testati;
- contratti di sessione review esistenti noti:
  `database/memoria_review_session.active.json`.

Criteri di uscita:

- `memoria review discover` disponibile in sola lettura;
- `memoria review status` disponibile in sola lettura;
- `memoria review work` disponibile in sola lettura su sessione attiva
  esistente;
- nessun comando Python crea o modifica sessioni, decisioni, profili,
  `verified_facts` o artefatti canonici;
- selezione run, conteggi principali e path osservabili restano compatibili con
  il wrapper PowerShell per il primo orientamento operativo;
- test mirati CLI passano;
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Stato: chiusa.

### T21 - Bridge CLI Python consolidate read-only

Dipendenze: T20.

Collegamento MVP: supporta Incremento MVP 1 rendendo visibile lo stato degli
artefatti consolidati preview dalla CLI Python canonica, senza sostituire i
comandi PowerShell che generano preview o gestiscono sessioni operative.

Criteri di ingresso:

- T20 chiuso;
- CLI Python `memoria` espone gia' un primo bridge operativo read-only;
- workflow PowerShell `consolidate discover/status` documentati e testati;
- contratto di sessione consolidate esistente noto:
  `database/memoria_consolidate_session.active.json`.

Criteri di uscita:

- `memoria consolidate discover` disponibile in sola lettura;
- `memoria consolidate status` disponibile in sola lettura;
- nessun comando Python crea o modifica sessioni consolidate, ledger,
  `verified_facts`, store o profili JSON-LD;
- selezione run, conteggi principali e path osservabili restano compatibili con
  il wrapper PowerShell per il primo orientamento operativo;
- test mirati CLI passano;
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Stato: chiusa.

### T22 - Bridge CLI Python sources read-only

Dipendenze: T21.

Collegamento MVP: supporta Incremento MVP 1 rendendo visibile dalla CLI Python
canonica lo stato delle fonti online/offline e dei candidati di intake, senza
avviare rete, download, browser, OCR o pipeline.

Criteri di ingresso:

- T21 chiuso;
- CLI Python `memoria` espone gia' bridge operativi read-only per review e
  consolidate;
- workflow PowerShell `sources online/offline discover/status` documentati e
  testati;
- contratto di sessione sources online esistente noto:
  `database/memoria_sources_online_session.active.json`.

Criteri di uscita:

- `memoria sources online discover` disponibile in sola lettura;
- `memoria sources online status` disponibile in sola lettura;
- `memoria sources offline discover` disponibile in sola lettura;
- `memoria sources offline status` disponibile in sola lettura;
- nessun comando Python crea o modifica sessioni sources, cartelle intake,
  download, store, run, OCR, pipeline o profili JSON-LD;
- registry fonti da `memoria-sources` con fallback compatibili, indice profili
  pilota, sessione attiva e cartelle offline sono letti superficialmente con
  output compatibile per il primo orientamento operativo;
- test mirati CLI passano;
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Stato: chiusa.

### T23 - Decisione cloud workspace pluggable

Dipendenze: T22.

Collegamento MVP: supporta Incremento MVP 1 mantenendo i dati reali fuori da
Git e preparando un workspace condivisibile senza dipendere da un drive Windows
specifico.

Criteri di ingresso:

- T22 chiuso;
- draft architetturale cloud workspace disponibile;
- esigenza esplicitata di accedere a cartelle pCloud esistenti via REST prima di
  migrare o ricreare strutture;
- vincolo confermato: nessun dato reale copiato nei repository e nessuna
  chiamata cloud obbligatoria in questo incremento.

Criteri di uscita:

- decisione architetturale registrata: workspace operativo come risorsa logica
  pluggable;
- `P:\Comune\Me.Mo.Ri.a` riclassificato come backend locale compatibile;
- pCloud scelto come primo backend cloud candidato, con uso iniziale read-only
  per verificare cartelle esistenti via REST;
- sequenza tecnica successiva definita: interfaccia storage, driver local,
  manifest provider-aware, pCloud read-only, pCloud write diagnostico e cache;
- MVP PowerShell/local non bloccato dalla traiettoria cloud;
- nessun driver cloud implementato;
- nessuna chiamata reale a pCloud eseguita;
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Stato: chiusa.

### T24 - WorkspaceStorage interface e driver local

Dipendenze: T23.

Collegamento MVP: preserva il comportamento locale esistente mentre introduce il
contratto necessario per backend cloud futuri.

Criteri di ingresso:

- T23 chiuso;
- interfaccia minima definita nei documenti;
- nessuna modifica cloud richiesta.

Criteri di uscita:

- interfaccia Python `WorkspaceStorage` o equivalente disponibile;
- `LocalWorkspaceStorage` implementa `exists`, `list_dir`, `read_bytes`,
  `write_bytes` controllato, `mkdir` controllato e `stat`;
- almeno un comando diagnostico usa il driver local senza cambiare output
  osservabile;
- test unitari offline passano;
- nessun accesso cloud eseguito;
- nessun dato reale copiato nei repository.

Stato: chiusa.

### T25 - Manifest workspace provider-aware

Dipendenze: T24.

Collegamento MVP: permette di selezionare backend locale o cloud senza cambiare
codice applicativo.

Criteri di ingresso:

- T24 chiuso;
- manifest attuale descriptor-only disponibile;
- compatibilita' con `MEMORIA_DATA_ROOT` da preservare.

Criteri di uscita:

- `memoria-workspace/manifest.yml` supporta `workspace.provider`;
- provider `local` mantiene compatibilita' con il path esistente;
- provider `pcloud` puo' essere descritto senza salvare segreti;
- resolver CLI legge il nuovo formato e mantiene fallback legacy;
- test manifest/resolver passano.

Stato: chiusa.

### T26 - PCloudWorkspaceStorage read-only con mock HTTP

Dipendenze: T25.

Collegamento MVP: verifica l'accesso a cartelle cloud esistenti senza scritture
e senza migrazione dati.

Criteri di ingresso:

- T25 chiuso;
- token pCloud gestito solo tramite variabile ambiente o secret manager;
- nessun test live obbligatorio.

Criteri di uscita:

- driver pCloud read-only implementa `exists`, `list_dir`, `read_bytes` o
  download controllato, e `stat`;
- `list_dir` usa `folderid` quando disponibile e `path` solo per bootstrap;
- comando diagnostico read-only mostra `folderid`, path e contenuti sintetici
  di una cartella esistente;
- test con mock HTTP passano;
- test live opzionale disabilitato di default;
- nessuna scrittura cloud eseguita dai test standard.

Stato: chiusa il 2026-09-12 per il perimetro read-only con mock HTTP; l'accesso
live resta in hold finche' l'API pCloud non e' verificata e non viene data
autorizzazione esplicita con credenziali locali.

### T26a - Bridge CLI Python review decisions read-only

Dipendenze: T20, T25.

Collegamento MVP: supporta Incremento MVP 1 rendendo visibile dalla CLI Python
canonica lo stato delle decisioni umane review gia' registrate negli artefatti
preview, senza applicare nuove decisioni e senza dipendere dal backend cloud.

Criteri di ingresso:

- T20 chiuso;
- T26 pCloud in hold o non prioritario per la demo MVP locale;
- sessioni e summary decisioni review preview gia' prodotti dai workflow
  PowerShell o dagli artefatti di run;
- vincolo confermato: nessuna scrittura su sessioni, decisioni, profili,
  `verified_facts`, store o artefatti canonici.

Criteri di uscita:

- `memoria review decisions` disponibile in sola lettura;
- il comando legge la sessione review attiva se esiste, altrimenti usa la run
  candidata consigliata dalla discovery read-only;
- output sintetico con run, path del summary decisioni, conteggi totali,
  decisioni storiche sostanziali e distribuzioni per azione/stato/tipo soggetto;
- nessun comando Python registra decisioni o sostituisce i comandi PowerShell
  decisionali dell'MVP finanziatori;
- test mirati CLI passano;
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Stato: chiusa.

### T26b - Bridge CLI Python MVP demo status read-only

Dipendenze: T20, T21, T22, T26a.

Collegamento MVP: supporta Incremento MVP 1 componendo in una sola vista
read-only lo stato del walkthrough demo locale: profili, review, decisioni,
consolidamento e fonti.

Criteri di ingresso:

- T26a chiuso;
- T26 pCloud in hold o non prioritario per la demo MVP locale;
- bridge read-only `profiles`, `review`, `consolidate` e `sources` disponibili;
- vincolo confermato: nessuna generazione di report, run, sessioni, decisioni,
  OCR, pipeline o modifiche al data root.

Criteri di uscita:

- `memoria mvp status` disponibile in sola lettura;
- output sintetico con stato profili, run/sessione review, decisioni review,
  consolidamento, registry fonti e intake offline;
- output con walkthrough dei comandi read-only gia' disponibili per la demo;
- nessuna scrittura su sessioni, decisioni, profili, store, report o artefatti
  canonici;
- test mirati CLI passano;
- nessun dato reale copiato nei repository;
- nessun file del data root esterno modificato;
- nessun OCR, extraction, JSON-LD writer o pipeline lanciato.

Stato: chiusa.

### T27 - PCloudWorkspaceStorage write diagnostico controllato

Dipendenze: T26.

Collegamento MVP: abilita solo una scrittura sintetica e auditabile prima di
qualsiasi run reale su cloud.

Criteri di ingresso:

- T26 chiuso;
- cartella diagnostica remota autorizzata;
- policy segreti e log confermata.

Criteri di uscita:

- `write_bytes` e `mkdir` supportati per file diagnostici sintetici;
- upload usa opzioni anti-sovrascrittura quando adatte;
- comando diagnostico scrive e rilegge un file di test non sensibile;
- test mock passano;
- test live opzionale resta opt-in;
- nessun documento reale caricato.

Stato: futuro candidato.

### T28 - Cache locale e manifest provider

Dipendenze: T27.

Collegamento MVP: riduce costo e fragilita' operativa dei backend cloud prima di
run o elaborazioni documentali.

Criteri di ingresso:

- T27 chiuso;
- contratto metadata remoto definito per pCloud.

Criteri di uscita:

- cache locale `.memoria-cache/` fuori dai repository Git o ignorata;
- manifest cache contiene provider, path logico, id remoto, size, hash o
  timestamp/revision disponibili;
- download ripetuti evitati quando il remoto non cambia;
- modalita' read-only supportata;
- test offline e mock passano.

Stato: futuro candidato.

## Corsia prioritaria F - Funding demo golden path

Questa corsia prevale sugli incrementi cloud T26-T28 e sui micro-refactor Q2
finche' T33 non e' chiuso. Cloud e qualita' possono avanzare solo se richiesti
esplicitamente o se rimuovono un blocco diretto della golden run.

Documento di riferimento:

```text
memoria-bootstrap/docs/funding-demo-golden-path.md
```

### T29 - Contratto Funding Demo Golden Path

Dipendenze: T26b.

Collegamento MVP: Incremento MVP 2 - Contratto golden path.

Criteri di ingresso:

- bridge read-only `memoria mvp status` disponibile;
- capacita' preview di review, consolidamento e fonti gia' osservabili;
- materiali e run esistenti disponibili nel data root esterno;
- gap confermati: run frammentate, merge multi-fonte poco evidente e feedback
  loop non ancora chiuso.

Criteri di uscita:

- caso principale e, se utile, caso di contrasto selezionati;
- 2-4 documenti candidati identificati senza copiarli nei repository;
- almeno due fonti/famiglie documentali differenti selezionate;
- criteri di riconciliazione multi-fonte definiti;
- contratto minimo del descrittore golden run definito;
- artifact map e walkthrough di 7-10 minuti definiti;
- feedback trigger candidato identificato;
- gap tecnici puntuali per T30-T32 elencati;
- nessuna pipeline, OCR, rete o modifica ai dati reali eseguita.

Stato: chiusa.

Evidenza: `memoria-bootstrap/docs/funding-demo-t29-contract.md`.

### T30 - Golden run multi-fonte canonica

Dipendenze: T29.

Collegamento MVP: Incremento MVP 3 - Golden run multi-fonte.

Criteri di ingresso:

- contratto T29 approvato;
- profilo e documenti demo selezionati;
- comandi e pipeline esistenti necessari identificati;
- strategia di backup e isolamento della run definita.

Criteri di uscita:

- una sola run canonica contiene o collega in modo auditabile tutti gli
  artefatti della demo;
- descrittore golden run presente nel data root esterno;
- almeno due fonti differenti contribuiscono alla stessa scheda/profilo;
- tabella di riconciliazione mostra claim, fonte, compatibilita' o conflitto;
- review queue ridotta al perimetro demo;
- almeno una decisione sostanziale, un verified fact preview e una profile patch
  preview sono collegati alla stessa catena di provenance;
- report e CLI identificano senza ambiguita' il `run_id` canonico;
- eventuali sidecar di riallineamento manuale/preview, incluso
  `--output-aligned-ledger`, sono marcati come ponte temporaneo T30 e non come
  flusso ordinario di arricchimento schede;
- nessuna patch applicata ai profili canonici;
- test mirati e prova read-only della run passano.

Stato: chiusa.

Evidenza: descrittore attivo
`P:\Comune\Me.Mo.Ri.a\database\memoria_mvp_demo.active.json`, ledger preview
T30 `mvp_consolidated_review_ledger.t30-preview.json` e tabella
`mvp_demo_reconciliation_table.md` sulla run
`prova-preview-profili-5-reviewed-01-pipeline`. Verifica read-only del
2026-07-14: `memoria mvp demo` conferma `ready_for_internal_demo`; il dry-run
`memoria mvp demo-build --ledger <sidecar T30>` conferma 3 famiglie coperte,
4/4 documenti coperti, 22 righe di riconciliazione, 10 decisioni sostanziali,
8 verified facts preview e 2 ProfilePatch preview. Il sidecar T30 resta ponte
temporaneo preview-only: T32 deve rigenerare lo stesso risultato dal flusso
standard.

### T31 - Feedback loop storico chiuso

Dipendenze: T30.

Collegamento MVP: Incremento MVP 4 - Feedback loop dimostrato.

Criteri di ingresso:

- golden run T30 disponibile;
- almeno una lacuna, incertezza o contraddizione selezionabile;
- workflow feedback e planner fonte-specifico esistenti identificati;
- perimetro della ricerca controllata definito.

Criteri di uscita:

- una decisione dello storico richiede ulteriori fonti o verifica;
- una `ResearchFeedbackAction` o equivalente e' approvata per la demo;
- query e strategia fonte-specifica sono registrate;
- ricerca controllata eseguita oppure sessione manuale tracciata;
- esito registrato come nuovo documento/claim candidato oppure `no_results`,
  `needs_manual_review` o `blocked_or_dynamic` motivato;
- profilo o piano di ricerca preview conserva il collegamento all'esito;
- nessun nuovo claim promosso senza review;
- walkthrough aggiornato per mostrare il ciclo completo.

Stato: chiusa.

Evidenza parziale del 2026-07-15: aggiunto e testato in `memoria-engine` il
builder preview-only `feedback_loop_outcome` per registrare l'esito auditabile
del loop T31 e la `search_memory_update_preview` senza scrivere profili,
promuovere claim o creare verified facts. Questa evidenza ha preparato la
chiusura operativa: mancavano ancora approvazione demo ed esito persistito nel
data root autorizzato della golden run.

Evidenza di chiusura del 2026-07-15: il descrittore attivo
`P:\Comune\Me.Mo.Ri.a\database\memoria_mvp_demo.active.json` punta agli
artefatti T31; `feedback_loop_outcome.t31-demo.json` registra
`closed_with_auditable_outcome` con outcome `needs_manual_review`, azione
`research-feedback-action:7bdbb2060d955baa`, piano
`feedback-search-plan:a19b13e6e3cd8b0d`, profilo Andreoli e
`search_memory_update_preview`. Le safety flag restano preview-only:
nessun claim promosso, nessuna patch applicata e nessun profilo canonico
modificato.

### T32 - Hardening e prova generale demo

Dipendenze: T31.

Collegamento MVP: Incremento MVP 5 - Hardening della demo.

Criteri di ingresso:

- golden run e feedback loop disponibili;
- lista di incoerenze CLI, test, naming e guide prodotta da T29-T31;
- walkthrough completo eseguibile almeno manualmente.

Criteri di uscita:

- `memoria mvp status` identifica correttamente la golden run e i conteggi;
- il risultato ottenuto in T30 tramite sidecar `--output-aligned-ledger` e'
  rigenerato dal flusso standard di arricchimento
  `documenti/CSV/DOCX -> person linking -> candidate_evidence_claims ->
  evidence store -> consolidated ledger`; T32 non puo' avanzare se la demo
  dipende ancora dal sidecar come fonte primaria dei claim T30;
- `--output-aligned-ledger` e gli artefatti derivati restano documentati come
  variazione temporanea preview-only, non come percorso canonico di produzione
  della golden run;
- test path/cross-platform che incidono sulla demo corretti o motivati;
- CLI Python, wrapper PowerShell e guide usano la stessa run selection;
- playbook e roadmap non contengono riferimenti operativi obsoleti;
- naming e sezioni non suggeriscono pubblicabilita' di output non approvati;
- verifica che il pacchetto repository distribuibile non contenga dati reali;
- prova generale di 7-10 minuti completata con checklist;
- nessuna dipendenza da rete live non controllata per il percorso principale.

Stato: chiusa.

Evidenza: `memoria mvp demo` conferma `ready_for_internal_demo` sulla run
`prova-preview-profili-5-reviewed-01-pipeline`, con ledger standard
`mvp_consolidated_review_ledger.json`, 3 famiglie fonte coperte, 4/4 documenti
coperti e safety flag preview-only. Il walkthrough asciutto, il trattamento
sidecar e l'esclusione dei residui operativi legacy dagli archivi distribuibili
sono documentati in:
`memoria-bootstrap/docs/funding-demo-t32-walkthrough-dry-run.md`,
`memoria-bootstrap/docs/funding-demo-t32-sidecar-treatment.md` e
`memoria-bootstrap/docs/funding-demo-t32-distribution-risk.md`.

### T33 - Pacchetto finanziatori

Dipendenze: T32.

Collegamento MVP: Incremento MVP 6 - Pacchetto finanziatori.

Criteri di ingresso:

- golden run pronta per demo interna;
- walkthrough provato;
- limiti e stato preview documentati;
- artefatti principali stabilizzati.

Criteri di uscita:

- una sola golden run canonica con tre casi selezionati, promossa soltanto dopo
  review e validazione della candidata;
- dossier finanziatori breve collegato alla golden run;
- script del walkthrough e comandi di fallback disponibili;
- diagramma del percorso fonti-documenti-evidenze-review-feedback;
- scheda del caso demo con provenance leggibile;
- roadmap dell'uso dei fondi e risultati attesi;
- distinzione esplicita fra capacita' attuali, sviluppo finanziato e visione;
- checklist di readiness approvata per presentazione esterna;
- nessuna affermazione storica non supportata o output preview presentato come
  pubblicabile.

Vincolo di transizione T33: la run precedente resta l'unica attiva mentre si
prepara la candidata. Non e' ammessa una run comparativa usata in parallelo
dalla presentazione; descriptor, dossier, walkthrough e feedback loop devono
convergere sulla candidata prima della promozione.

Stato: **chiuso il 2026-08-29**. La golden run, il pacchetto revisionabile,
la revisione umana del racconto e il layout interno non pubblicabile risultano
completati; non e' autorizzata la pubblicazione o la modifica canonica.

### T34 - Migrazione controllata dei profili legacy

Dipendenze: T33, T17 e T18.

Collegamento MVP: sviluppo della base profili operativi senza perpetuare il
seed storico `caduti_purocielo.csv`.

Priorità: completata il 2026-09-02. T26-T28 cloud restano in hold; Q2 può
proseguire con micro-refactor behavior-preserving.

Criteri di ingresso:

- la lavorazione operativa è organizzata in lotti massimi di 20 profili; ogni
  profilo mantiene candidati, decisioni, backup e audit distinti;

- i 57 profili indicizzati sono censiti e risultano ancora marcati con
  `seed.source = ricerche\\caduti_purocielo.csv`;
- esiste un inventario dei documenti e delle fonti strutturate disponibili per
  ciascun profilo;
- il contratto editoriale `metadata.profile_status`,
  `metadata.review_status` e `metadata.publication_status` resta applicabile;
- il perimetro di scrittura, backup e rollback è definito prima di ogni run.

Fasi obbligatorie:

1. audit read-only dei profili legacy e della copertura documentale;
2. intake locale dei documenti, con hash, sidecar e provenance;
3. generazione di `CandidateProfileUpdate` e `CandidateNewProfile` preview-only;
4. revisione umana dei candidati e delle evidenze, senza promozione automatica;
5. produzione della mappa auditabile profilo legacy → profilo ricostruito;
6. dry-run della migrazione con backup verificato e piano di rollback;
7. applicazione canonica solo per il lotto esplicitamente approvato, con audit
   e verifica post-migrazione.

Criteri di uscita:

- ogni profilo migrato ha provenance verso documenti e fonti strutturate;
- ogni sostituzione è collegata a decisioni di revisione e a un audit;
- backup, manifest, mappa vecchio→nuovo e rollback sono verificati;
- i profili senza copertura sufficiente restano invariati e sono elencati come
  residui legacy;
- nessun claim non revisionato diventa `verified_fact`;
- nessuna migrazione in-place o cancellazione del seed storico senza approvazione
  esplicita e tracciata.

Stato: chiusa il 2026-09-02. La migrazione controllata dei profili legacy è
completata; le evidenze operative restano nel data root esterno.

Chiusura operativa 2026-09-02: T34 non lascia un preflight pendente nella fase
di intake/revisione preview. La riconciliazione finale dei residui e
l'eventuale applicazione canonica autorizzata sono ora tracciate separatamente
in T34b.

Aggiornamento operativo 2026-08-31: la revisione T34 e' chiusa in preview-only;
profili canonici invariati. L'applicazione resta un incremento separato.

Aggiornamento operativo 2026-08-30: il lotto T34-2 di 20 profili e' stato
interrogato tramite la CLI del connettore `storia_memoria_bo`. La ricerca ha
prodotto 16 esiti `ok` e 4 `no_results`, ma nessun documento dettagliato
acquisito (`SourceDocument=0`). I 16 esiti restano quindi candidati di ricerca
ambigui e non possono alimentare `CandidateProfileUpdate` senza disambiguazione
e documento identificabile. Nessun profilo canonico e' stato modificato. Il
prossimo gate e' la revisione dei report e l'associazione documentale; i quattro
`no_results` restano residui legacy.

### T34b - Chiusura operativa della migrazione profili legacy

Dipendenze: T34, T17 e T18.

Priorità operativa corrente: T34b precede il post-MVP, Q2 e qualsiasi riapertura
della traiettoria cloud. T34 resta chiusa per intake, generazione candidati e
revisione preview; T34b chiude invece il residuo operativo senza confondere
preview e modifica canonica.

Obiettivo: riconciliare lo stato effettivo dei candidati T34, completare la
revisione umana dei casi ancora pending, preparare il dry-run auditabile e
applicare esclusivamente le operazioni esplicitamente approvate.

Perimetro obbligatorio:

1. riconciliare conteggi, provenance e stato dei `CandidateProfileUpdate` e
   `CandidateNewProfile` tra worklist e run esterne;
2. chiudere, rifiutare o lasciare esplicitamente pending ogni candidato con
   nota motivata e residuo legacy identificato;
3. verificare backup, manifest, mappa legacy → profilo ricostruito, dry-run e
   piano di rollback;
4. applicare solo il lotto autorizzato esplicitamente, con audit post-run;
5. verificare che nessun claim non revisionato diventi `verified_fact` e che i
   profili senza copertura sufficiente restino invariati.

Criteri di uscita:

- i conteggi della coda T34 sono coerenti e riconciliati con gli artefatti
  esterni;
- ogni decisione sostanziale ha provenance, revisore e stato esplicito;
- il dry-run, il backup, il rollback e l'audit post-run sono verificati;
- eventuali `ProfilePatch` applicate corrispondono soltanto ad autorizzazioni
  esplicite e sono tracciate;
- i residui legacy e i casi pending sono elencati senza promozione automatica;
- T34b è chiusa prima di selezionare il primo incremento post-MVP.

Stato: priorità selezionata il 2026-09-10. I gate read-only di riconciliazione
e inventario sono stati eseguiti il 2026-09-10: la coda contiene 51 elementi,
44 hanno una decisione univoca dopo l'esclusione del set `block5d` invalidato,
e i 7 residui hanno ora 4 `accepted` e 3 `rejected`. La revisione umana dei
`CandidateNewProfile` e' completa e T34b e' chiusa operativamente: dry-run,
backup, applicazione autorizzata, rollback condizionato e audit post-run sono
verificati. Nessun claim o `verified_fact` e' stato promosso.

Aggiornamento Gate 6 del 2026-09-11: il contratto
`CandidateNewProfileMaterializationPlan` e' implementato in preview-only con
provenance, hash, manifest, rollback metadata e audit. L'integrazione con gli
artefatti reali e il dry-run operativo restano un incremento separato.

Aggiornamento Gate 8 del 2026-09-11: il piano aggregato e il report dry-run
T34b sono stati scritti nella run esterna in preview-only. Quattro piani sono
verificati con zero scritture canoniche; l'applicazione resta subordinata a
backup, rollback, audit post-run e autorizzazione esplicita.

Aggiornamento Gate 9 del 2026-09-11: applicazione canonica T34b completata con
3 profili nuovi, 1 collegamento esistente, indice 57 -> 60, backup e audit
verificati. T34b e' chiusa; il prossimo incremento torna alla roadmap del
prodotto completo.

## Post-MVP - Intake immagini, OCR strutturato e collegamento ai profili

Obiettivo: consentire di portare un insieme di immagini dalla cartella di
ingresso a trascrizioni revisionabili e candidati collegabili ai profili usando
la CLI Python `memoria`, senza richiedere editing diretto di JSON o wrapper
PowerShell come interfaccia operativa. È una sequenza candidata da selezionare
in micro-incrementi: non implica che tutte le capacità siano già disponibili.

### Requisiti del flusso CLI

1. Discovery e intake: individuare i file supportati in un percorso esplicito,
   mostrare un preflight/preview prima dell'elaborazione e registrare identità
   stabile del documento, hash, percorso relativo e stato. L'originale resta
   immutato; ripetere l'operazione non deve duplicare documenti né sovrascrivere
   silenziosamente risultati precedenti.
2. OCR e risultati: invocare il processamento per lotto dalla CLI e produrre
   artefatti ispezionabili per documento e run. Conservare testo, pagina,
   lingua/configurazione e motore, confidence disponibile, errori e riferimenti
   alle regioni; riportare esplicitamente pagine o porzioni non lette e incerte.
3. Trascrizione Markdown per pagina: produrre un file Markdown per ogni immagine
   o pagina, non soltanto OCR o testo estratto, ricostruendo in forma
   semplificata e verificabile la gerarchia e il layout: pagina, blocchi, titoli,
   paragrafi, colonne e ordine di lettura, liste, didascalie e tabelle quando
   rilevabili. Ogni elemento deve poter rinviare alla regione dell'immagine
   originale (coordinate o identificatore stabile). Distinguere chiaramente
   testo trascritto da struttura inferita; marcare ordine/strutture incerte e
   passaggi da revisionare. Non inventare testo illeggibile: usare un marcatore
   esplicito di illeggibilità/incertezza senza completamenti congetturali.
   Coordinate e confidence, se disponibili, devono restare riconducibili
   all'immagine originale.
4. Tabelle e layout misti: rilevare aree tabellari e, quando supportato,
   ricostruire righe/celle mantenendo ordine, pagina, coordinate e stato di
   verifica. Celle ambigue o mancanti vanno segnalate, non completate per
   supposizione. Criteri di qualità e soglie saranno definiti con fixture
   rappresentative prima di scegliere o fissare un'implementazione.
5. Valutazione comparativa di pipeline e modelli: confrontare approcci OCR e
   rilevamento layout (inclusi pipeline modulari/deterministiche) con LLM locali,
   anche multimodali, come opzioni e non come decisione di stack. Valutare
   fedeltà della gerarchia e del layout/ordine di lettura, copertura delle
   regioni, ricostruzione di tabelle, qualità della trascrizione, costo e
   risorse necessarie, nonché il carico e la necessità di revisione umana.
   Nessun modello o stack viene scelto in questa fase. Un'eventuale opzione
   locale deve funzionare offline, rispettare la privacy, e conservare identità
   e versione del modello, configurazione, provenance degli input/output e
   informazioni sufficienti a riprodurre l'elaborazione.
6. Diagrammi e cartine: trattarli come una classe separata. La ricostruzione
   della pagina descrive blocchi, posizioni e testo visibile, ma non equivale
   all'interpretazione di mappe né alla semantica dei simboli. Il testo OCR di
   etichette e legenda è un indizio, non una lettura semantica della mappa.
   Diagrammi semplici possono conservare testo, didascalie e regioni; relazioni
   grafiche non sono fatti finché non sono verificate. Georeferenziazione,
   controllo punti e interpretazione geografica sono capacità distinte, non
   implicate dall'OCR.
7. Collegamento ai profili: inviare documenti processati alla pipeline offline
   esistente o alla sua evoluzione CLI per generare candidati di associazione e
   claim. Ogni candidato deve rinviare a documento sorgente, hash, pagina e
   regione quando disponibili. CLI di ispezione/review separa proposta, evidenza
   e decisione umana; eventuali patch restano preview-only fino ad audit e
   autorizzazione esplicita. Nessuna modifica canonica automatica.

### Criteri di accettazione trasversali

- il workflow completo si avvia e si ispeziona con CLI Python installabile;
- test offline con fixture che includano almeno scansione multi-colonna,
  header/footer, tabella, layout misto e testo degradato; verificare per ciascuna
  la copertura delle regioni, la gerarchia/ordine ricostruiti e la corrispondente
  fixture Markdown attesa, inclusi marcatori per inferenze e testo illeggibile;
- confrontare su tali fixture le alternative OCR/layout e le eventuali opzioni
  LLM locali per fedeltà del layout, copertura delle regioni, tabelle,
  qualità/costo/risorse e necessità di revisione umana, senza richiedere un
  benchmark o una selezione di modello in questa fase;
- risultati ripetibili e idempotenti, con errori per file isolati e riepilogo
  per lotto;
- trascrizione, regioni e candidati sono riconducibili all'originale e le
  incertezze non scompaiono nel passaggio Markdown;
- nessuna acquisizione massiva non richiesta, promozione automatica di fatti o
  scrittura di profili canonici.

La ricostruzione Markdown riguarda la struttura visibile della pagina e il suo
ordine di lettura, non l'interpretazione semantica di mappe o simboli. Un testo
degradato o non leggibile resta esplicitamente tale e richiede revisione umana;
non viene ricostruito per supposizione.

### Stato e limiti osservati

Il runner OCR locale attuale usa Tesseract per estrarre testo e diagnostica di
qualità/layout; il testo viene normalizzato e non costituisce una ricostruzione
semantica di tabelle o cartine. Produce artefatti strutturati per il
processamento e report Markdown operativi, ma questi report non sono una
trascrizione Markdown strutturata pagina/regioni. Il catalogo cartografico può
segnalare mappe candidate, ma non interpreta la mappa né la georeferenzia.
Questi limiti sono il punto di partenza per selezionare i successivi
micro-incrementi, non una promessa di accuratezza OCR universale.

Stato: requisiti consolidati il 2026-09-17. Primo passo completato: la CLI
`memoria documents register` offre discovery ricorsiva in preview read-only e
crea sidecar solo con `--apply`, saltando quelli esistenti. Il comando registra
documenti per il successivo processamento ma non avvia OCR; gli altri requisiti
restano da implementare per micro-incrementi.

Passo successivo completato: `memoria documents process` mostra in preview
read-only i candidati OCR e delega al runner batch locale soltanto con
`--apply`. Trascrizione Markdown strutturata, layout e valutazione comparativa
restano da implementare e verificare con fixture dedicate.

Incremento `ocr-line-layout-evidence-v1` in quality gate: il payload OCR
Tesseract conserva righe TSV con identificatori stabili di documento, pagina e
regione, testo, bounding box, confidence media e stato `unreviewed`. L'ordine
derivato dal sorting geometrico top/left è una proposta inferita e riporta la
sua base, senza rappresentare struttura semantica. Le righe restano distinte dai
candidati di nota o riferimento, che rinviano a documento, riga e regione di
origine. In assenza di TSV il formato resta compatibile con una lista di righe
vuota. Nessuna ricostruzione Markdown o inferenza di layout semantico è stata
introdotta.

Incremento `ocr-page-markdown-export-v1` completato: la CLI esporta in preview
read-only, o con `--apply` esplicito, un Markdown per pagina dalle righe OCR
gia' tracciate. Il file conserva provenance, coordinate, confidence, review e
ordine inferito; il testo OCR non fidato e' recintato come letterale. Non sono
state introdotte inferenze di titoli, colonne, tabelle, claim o profili.

Incremento `ocr-quality-gated-retry-v1` completato: prima della registrazione il
runner valuta congiuntamente testo e TSV. Se il risultato e' insufficiente prova
un PSM alternativo e, soltanto allora, una derivata temporanea preprocessata con
il PSM migliore; i tentativi sono al massimo tre e la sintesi resta nel payload
scelto. Nessun JSON OCR viene creato o sovrascritto se nessun candidato supera
il gate; l'export Markdown salta documenti rifiutati e righe senza caratteri
alfanumerici. Le soglie del pilot sono provvisorie: almeno 2 token alfanumerici,
una riga TSV alfanumerica, confidence media >= 35 e non oltre il 75% di token a
confidence bassa. Servono fixture di scansioni reali rappresentative per
calibrarle prima di trattarle come criteri archivistici stabili.
Il gate riguarda esclusivamente il JSON `ProcessedDocumentText`: i file
`*.metadata.json` separati conservano metadati indipendenti e non sono trattati
come output OCR vuoti.

### Valutazione dedicata Qwen locale per OCR

Attivita' candidata, non selezione di stack: valutare Qwen3-VL 8B in esecuzione
locale e le varianti `instruct`/`thinking` effettivamente disponibili. Il pilot
del 2026-09-17 con `qwen3-vl:8b` ha lasciato vuota la risposta finale dopo aver
esaurito il budget nei token di thinking. L'immagine intera ad alta risoluzione
ha saturato il context da 4096 token; anche il crop ridotto con context piu'
ampio ha consumato il budget in thinking senza una trascrizione finale completa.
Questi esiti motivano una valutazione mirata, ma non determinano il modello o
lo stack da adottare.

La valutazione dovra' usare fixture offline con trascrizione di riferimento,
includendo testo degradato e pagine con tabella/layout misto. Le quattro lingue
minime supportate e verificate sono italiano (`ita`), tedesco (`deu`), inglese
(`eng`) e russo (`rus`); il russo richiede copertura esplicita dell'alfabeto
cirillico. Confrontare Tesseract aggiornato e i suoi language pack, PP-OCRv5,
e modelli vision locali disponibili (fra cui Qwen3-VL e GLM-OCR quando
installabili) sugli stessi input e ground truth. Provare prompt di
trascrizione letterale nella lingua sorgente (senza traduzioni o completamenti),
limiti `context`/`num_predict`, modalita' thinking, dimensionamento delle
immagini, crop e tiling. Misurare accuratezza e copertura del testo,
completezza, non-invenzione, fedelta' della struttura e del layout, oltre a
latenza e risorse CPU/GPU. Conservare provenance riproducibile: tag e digest
del modello, versione/runtime e configurazione, hash del prompt e trasformazioni/
crop applicati. I risultati vanno disaggregati per lingua e difficolta'; un
buon punteggio aggregato non deve nascondere il fallimento su una lingua. La
scelta resta aperta fino al confronto riproducibile e alla revisione dei
risultati.

Prova appaiata Qwen/Tesseract completata il 2026-09-18 sui file in
`P:\Comune\Me.Mo.Ri.a\documenti_da_processare\foto\T314 R1275\test`, in sola
lettura e senza registrare `ProcessedDocumentText`. Qwen3-VL 8B e 4B hanno
restituito output vuoto sulle fixture sintetiche e sui due TIFF; Tesseract con
lingue `ita` e `deu` ha prodotto testo sui TIFF, ancora rumoroso. Non essendoci
ground truth umana validata, non sono state calcolate né dichiarate accuratezza.
Il confronto 4B/8B ha usato gli stessi originali, ma gli hash dei PNG inviati
sono diversi e l'identità pixel-level non è stata verificata; non si assume
quindi che i due modelli abbiano ricevuto input pixel-identici. Nessun risultato
costituisce un claim storico o seleziona uno stack OCR.

Calibrazione multimodale locale del 2026-09-19, solo su fixture sintetiche con
ground truth: Ollama 0.33.2 espone `llava-llama3:latest` (digest
`44c161b1f46523301da9c0cc505afa4a4a0cc62f580581d98a430bb21acd46de`). Il tag
`qwen3-vl` non e' installato; `llama3.2-vision:latest` e' presente ma Ollama
rifiuta l'esecuzione per incompatibilita' e propone di riscaricarlo, operazione
non effettuata. Il benchmark conserva prompt esatto/hash, temperatura,
`num_ctx`, `num_predict`, `think`, digest del modello e hash SHA-256 di ogni
risposta, senza salvare le trascrizioni.

Sul manifest `synthetic-ocr-foundation-v1` (SHA-256
`8a48595d3a1e9d2abc09e2dc2e4cf0b314cd67f26ddad0e015e46f6191f05c28`), con
`num_predict=256` e `think=false`, il baseline LLaVA con prompt italiano hash
`04f17ecf2f4bad0f35e24eb34cd74593967434c4e86a7114c33ded07fad85dab`,
`temperature=0` e `num_ctx=4096` ha ottenuto accuratezza testuale aggregata
0.686 e tasso di aggiunte 0.273. Ripetendo la configurazione, gli hash delle
risposte sono rimasti identici per tutte le tre immagini: clean
`303f21ef6cb5cb4dc7999bffa5492e17721affee8450f7538bfe00c5e82b24a3`,
degraded `616658743aa337537e4e64aa81b07e168fca1f1e9c87eb1e219ec894e785e74b`,
mixed `602efe9e1584ecf044965e850e1ded8d26ec8c4b996ec8c51b733e361df438a8`.
Portare solo `num_ctx` a 8192 non ha cambiato hash o metriche. Un prompt
italiano che richiede `[illeggibile]` (hash
`8e08180699e69b9e2f0604a3c7526c3c574e3cfc36de3ff1693c7214ed7a38fd`) con
temperatura 0 ha portato l'accuratezza aggregata a 0.714 e le aggiunte a 0.242,
ma il fixture misto resta a 0.50. Il prompt inglese ha peggiorato il risultato
(0.622 di accuratezza; 0.378 di aggiunte). Temperatura 0.2 non ha migliorato
l'aggregato e ripetendo gli stessi parametri ha prodotto hash diversi: la
temperatura zero e' necessaria per la ripetibilita' osservata, non sufficiente
per accuratezza.

Valutazione LLaVA con prompt selezionato per lingua, completata il
2026-09-19 sulle sei fixture sintetiche: Ollama 0.33.2, modello
`llava-llama3:latest` (digest
`44c161b1f46523301da9c0cc505afa4a4a0cc62f580581d98a430bb21acd46de`), engine
`ollama-vision` su localhost, timeout 120 s, `num_ctx=4096`,
`num_predict=256`, `think=false`, `temperature=0`. Su 66 token di riferimento
ha prodotto 193 token con 38 match: accuratezza 0.196891, copertura 0.575758,
invenzione 0.803109. Metriche per lingua accuracy/coverage/invention:
`ita` 0.657143/0.657143/0.281250 (3 fixture), `deu` 0.363636/0.400000/0.636364,
`eng` 1/1/0 e `rus` 0/0/1 (una fixture ciascuna per le ultime tre lingue).
SHA-256 prompt/risposta e latenza ms per fixture: clean-text
`1f1134efd78479978bbeba3f98a44e04c858d4266c0e14fd841ef4aa9cf16181` /
`1d3ecf83612720e6ef0308c97158bab23a3d4c9983e3098d85e2661f66bf711c` /
23859.808; degraded-text stesso prompt /
`88e05129b8d7c74f0d31f7cf6d04911159d45c32eb400ce6f1ed9246869b5dab` /
12609.975; mixed-table-layout stesso prompt /
`602efe9e1584ecf044965e850e1ded8d26ec8c4b996ec8c51b733e361df438a8` /
11742.573; german-text
`edf845ecb8bde0fb2d047fed411bd95e8853660e118b49a55927adb238f24f83` /
`84e697e4f17ee1c50bbecd736b653ab90382c3387d3edcf22cbd55eece69015b` /
12495.317; english-text
`3aa64c709d67eeef5348b745cb0322312e571a72c7cdba1e0f6189663750524d` /
`bda71f65e5161ca833b61769cb5b64a1f1a86b0d52a2bd1da65a8c698468154e` /
10771.983; russian-text
`f4b0b472bd127b6dca36e552f6fe5461b713c04cb1a1fa1bd4159412165ee27b` /
`ce03d538e7014940483b7ea830f6e08fb047c64ce5041f259150fb91e35eede4` /
55281.920. Code review PASS; nessun test aggiunto o eseguito. Paddle/PaddleOCR
non sono installati; LLaMA 3.2 Vision è installato ma incompatibile con
l'attuale Ollama e non è stato eseguito; Qwen3-VL non è disponibile. Il risultato
non selezionava ancora alcun engine; al 2026-09-19 il prossimo candidato era l'integrazione PP-OCRv5
e dei modelli vision disponibili. Solo fixture sintetiche, nessun claim.

Sul medesimo manifest Tesseract 5.5.0.20241111, lingua `ita`, OEM 1 e PSM 6 ha
ottenuto accuratezza aggregata 0.686: clean 1.00, degraded 0.75 e mixed 0.357.
Il piccolo corpus non dimostra accuratezza su scansioni storiche e non supporta
la selezione di un modello. Tesseract e il suo quality gate costituiscono il
baseline/riferimento corrente del benchmark, in attesa di un confronto
riproducibile e della revisione umana. Questa era la conclusione della fase
esplorativa al 2026-09-19; la decisione del 2026-09-20 riportata piu' sotto
seleziona PP-OCRv5 come recognizer primario del prossimo pilot. Il modello vision
resta una lettura indipendente e nessun engine corregge automaticamente la
trascrizione di un altro.

Sequenza di valutazione: (1) estendere le fixture sintetiche controllate a
italiano, tedesco, inglese e russo e misurare le lingue separatamente -
completato; (2) aggiornare Tesseract e confrontare configurazioni e language
pack - completato con Tesseract 5.5.3.20260724, OEM 1/PSM 6, sulle sei fixture
sintetiche: accuratezza `ita` 0.714286 (3 fixture; baseline 5.5.0 0.685714),
`deu`/`eng`/`rus` 1.0 (una fixture pulita ciascuno), totale 0.848485 su 66
token di riferimento; (3) adapter PP-OCRv5 opt-in/lazy e benchmark runtime
completati sulle stesse sei fixture sintetiche: PaddleOCR 3.7.0, PaddlePaddle
CPU 3.3.0, modelli PP-OCRv5 mobile e `enable_mkldnn=false`. Risultato aggregato
su 66 token di riferimento: 67 output, 65 match, 1 omissione e 2 aggiunte;
accuratezza 0.970149, copertura 0.984848, completezza 1.0 e invenzione
0.029851. Per lingua accuracy/coverage/invention: `ita` 0.944444/0.971429/
0.055556 (35 riferimenti, 36 output, 34 match), `deu` 1/1/0 (10/10/10),
`eng` 1/1/0 (11/11/11), `rus` 1/1/0 (10/10/10). Cinque fixture perfette;
la fixture italiana degradata: accuratezza 0.833333, copertura 0.909091,
invenzione 0.166667. Latenza 1.469-3.959 s per fixture. La ripetizione con
filtraggio dei file `.cache` ha confermato i sei hash di risposta. SHA-256 del
manifest `08a51b197d34400fdc40943ddfa7a681a4a12d4004bc2f348a38ce8346cbf436`;
pesi detector `afa1820cb16c1fd0dad589d0f8b389139061c1ef6d68019685fd07be997dda5b`,
Latin `53cdc8b481a7394bb108f96d0fb3432b0a8f392e22c7d18f06dbb2d42b8b25f9`,
English `3ec8a97ed6cefe8568d3e2ee90bb193299b566a7661aa4fd52d224b96b59f66b`,
East Slavic `f11057b05d8517868bca505271278973d706600d9dcc184cbcf5c4512091c32b`.
La provenance verifica localmente i file attesi e gli hash, non certifica una
firma ufficiale. Il corpus e' sintetico e text-only: non valuta struttura o
layout, non supporta claim su scansioni storiche e non seleziona/promuove uno
stack. (4) prossimo: validare un campione limitato di scansioni rappresentative
con trascrizione umana verificata, mantenendo distinti gli output dei motori.
Riferimenti: [OCR pipeline](https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html)
e [modelli PP-OCRv5 multilingue](https://www.paddleocr.ai/latest/en/version3.x/algorithm/PP-OCRv5/PP-OCRv5_multi_languages.html).
Installer ufficiale Tesseract 5.5.3.20260724:
https://github.com/tesseract-ocr/tesseract/releases/download/5.5.3/tesseract-ocr-w64-setup-5.5.3.20260724.exe,
SHA-256 `BEE9E3434BD94FD65387D9BE28CD467A41F61B1275383B55B0F59A1331270AE4`
(coincide con il manifest ScoopInstaller/Main); certificato Authenticode
scaduto/non verificabile. Modelli `deu`/`rus` da
https://github.com/tesseract-ocr/tessdata_fast (raw `main`), SHA-256
`19D219BBB6672C869D20A9636C6816A81EB9A71796CB93EBE0CB1530E2CDB22D` e
`E16E5E036CCE1D9EC2B00063CF8B54472625B9E14D893A169E2B0DEDEB4DF225`;
staging temporaneo in Temp e `TESSDATA_PREFIX` per la prova. Risultati solo
sintetici: nessuna scansione reale, approvazione di claim o selezione di stack.
Nota storica 2026-09-19: la scelta dello stack era mantenuta aperta fino alla
revisione del confronto. La decisione 2026-09-20 piu' sotto chiude questa fase
esplorativa senza autorizzare correzioni o sovrascritture automatiche fra engine.

Per rendere confrontabili gli input immagine, registrare anche la pipeline
esatta di decode e trasformazione (formato, algoritmo e dimensioni del resize),
l'hash dei byte effettivamente inviati al modello e, quando si dichiara identità
pixel-level tra modelli, un hash canonico dei pixel decodificati o una verifica
equivalente. Un hash PNG diverso non dimostra da solo che i pixel siano diversi;
stessa sorgente e stesse dimensioni non dimostrano da sole che il payload sia
identico. Un output vuoto o a zero token va riportato come nessuna trascrizione,
non come copertura utile. L'accuratezza su immagini reali si valuta solo con
ground truth umana validata.

Confronto offline delle pipeline (candidati, non selezionati):

1. OCR con testo grezzo, token/regione, bounding box e confidence; aggiungere
   analisi layout e struttura tabellare, con un eventuale LLM solo per
   formattazione o proposte di correzione.
2. Conversione documentale diretta da immagine/pagina con un VLM.
3. Pipeline end-to-end di parsing documentale come PaddleOCR PP-StructureV3 o
   Docling. Sono alternative da valutare, non una selezione di stack.

Strategia incrementale preview-only da valutare:

1. OCR e layout creano un pacchetto di evidenze che conserva il testo grezzo,
   regioni/token, coordinate e confidence, hash/configurazione/trasformazioni,
   oltre a ipotesi esplicite di ordine di lettura e celle.
2. Un LLM locale riceve il pacchetto e produce una preview JSON/Markdown con
   riferimenti alle evidenze per ogni elemento. Il testo OCR originale rimane
   invariato; l'incertezza e' marcata e non si completa o corregge testo senza
   confronto visivo con la pagina.
3. La proposta e' revisionata contro la pagina e misurata con metriche testuali
   e strutturali separate. Una reference umana e' necessaria per dichiarare
   accuratezza, non per l'ispezione qualitativa.

Il primo pilot riusa i risultati gia' salvati per la pagina 00028 e un modello
locale gia' installato, senza download e senza servizi remoti. L'output resta
preview-only: non seleziona o promuove uno stack e non modifica la trascrizione
OCR grezza.

Esito del pilot locale su 00028 con `qwen2.5-coder:1.5b` via Ollama: due
risposte estese sono state troncate; una richiesta JSON compatta ha restituito
45/45 region ID una volta ciascuno, ma soltanto un heading e un paragraph con
gli altri 44 ID. Non ha ricostruito la tabella e non consente claim di
accuratezza. Gli output persistenti sono in
`%LOCALAPPDATA%\MeMoRiA\ocr-review\T314-1275-00028-hybrid-reconstruction`.
L'artefatto `markdown\test-images-661d6b0728033fa0\tesseract-page-1.md`
presente nella cartella `P:\Comune\Me.Mo.Ri.a\documenti_da_processare\foto\T314 R1275\test`
e' un Markdown Tesseract `deu`, `unreviewed`, timestamp 2026-09-17, e non il
run GPU. La variante `documenti\_da\_processare` non esiste; nel percorso
esaminato non sono stati identificati nuovi artefatti GPU. Non attribuire a quel
run risultati o output.

Conservare sempre l'output OCR grezzo separato. Ogni testo formattato o corretto
deve rinviare ai token/regione/bounding box di origine, confidence,
motore/modello e trasformazioni applicate; mantenere esplicita l'incertezza e
non completare testo senza evidenza. Valutare separatamente accuratezza e
coverage testuale, struttura delle celle e reading order, invenzioni,
formattazione e latenza/risorse; disaggregare i risultati per lingua e
difficolta' su fixture offline con reference umana.

La geometria OCR da sola non assegna semantica alle celle e non recupera lo
stile tipografico visivo. Markdown e Word sono derivati e non costituiscono una
trascrizione archivistica verificata. Questa conclusione resta valida; la scelta
implementativa viene invece fissata dalla decisione 2026-09-20 seguente.

Riferimenti upstream ufficiali, da usare per descrivere le interfacce e
impostare il confronto, non come evidenza di qualita' o supporto linguistico:
[PaddleOCR PP-StructureV3](https://paddlepaddle.github.io/PaddleOCR/main/en/version3.x/pipeline_usage/PP-StructureV3.html)
documenta la pipeline di parsing; [Docling usage](https://docling-project.github.io/docling/usage/)
documenta la conversione del documento con esportazione Markdown.

## Decisione OCR strutturato 2026-09-20

La fase esplorativa OCR/layout viene chiusa come confronto aperto e passa a una
direzione implementativa selezionata. Documento di riferimento:
`memoria-bootstrap/docs/ocr-structured-evidence-strategy.md`.

Direzione:

```text
immagine
  -> PP-OCRv5 structured regions
  -> OcrPageEvidence
  -> ricostruzione deterministica della struttura
  -> DocumentStructure
  -> Markdown derivato
  -> review
```

PP-OCRv5 e' il recognizer primario del prossimo pilot; Tesseract resta seconda
lettura/fallback e comparatore. La scelta e' relativa alla traiettoria corrente
e non implica accuratezza universale su qualunque scansione storica.
PP-StructureV3 e Docling restano strumenti di confronto, non dipendenze del
critical path. I VLM non ricevono il compito page-level di riscrivere la pagina:
possono essere introdotti soltanto dopo il baseline deterministico e su crop
ambigui, se una misura separata ne dimostra il beneficio.

Il testo piatto normalizzato non e' la sorgente canonica per layout o Markdown.
L'evidenza primaria conserva regioni, geometria, confidence, engine/modello e
trasformazioni; il Markdown e' una view derivata con riferimenti alle regioni.

### T35 - PP-OCRv5 structured evidence contract e adapter

Dipendenze: T34b chiusa; benchmark PP-OCRv5 e pilot OCR/layout del 2026-09-19.

Obiettivo: trasformare l'adapter PP-OCRv5 da benchmark text-only a produttore di
evidenza OCR strutturata engine-neutral.

Criteri di uscita:

- `rec_texts`, `rec_scores` e geometria disponibile (`rec_polys`/`rec_boxes`)
  sono conservati senza perdita nel nuovo contratto;
- ogni regione ha ID stabile, testo, confidence, geometria e provenance;
- gli ID regione derivano dall'ordine dei risultati e non sono ancore persistenti
  da soli; per riusare annotazioni vanno associati all'hash/versione
  dell'artefatto o del run;
- la trasformazione immagine e il riferimento alla pagina sorgente sono
  tracciabili;
- l'import PaddleOCR resta lazy/opt-in;
- Tesseract legacy resta compatibile;
- test offline/injected mirati passano o le failure preesistenti sono separate e
  documentate;
- nessuna inferenza di heading, paragraph, list, table o Markdown in T35.

Stato: **completata il 2026-09-20**. Il contratto strutturato conserva testo,
confidence, geometria neutra polygon/bbox, ID, hash/provenance di trasformazione,
engine e lingua; test offline/injected e review: PASS. Gli ID restano relativi
all'ordine dei risultati e non si dichiara accuratezza su scansioni storiche.

### T36 - High-resolution transform e tiling pilot

Dipendenze: T35.

Obiettivo: evitare che il downscale globale diventi una perdita obbligatoria di
informazione su scansioni degradate. Pilot controllato sui due TIFF guida.

Il pilot rende gli output verificabili insieme all'utente: mostrare
trasformazioni applicate, crop/tile generati, risultati OCR e collegamento alla
pagina sorgente con hash e parametri. Usare le pagine guida `00028` e `00026`;
non avviare un lotto esteso prima della revisione condivisa degli output.

Criteri di uscita:

- trasformazioni nominate e riproducibili con hash/parametri;
- almeno raw/grayscale, contrast enhancement e threshold come varianti separate;
- supporto pilot per crop/tile o bande sovrapposte a risoluzione vicina
  all'originale;
- merge delle regioni con coordinate ricondotte alla pagina sorgente;
- nessuna modifica agli originali e nessun preprocessing distruttivo imposto
  come unico percorso;
- confronto qualitativo documentato su `T314-1275-00026` e `00028`.

Chiusura tecnica 2026-09-20: pilot completato su due TIFF da 3632x6192. Gli hash
dei byte grezzi coincidono con gli originali. Per ciascuna pagina sono state
prodotte quattro varianti full-page (raw, grayscale, contrast, threshold) e sei
tile raw 2400x2400 con overlap 200: 8 output full-page e 12 tile, 20 output OCR
totali. Provenance e geometrie sono state verificate; review tecnica PASS senza
rilievi. Il runtime ha comunque segnalato `max_side_limit=4000` nonostante
`8192` configurato, mentre i tile nativi restano 2400. Il threshold danneggia
in particolare `00026`. Confidence non equivale ad accuratezza; nessuna
accuratezza e' dichiarata. La revisione visiva utente ha preferito
`contrast-x1.8` per entrambe le pagine; per `00028` tutte le varianti sono
risultate ragionevolmente leggibili. Gli overview `visual-review` mostrano solo
la zona alta a sinistra e appaiono ritagliati. Questo e' feedback sugli
artefatti visivi, non validazione OCR.

Stato: **completata il 2026-09-20**; la review visiva non approva trascrizioni
o claim.

### T37 - Deterministic structure reconstruction e Markdown

Dipendenze: T36.

Obiettivo: introdurre il contratto `DocumentStructure` e ricostruire Markdown
senza chiedere a un modello generativo di riscrivere l'intera pagina.

Primi profili documentali:

- `leader_list_report` per sezioni, label, dot leader e valori allineati; caso
  guida `00028`;
- `numbered_report` per titoli, sezioni numerate, paragrafi e continuation line;
  caso guida `00026`.

Criteri di uscita:

- blocchi `heading`, `paragraph`, `key_value`, `list`, `table` o `unknown` con
  `source_region_ids`;
- parser basato prima su geometria, distanze, indentazione e pattern espliciti;
- stato/confidence della struttura distinto dalla confidence OCR;
- renderer Markdown legge `DocumentStructure`, non la stringa OCR normalizzata;
- nessun testo aggiunto senza regione sorgente, salvo marcatori espliciti di
  illeggibilita'/incertezza;
- golden fixture strutturali per i due profili iniziali.

Stato: **completata il 2026-09-20**. Il modulo separato costruisce i due
profili geometry-first solo da fixture OCR sintetiche: i blocchi mantengono
`source_region_ids`, `status` e `structure_confidence` distinti dalla confidence
OCR; il renderer Markdown consuma soltanto `DocumentStructure`. Il materiale
vuoto o non riconosciuto resta esplicitamente incerto. I golden test non usano
immagini o trascrizioni storiche e non producono claim di accuratezza. Sei
test mirati sono passati e la review indipendente conclusiva e' PASS. Il
residuo e' che i profili sono verificati solo su input sintetici: non si
dichiara accuratezza OCR o strutturale su documenti reali. Prossimo candidato
T38, previa disponibilita' di reference umana verificata.

### T38 - Reference umana e metriche OCR/struttura

Dipendenze: T37.

Obiettivo: misurare separatamente fedelta' testuale e ricostruzione della
struttura su un campione piccolo ma verificato.

Reference minima:

- pagina `00028` completa;
- crop rappresentativi di `00026`, inclusi testo leggibile, degradato e
  abbreviazioni difficili.

Metriche minime:

- testo: CER/WER o misura equivalente, coverage e invenzioni;
- struttura: reading order, heading/paragraph, continuation e pairing
  label-valore;
- review: numero di regioni/blocchi che richiedono intervento umano;
- risorse: latenza e trasformazioni usate.

Criteri di uscita:

- nessuna accuratezza su scansioni reali viene dichiarata senza reference;
- il quality gate tecnico viene descritto come processabilita', distinto da
  accuratezza e review;
- threshold per l'eventuale resolver visuale T39 definiti da errori misurati.

Per preparare la scala, costruire poi un campione iniziale complessivo di
30-50 pagine, stratificate per lingua, leggibilita' e tipologia. Il numero e'
esplorativo e non garantisce rappresentativita' statistica. Separare pagine di
calibrazione e holdout prima di fissare soglie o scalare; includere l'intera `00028` e crop
rappresentativi della `00026` nel pilot guida, senza confonderli con un holdout
indipendente. Verificare inoltre casualmente una quota degli output non segnalati
dal triage.

Stato: **contratto ed evaluator offline completati il 2026-09-21**; la
valutazione delle pagine guida resta in attesa di una reference umana verificata.

Il sotto-incremento `t38-human-reference-contract-offline-metrics` introduce
`OcrPageReference` page-scoped e un evaluator per CER/WER, coverage e
invenzioni, ordine e tipi dei blocchi, nonché pairing label-valore. I risultati
conservano la provenance OCR completa e l'anchor stabile alla pagina originale
emesso da T36, distinguendolo da crop e varianti. Le metriche sono eleggibili
per una valutazione reale solo con audit `human_verified`, reference verificata
e identità della pagina corrispondente. Fixture sintetiche verificano soltanto
il determinismo del contratto e dell'evaluator: non è disponibile una
trascrizione/reference umana per le pagine guida e non si dichiara accuratezza
su scansioni reali.

T39 resta condizionale: procedere solo dopo misure su reference verificata che
identifichino errori per cui un resolver visuale possa dimostrare beneficio.

### T38a - Ranking OCR assistito da dizionari

Dipendenze: T38.

Ingresso: T38 deve avere almeno una reference umana page-scoped e un candidato
OCR misurabile; il ranking lessicale non sostituisce la reference e non modifica
il raw OCR.

Obiettivo: usare dizionari offline dichiarati per proporre candidati a token
degradati, includendo tedesco storico/generale e sigle militari come fonti
separate, senza correzione automatica.

Criteri di uscita:

- contratto lessicale con termine, categoria, source_id e versione;
- suggerimenti deterministici basati su distanza edit e soglia esplicita;
- raw OCR, suggerimenti e decisione umana restano campi distinti;
- ogni suggerimento conserva provenance della voce lessicale e stato
  unreviewed;
- metriche T38 confrontano separatamente raw e candidato assistito;
- fixture sintetiche offline; nessun dizionario reale o trascrizione storica
  viene incorporato nel repository;
- se il ranking non riduce gli errori senza aumentare invenzioni, si chiude
  senza promozione del metodo.

Stato: completato il 2026-09-22. Il ranking e' deterministico e review-only;
raw OCR e decisione umana restano separati. I test usano solo fixture
sintetiche e non dimostrano accuratezza su scansioni reali.

### T39 - Selective visual ambiguity resolver

Dipendenze: T38.

Ingresso condizionale: eseguire soltanto se T38 mostra categorie di errore per
le quali un resolver visuale locale puo' aggiungere valore misurabile.

Obiettivo: usare un VLM solo su crop ambigui, mai come page-to-Markdown libero.

Criteri di uscita:

- trigger espliciti, per esempio bassa confidence o discordanza tra recognizer;
- input limitato a crop originale + candidati OCR + provenance;
- output schema-constrained: testo visibile o `[illeggibile]`;
- temperatura zero e nessun completamento congetturale;
- confronto con reference T38 e mantenimento del candidato OCR originale;
- se non emerge un vantaggio misurabile, T39 si chiude senza integrazione VLM.

Stato: contratto preview-only completato il 2026-09-22 con resolver iniettato e
test offline. Nessuna integrazione VLM live o beneficio reale e' stato
dichiarato; l'eventuale adozione resta condizionale a un confronto verificato.

### T40 - Integrazione CLI del flusso OCR validato

Dipendenze: T37 e T38; T39 solo se adottato.

Obiettivo: esporre tramite CLI Python il percorso validato da documento a
trascrizione Markdown revisionabile, senza introdurre una pipeline parallela.

Criteri di uscita:

- `memoria documents process` o comando equivalente usa il contratto strutturato;
- preview/apply, idempotenza, error isolation e provenance restano espliciti;
- raw OCR, `OcrPageEvidence`, `DocumentStructure` e Markdown derivato restano
  distinguibili;
- extraction e claim possono consumare solo artefatti tracciabili secondo le
  regole di review esistenti;
- per ogni lotto registrare throughput, latenza p95, costo per 1000 pagine e
  minuti di revisione umana per 100 pagine; introdurre checkpoint idempotenti,
  retry limitati e isolamento degli errori;
- confidence, disaccordo e processabilita' sono segnali per ordinare la review,
  non attestazioni di correttezza; ogni fatto pubblicabile mantiene fonte
  tracciabile e revisione umana;
- nessuna scrittura canonica di profili o fatti senza workflow autorizzato.

Stato: micro-incrementi CLI preview-first e osservabilita' completati il
2026-09-22 per `documents structure`; il batch completo resta futuro.

Stop condition della traiettoria: non aggiungere un nuovo framework OCR/layout
prima di T35-T37, salvo un difetto misurato che il percorso selezionato non puo'
coprire.

### T41 - Calibrazione OCR su campione reale stratificato

Dipendenze: T38 e T40.

Obiettivo: calibrare il confronto OCR su un campione reale piccolo e
rappresentativo, mantenendo separati output grezzi, reference umane e qualsiasi
decisione successiva.

Protocollo minimo:

- partire da un campione iniziale di 8-10 pagine e solo dopo estenderlo a un
  campione esplorativo di 30-50 pagine;
- stratificare le pagine per leggibilita', lingua e layout, annotando gli strati
  prima del confronto;
- usare reference umane page-scoped esterne al repository, con identita', hash
  e coordinate sufficienti a verificare la corrispondenza, senza copiare testi
  reali nel worktree;
- confrontare Tesseract e PP-OCRv5 su pagina intera, crop e tile, includendo
  trasformazioni dichiarate e mantenendo distinto il raw OCR;
- misurare CER, WER, coverage, omissioni, invenzioni, geometrie, ordine di
  lettura e latenza, con risultati disaggregati per strato e configurazione;
- separare il sottoinsieme di calibrazione dall'holdout prima del campione
  esplorativo e controllare anche output non segnalati dai gate di triage.

Vincolo tecnico obbligatorio per ogni run OCR successivo:

- venv/runtime, versioni, pesi, cache, `tessdata`, output di run e manifest
  devono risiedere sotto una root persistente, dichiarata e associata a
  Me.Mo.Ri.A; `Temp` e cache utente implicite non possono essere dipendenze
  operative;
- gli asset grandi o operativi restano fuori dal repository Git, ma la loro
  root, versione, hash e provenance devono essere configurabili e verificabili
  dal manifest del run;
- la root deve distinguere asset condivisi, cache e output di run e non deve
  incorporare dati storici canonici nel repository.

Gate e limiti:

- T41 calibra configurazioni e criteri di revisione, non produce una soglia
  archivistica o una dichiarazione generale di accuratezza;
- nessun engine, trasformazione o lettura viene promosso automaticamente e
  nessuna reference umana viene trattata come claim pubblicabile senza il
  workflow di revisione previsto;
- il campione reale, le reference e gli artefatti di run restano esterni al
  repository; TIFF, profili canonici, claim e fatti verificati non vengono
  modificati.

Stato: pianificata come micro-incremento documentale chiuso il 2026-09-25;
l'esecuzione della calibrazione reale richiede un task successivo con input
  esterni tracciati.

La formalizzazione del vincolo project-local è chiusa il 2026-09-26. La
migrazione runtime degli asset oggi presenti in
`C:\Users\info\AppData\Local\MeMoRiA\ocr-assets` e
`C:\Users\info\AppData\Local\MeMoRiA\ocr-runs` è il prossimo incremento
separato: deve prima dichiarare la root persistente, poi migrare/verificare
versioni, hash e provenance senza scaricare o spostare file in questo
incremento documentale.

## Traccia parallela Q - Qualita' e refactor continuo

Questa traccia puo' avanzare in parallelo agli incrementi T, ma non li sostituisce
e non autorizza refactor ampi. Ogni intervento deve essere piccolo,
verificabile, senza cambio di comportamento e legato a un rischio concreto di
manutenibilita'.

### Q1 - Audit modularita' memoria-engine

Dipendenze: T13b.

Collegamento MVP: supporto trasversale a tutti gli incrementi MVP, riducendo il
rischio che il package Python diventi difficile da modificare e testare.

Criteri di ingresso:

- suite test passante o stato test documentato;
- package Python installabile;
- moduli Python principali identificabili con metriche leggere;
- nessuna urgenza funzionale bloccante sull'incremento T corrente.

Criteri di uscita:

- elenco dei moduli Python piu' grandi o piu' accoppiati;
- responsabilita' principali di ogni modulo critico descritte;
- candidati micro-refactor ordinati per rischio e valore;
- per ogni candidato, test minimi da eseguire identificati;
- nessun codice spostato in questo audit salvo correzioni documentali minime.

Stato: chiusa.

### Q2 - Micro-refactor opportunistici

Dipendenze: Q1.

Collegamento MVP: supporto trasversale.

Criteri di ingresso:

- candidato micro-refactor gia' classificato in Q1 o emerso durante un
  incremento T;
- comportamento atteso coperto da test esistenti o da test mirati aggiunti;
- scope limitato a una responsabilita' chiara.

Criteri di uscita:

- una sola responsabilita' estratta, rinominata o isolata;
- nessun cambio di output, CLI, schema o workflow salvo decisione esplicita;
- test mirati passanti;
- documentazione aggiornata solo se cambia un confine pubblico.

Stato: differita per decisione di priorità del 2026-09-10. I micro-refactor Q2
restano disponibili dopo la chiusura di T34b, ma non devono precedere la
finalizzazione della migrazione profili legacy.

### Q2b - Pulizia delle copie private legacy dei renderer funding package

Dipendenze: Q2 - Isolamento dei renderer Markdown del funding package.

Obiettivo: rimuovere le copie private legacy rimaste in
`mvp_funding_package.py` dopo l'estrazione dei renderer, mantenendo come unica
implementazione autorevole `mvp_funding_package_markdown.py`.

Perimetro:

- eliminare esclusivamente le definizioni private duplicate e non utilizzate;
- mantenere gli export pubblici compatibili e gli alias di retrocompatibilita';
- non modificare output Markdown, builder, CLI, schema o workflow.

Criteri di uscita:

- nessuna copia privata legacy dei renderer resta nel builder;
- import pubblici e nuovo modulo renderer verificati;
- test mirati `tests.test_mvp_funding_package` passanti;
- nessun dato esterno o profilo canonico modificato.

Stato: chiusa il 2026-09-02.

## Criteri tecnici generali

- Prima leggere roadmap e stato corrente.
- Poi documentare il confine dell'incremento.
- Poi aggiungere test mirati se si modifica codice.
- Poi modificare il minimo necessario.
- Non introdurre dipendenze senza necessita' esplicita.
- Non usare dati reali come fixture.
- Non usare scansioni massive come controllo diagnostico.
- Non saltare milestone senza decisione registrata.
- La traccia Q puo' essere eseguita in parallelo solo come audit o micro-refactor
  con comportamento invariato, test mirati e stop condition esplicita.

## Fuori scope tecnico immediato

- Refactor ampi.
- Nuovi framework CLI.
- OCR orchestration.
- Extraction.
- JSON-LD writer.
- Pipeline end-to-end.
- Generazione di schede definitive.
