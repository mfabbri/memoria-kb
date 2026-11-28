# Ricerca online e review candidate da CLI

Questa procedura guida una ricerca reale usando una fonte già dichiarata nel
registry fino alla review umana delle candidate Place o HistoricalEvent. I
risultati restano candidati: non diventano fatti canonici e non vengono
pubblicati automaticamente.

Per menzioni e action collegate a profili persona, applicare anche il
`codex-person-profile-feedback-loop-core.md`: la review di una action e la
risoluzione dell'identità sono decisioni distinte.

Eseguire tutti i comandi di prodotto qui sotto con il launcher Me.Mo.Ri.A
installato (`memoria` o l'eseguibile nella `.venv`), non con `python -m` o
import diretti. Se il launcher non parte, riparare prima l'ambiente e poi
ripetere il comando attraverso il launcher.

## Destinazione persistente degli artifact reali

Per ogni ricerca o review reale, creare un nuovo run ID e salvare report,
documenti acquisiti, preview, claim, queue, manifest, receipt e feedback sotto
`P:\Comune\Me.Mo.Ri.a\risultati\runs\<run-id>\`. Organizzare i passaggi in
sottodirectory della stessa run; non sovrascrivere run precedenti. Non usare
`.tmp`, `.tmp-tests` o directory del repository per dati/artifact reali: sono
destinati a fixture sintetiche e smoke test. Se la root persistente non è
accessibile o scrivibile, interrompere il flusso e segnalare il blocco senza
creare un ripiego temporaneo. Nei comandi seguenti `<run-dir>` indica la
directory persistente di quella run, mentre gli input e gli output intermedi
vanno collocati nelle sue sottodirectory. Comunicare all'utente il percorso
effettivo, il contenuto prodotto e il successivo comando CLI.

## 1. Scegliere la fonte e verificare la ricerca

### Connettori e selezione degli attempt

Quando il registry dichiara un connettore per la fonte, usare il launcher
installato `memoria sources online run`. Consultare la strategia e selezionare
gli ID attempt autorizzati con `--attempt-id` ripetibile. Prima di eseguire,
confrontare gli ID del piano con i report dei run precedenti e con gli attempt
esclusi dall'utente. Non rilanciare attempt già eseguiti e non eseguire attempt
esclusi anche se riappaiono nel piano. `--execute-first-planned-attempt`, un
piano `ready_for_review` o una decisione `BUONA` non sostituiscono
l'autorizzazione per fonte e query.

**Attenzione:** `--include-search-plan` aggiunge il piano al report, ma non
attiva una modalità preview. Anche senza `--attempt-id`, il comando esegue la
strategia standard della fonte, che può lanciare più query. Prima di invocarlo
controllare gli attempt previsti e già eseguiti; per limitare la ricerca,
passare solo gli ID autorizzati con `--attempt-id`. Non usare questo comando
come ispezione innocua del piano: al momento non è una preview senza rete.

```powershell
memoria sources online run `
  --profiles-index <profiles-index.jsonld> `
  --sources-yaml memoria-sources/registry/camalanca_fonti.yaml `
  --source <source_id> --profile-id <profile_id> --limit 1 `
  --attempt-id <attempt_id> `
  --output-json <run.json> --output-dir <nuova-directory-run> `
  --acquire-documents-root <directory-acquisizione>
```

Aggiungere altri `--attempt-id` solo se autorizzati e non eseguiti. Per fonti
con SPID/CIE, il login resta un handoff manuale: non inserire credenziali,
cookie o token nella CLI. Quando il connettore esiste, non usare un motore web
generale come ripiego.

1. Leggere `memoria-sources/registry/camalanca_fonti.yaml` e scegliere un
   `source_id` presente in `enabled_sources` e adatto alla domanda. Non inventare
   una fonte o passare a uno scraping ampio per comodità.
2. Eseguire la ricerca e acquisire i risultati tramite il launcher e il
   connettore dichiarato per quella fonte. Non sostituire la ricerca CLI con
   motori web generali o navigazione diretta del browser. Conservare URL esatto,
   titolo e data di accesso. Una pagina dei risultati è un candidato da
   verificare, non una prova di per sé.
3. Trascrivere solo gli estratti pertinenti, con provenienza. Non dedurre fatti
   da un risultato di ricerca, da un nome simile o da OCR provvisorio.

Se il connettore marca il dettaglio `detail_needs_manual_review` o
`unverified_permalink_manual_review`, non trattare il collegamento costruito
come pagina verificata e non estrarre claim da quel dettaglio. Se il canale CLI
non consente la verifica richiesta, lasciare il documento candidato e
`unreviewed`, descrivere il limite e fermare la generazione di claim; non
aggirare il limite usando un browser o un motore esterno.

## 2. Registrare la pagina nel catalogo operativo

Usare il database operativo già configurato nel workspace. Non crearne uno
scratch quando la richiesta riguarda il catalogo reale e non scrivere nel DB con
script o SQL diretti.

Prima eseguire il comando in preview:

```powershell
memoria documents register-online-source `
  --database <database-operativo-esistente> `
  --source-id <source_id-abilitato> `
  --document-id <id-univoco> `
  --title <titolo-pagina> `
  --url <url-https> `
  --access-date YYYY-MM-DD
```

Controllare il riepilogo. Se è corretto, ripetere lo stesso comando con
`--apply`. Il comando crea `SearchRun` e `SourceDocument` in modo additivo e
idempotente; la pagina rimane `unreviewed`. `excerpt_only` non significa che
l'intera pagina sia stata archiviata: non dichiarare un archivio completo se
non esiste un file acquisito e verificabile.

Non correggere un record esistente sovrascrivendolo. Per la sola correzione
intenzionale del titolo è disponibile `--expected-existing-title`, che richiede
il titolo corrente esatto e verifica anche ID, fonte, URL e data.

### Sidecar acquisiti dal connettore

Il connettore può produrre sidecar `*.document.yaml` con il file acquisito e
metadata annidati. Sono input validi per `memoria documents text-extract` anche
se l'opzione CLI si chiama `--metadata-json`. Passare sidecar espliciti delle
sole schede dettagliate, non immagini o pagine generiche. L'estrazione mantiene
`source_document_id`, URL, titolo e `review_status`, calcola un digest e non
esegue OCR né crea claim. Usare una directory nuova per gli output.

Rispetta anche la valutazione del dettaglio del connettore: stati come
`detail_needs_manual_review` o
`unverified_permalink_manual_review` richiedono verifica manuale della pagina
prima di usarla per estrarre claim. Il fatto che `text-extract` riesca a leggere
il sidecar o che i metadata dicano `claim_eligible` non prova da solo che il
permalink sia stato verificato o che il contenuto supporti un'affermazione.

### Trascrizione manuale revisionabile di immagini gia' acquisite

Il launcher espone un percorso senza OCR/VLM e senza scansione del corpus:

```powershell
memoria documents transcription-wizard `
  --source-report <report-acquisizione-online.json> `
  --document-id <source-document-id-immagine-recto> `
  --document-id <source-document-id-immagine-verso> `
  --output-dir <nuovo-run-esterno> `
  --open-images
```

Il comando accetta gli ID delle **immagini correlate**, non l'ID della scheda
parent. Risolve solo i file espliciti del report e verifica parent, source ID,
sidecar online e SHA-256; non scarica URL e non modifica i flag delle fonti.
`--open-images` apre esclusivamente i file locali verificati con il viewer di
sistema, durante inserimento e review; senza flag stampa i percorsi. Non
attesta che il viewer o il reviewer abbiano identificato correttamente il dato.

Una persona inserisce identificativo trascrittore, porzione/campo, copertura
parziale/intera immagine e testo su una riga; `[i]` indica porzione illeggibile.
Il comando non propone letture e non usa appunti pregressi come precompilazione.
In una fase distinta raccoglie reviewer dichiarato, conferma della lettura,
rifiuto oppure incertezza; una nota e' obbligatoria per rifiuto/incertezza.
Reviewer e trascrittore possono coincidere: le identita' non sono autenticate
e non si dichiara una review indipendente. Una porzione illeggibile non puo'
essere confermata. `[q]`, EOF o mancata conferma finale non salvano receipt.

Solo dopo conferma finale scrive in una directory nuova:

- `transcription-draft.json`: testo manuale originario, ambito e stato unreviewed;
- `image-N.text.json`: ProcessedDocumentText con l'ID della singola immagine,
  metodo `manual_transcription`, confidence non misurata (`null`) e provenance;
- `transcription-manifest.json`: riferimenti e hash di report, immagini,
  sidecar, draft e testi;
- `transcription-review-receipt.json`: decisioni per immagine e porzione,
  reviewer dichiarato e timestamp, legati all'hash del manifest e dei testi.

Gli input sono ricontrollati prima della pubblicazione. Nessun overwrite;
input cambiati o conferma annullata impediscono una receipt completa.
`review_complete=true` significa decisioni definitive sulla lettura delle
porzioni dichiarate (anche respinte); incertezza mantiene `pending`.
Un testo confermato ha `review_status=human_reviewed_transcription`, non e' un
fatto storico verificato. Testi respinti/incerti restano `unreviewed`; porzioni
illeggibili non hanno testo inventato. `claim_eligible`, promozioni e scritture
canoniche restano disabilitati. La receipt non cambia immagini o catalogo.

Queste receipt riguardano la **trascrizione**, non le decisioni su EvidenceClaim:
non sostituiscono `claims-wizard`. Per eventuali claim futuri occorrono i gate
del dominio e l'ID della fonte realmente citata; non verificare un claim del
parent contro la trascrizione di un'immagine con ID diverso.

Il wizard non ha un'opzione per saltare un'immagine gia' selezionata. Se la
persona esclude una faccia, annullare senza scritture e riavviare con i soli
ID voluti, riportando esclusivamente le risposte gia' fornite. Non sostituire
un'esclusione con il marcatore di illeggibilita' o con un testo inventato.
Nella guida in chat, mostrare i file locali indicati dalla CLI e usare parole
semplici: la copertura parziale corrisponde alla scelta di un solo campo.
Il wizard gira nel terminale della sessione; non apre una finestra del form.

Per Bendini, dopo i test sintetici e' stata autorizzata e completata la sola
trascrizione/review del campo Formazione del recto nel run esterno
`bendini-transcription-review-20261124-recto`, senza nota; verso escluso.
Il launcher ha salvato una decisione di lettura, non una nuova EvidenceClaim.
La vecchia scheda fuori procedura resta non validata e non e' un input ammesso.
T41 resta sospeso; non avviare altre review o ricerche senza perimetro autorizzato.

### Copie locali, lineage e fedelta' delle citazioni

Quando l'utente fornisce una directory di documenti e autorizza l'inventario
ricorsivo, scandire quella radice includendo le sottodirectory; non sostituire
la scansione richiesta con la sola lista del primo livello. Comunicare quanti
file sono stati esaminati, quali formati/file pertinenti sono stati trovati e
ogni limite di accesso. Non estendere l'inventario ad altre radici senza
autorizzazione.

Un'acquisizione locale di una pagina online resta un `SourceDocument`
identificabile separatamente. Se il sidecar dichiara
`original_source_document_id`, conservarlo come provenance esplicita; non
dedurre una relazione da URL simili o hash. Quando entrambi gli ID sono noti,
la CLI consente una preview read-only:

```powershell
memoria review source-lineage-preview `
  --links-json <SourceDocumentLineageRequest.json> `
  --source-documents-db <catalogo-operativo> `
  --output-dir <nuova-directory-run>
```

La richiesta deve esplicitare i due ID, un tipo relazione ammesso, rationale e
riferimento alla provenance. Il comando verifica la presenza nel catalogo e
produce `CandidateSourceDocumentLineageSet` con relazioni `unreviewed`; non
scrive o fonde record. Per dati reali salvare input e output nella directory
persistente della run indicata sopra, mai in `.tmp` o `.tmp-tests` del repository.

Prima di usare una quote di claim, confrontare l'`evidence_span` esatto con il
`ProcessedDocumentText` del medesimo `source_document_id`:

```powershell
memoria review evidence-verify `
  --claims-json <CandidateEvidenceClaimSet.json> `
  --processed-text <ProcessedDocumentText.json> `
  --output-dir <nuova-directory-run>
```

`not_exact` segnala una discrepanza testuale, non decide quale versione sia
corretta. Non riscrivere claim o receipt gia' revisionati: ogni eventuale
correzione richiede una nuova decisione umana. La vista consolidata puo' mostrare
separatamente quote-check e lineage, mantenendo provenance e stati di review:

```powershell
memoria review memory-view `
  --inventory-json <ResearchMemorySessionInventory.json> `
  --lineage <CandidateSourceDocumentLineageSet.json> `
  --quote-verification <CandidateEvidenceQuoteVerification.json> `
  --output-dir <nuova-directory-run>
```

La presenza di due documenti o di due acquisizioni dello stesso URL non prova
due fonti indipendenti. Mantenere visibili lineage e conflitti; non promuovere
claim, non risolvere identita' o date divergenti e non modificare i profili.

## 3. Generare la preview

Preparare gli input macchina necessari a partire dall'estratto reale e dalla
provenienza verificata; l'utente non deve crearli o compilarli. Poi eseguire il
comando CLI pertinente:

- `memoria documents place-preview` per candidate Place;
- `memoria documents event-preview` per candidate HistoricalEvent.

Gli input strutturati sono preparati dall'agente o da un comando upstream;
l'utente non li compone e non modifica JSON. Usare una directory di output
dedicata alla run. Le forme dei comandi sono:

```powershell
memoria documents place-preview `
  --segments-dir <segmenti-generati> `
  --candidate-claims-json <claim-candidate-generati> `
  --source-documents-db <database-operativo-esistente> `
  --places-index-json <indice-place> `
  --place-jsonld <place-candidato> `
  --output-dir <nuova-directory-preview>

memoria documents event-preview `
  --segments-dir <segmenti-generati> `
  --candidate-claims-json <claim-candidate-generati> `
  --source-documents-db <database-operativo-esistente> `
  --events-index-json <indice-eventi> `
  --event-jsonld <evento-candidato> `
  --output-dir <nuova-directory-preview>
```

Il CLI valida il catalogo in sola lettura, genera i file di preview e mostra il
manifest, gli ID e i conteggi. Usare il manifest stampato dal comando; non
chiedere all'utente di aprire o modificare gli artifact JSON.

Quando sono già disponibili i tre set di link candidati, la vista tipizzata
comune si compone senza inferenze aggiuntive:

```powershell
memoria documents relationship-preview `
  --person-links-json <candidate-document-person-links> `
  --place-links-json <candidate-document-place-links> `
  --event-links-json <candidate-document-event-links> `
  --output-dir <nuova-directory-preview>
```

La vista distingue `identity_match_candidate` dai link di menzione Place/Event,
conserva provenienza del link e contesto-evidenza e lascia i candidati
`unreviewed`. Gli identificativi del documento non sono verificati nel catalogo
da questo compositore; un link a HistoricalEvent non afferma partecipazione
personale né un fatto storico. Le collisioni restano visibili come candidati
separati.

`CandidateEntityRelationshipManifest` è una vista riepilogativa, non una
receipt di review e non è attualmente accettato da
`documents preview-review-wizard`. Lasciare il set `unreviewed`; per Place/Event
usare il manifest specifico prodotto dai rispettivi preview. Non dichiarare
review completata finché non esiste una receipt riferita agli artifact esatti.

Prima di passare alla review, spiegare in breve cosa è stato generato, dove si
trova la preview e che cosa resta da decidere. Le candidate e i conteggi non
sono conferme storiche; link e aggiornamenti non modificano l'entità canonica.

## 4. Raccogliere le decisioni nel wizard

Avviare il wizard con il manifest della preview e un nuovo percorso per la
receipt:

```powershell
memoria documents preview-review-wizard `
  --manifest <percorso-manifest> `
  --output <percorso-nuova-receipt>
```

Il wizard mostra un candidato alla volta, la corrispondenza e la provenienza
disponibile. Chiede reviewer, decisione, nota facoltativa e conferma finale. Solo
la persona che revisiona sceglie se accettare, respingere o chiedere altre
evidenze. Uscita o mancata conferma non scrivono la receipt. La receipt registra
decisioni e hash per audit; non autentica il reviewer e non applica modifiche
canoniche.

Non usare `preview-review-template`/`preview-review-record` come procedura da
assegnare all'utente e non chiedere decisioni via JSON o testo ambiguo. Se il
wizard non è disponibile, fermare il passaggio di review e delimitare un
incremento CLI per colmare la lacuna; non inventare decisioni.

## 5. Chiudere il passaggio

Riportare il percorso degli artifact, l'esito del wizard e i limiti della
fonte. Se la review è ancora pendente, lasciare le candidate `unreviewed` e
indicare il comando esatto per riprenderla. La chiusura di T48 non autorizza
claim canonici, merge o pubblicazione. T49 resta un percorso separato: fixture
e preview non valgono come ricerca/review reale né come autorizzazione a
eseguire nuove query.

### Decisioni umane: una per volta e con contesto

Quando manca un'autorizzazione o serve scegliere una candidata, presentare una sola decisione per messaggio. Includere il contesto necessario: persona/profilo in esame, fonte abilitata, tentativo e query esatti, cosa è già stato eseguito, risultati candidati già presenti e cosa l'autorizzazione sblocca. Separare la valutazione di utilità dell'action (`BUONA`/`DUBBIA`/`INUTILE`) dall'autorizzazione alla ricerca e dalla risoluzione dell'identità. Registrare il perimetro letterale della risposta; un sì a un attempt non autorizza gli altri tentativi del piano, una nuova fonte o una query futura. Dopo la decisione, eseguire solo il perimetro autorizzato e comunicare run/artifact e prossimo comando CLI. Se non serve alcuna decisione, proseguire con il prossimo passaggio già autorizzato.
