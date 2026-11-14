# T55 — Valutazione del pilot Bendini (2026-11-14)

## Esito

Il dossier multi-fonte non è stato composto: le evidenze disponibili non
consentono di attestare due `SourceDocument` online/offline nel catalogo
operativo senza aggiungere una capacità CLI mancante o fare nuove registrazioni.
Non sono state eseguite ricerche live, registrazioni, review o scritture.

## Materiale esistente

- T47 contiene un CSV locale non claim-eligible, un DOCX locale e una pagina
  `storia_memoria_bo`; l'audit T47 indica che gli ID CSV, DOCX e pagina online
  non sono presenti nel catalogo `evidence.sqlite`.
- Il PDF trovato da T47 resta un SearchResult: non è stato acquisito né
  registrato come SourceDocument.
- T49 Bendini contiene report per `storia_memoria_bo` e `partigiani_italia`,
  con documenti candidati e preview feedback. La presenza dei relativi documenti
  nel catalogo operativo non è attestata da ricevute disponibili in questo
  audit.
- Il data root e `database/evidence.sqlite` sono accessibili; i documenti reali
  restano esterni al repository.

## Gap CLI che blocca il dossier

La CLI installata offre `documents register-online-source` per fonti abilitate,
`documents register-ocr-source` per manifest OCR e `documents register` per
sidecar d'immagini. Non offre una registrazione preview/apply di un file locale
arbitrario, come il DOCX T47, nel catalogo `SourceDocument`. Il builder
`review claims-preview` verifica gli ID nel catalogo SQLite; la sola presenza
nei report T47/T49 non basta.

Per riprendere T55 serve un micro-incremento CLI circoscritto che registri un
singolo file locale esplicitamente selezionato con hash, media type, provenance
e `review_status`, preview prima di apply e verifica idempotente nel catalogo.
Poi si potrà registrare/validare la pagina online T47 già identificata e
costruire il dossier senza nuove query. L'identità del file e la decisione di
apply vanno confermate attraverso il workflow, non inferite da un SearchResult.

## Verifiche read-only

- Ispezionati il riepilogo e il descriptor T47, e la struttura dei report T49.
- Controllato l'help della CLI installata per le superfici di registrazione e
  `claims-preview`.
- Nessun output di dossier generato perché non è stato dimostrato il requisito
  minimo di due SourceDocument nel catalogo.
