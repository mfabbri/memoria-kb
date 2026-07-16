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

La superficie canonica futura per i workflow operativi deve essere la CLI Python
installabile `memoria`, non un wrapper specifico di piattaforma. La CLI deve
restare eseguibile come console script su Windows e Linux, usando path espliciti,
`MEMORIA_DATA_ROOT` o manifest per risolvere il data root.

I wrapper OS-specifici restano ammessi, ma come facciate sottili:

- `scripts/memoria.ps1` continua a servire l'MVP e i workflow Windows gia'
  validati;
- un futuro wrapper shell Linux potra' offrire ergonomia equivalente;
- la logica di dominio, selezione run, review, fonti e decisioni non deve essere
  duplicata in PowerShell e shell script;
- la migrazione dei workflow operativi nella CLI Python richiede incrementi
  dedicati, test mirati e nessun cambio di output osservabile.

Per l'MVP da mostrare ai finanziatori resta accettato usare PowerShell come
superficie operativa primaria, per ridurre il rischio della demo. Questa scelta
e' una compatibilita' temporanea, non la destinazione architetturale finale.

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

Stato: futuro candidato in hold finche' l'accesso API pCloud non e' risolto o
finche' non viene autorizzato un incremento solo mock senza accesso live.

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

- dossier finanziatori breve collegato alla golden run;
- script del walkthrough e comandi di fallback disponibili;
- diagramma del percorso fonti-documenti-evidenze-review-feedback;
- scheda del caso demo con provenance leggibile;
- roadmap dell'uso dei fondi e risultati attesi;
- distinzione esplicita fra capacita' attuali, sviluppo finanziato e visione;
- checklist di readiness approvata per presentazione esterna;
- nessuna affermazione storica non supportata o output preview presentato come
  pubblicabile.

Stato: **aperto e prioritario**.

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

Stato: prossimo candidato.

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
