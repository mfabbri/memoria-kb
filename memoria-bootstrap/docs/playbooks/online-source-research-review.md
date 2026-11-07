# Ricerca online e review candidate da CLI

Questa procedura guida una ricerca reale usando una fonte già dichiarata nel
registry fino alla review umana delle candidate Place o HistoricalEvent. I
risultati restano candidati: non diventano fatti canonici e non vengono
pubblicati automaticamente.

## 1. Scegliere la fonte e verificare la ricerca

1. Leggere `memoria-sources/registry/camalanca_fonti.yaml` e scegliere un
   `source_id` presente in `enabled_sources` e adatto alla domanda. Non inventare
   una fonte o passare a uno scraping ampio per comodità.
2. Consultare la pagina reale nel browser o nel canale consentito dalla fonte.
   Conservare URL esatto, titolo e data di accesso. Una pagina dei risultati è
   un candidato da verificare, non una prova di per sé.
3. Trascrivere solo gli estratti pertinenti, con provenienza. Non dedurre fatti
   da un risultato di ricerca, da un nome simile o da OCR provvisorio.

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
indicare il comando esatto per riprenderla. Nessun passo di questa procedura
autorizza claim canonici, merge, pubblicazione o avvio di T49 prima della
chiusura di T48.
