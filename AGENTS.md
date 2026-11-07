# AGENTS.md — Me.Mo.Ri.A

Regole persistenti (valgono per ogni task). Il resto si carica **solo quando
serve**: `memoria-bootstrap/docs/model-routing-policy.md`, skill mirate,
contratti e sezioni di roadmap pertinenti.

## Dominio e limiti

`fonti -> documenti -> evidenze -> riconciliazione -> revisione umana -> feedback -> nuova ricerca`.
Un risultato di ricerca non e' un fatto. Ogni `EvidenceClaim` richiede un
`SourceDocument` identificabile, provenance e `review_status`; le patch canoniche,
le decisioni storiche e la pubblicazione non sono automatizzate.
Dati reali, credenziali, corpus OCR e run pesanti restano fuori da Git.
Il registry `memoria-sources/registry/camalanca_fonti.yaml` e' la fonte di verita'
per i quattro livelli dichiarativi delle fonti.

Per ricerche online parti da una fonte abilitata nel registry e dal database
operativo configurato; usa la CLI per registrare SourceDocument e generare le
preview, poi il wizard per raccogliere le decisioni umane. Non chiedere
all'utente di creare o compilare JSON. Spiega dove la CLI ha salvato gli
artifact, cosa contengono e il comando successivo. Se manca un passaggio CLI,
delimita l'estensione necessaria prima di trasferire all'utente attività manuali
sui file. Procedura completa: `memoria-bootstrap/docs/playbooks/online-source-research-review.md`.

## Incrementi

- Leggi `memoria-bootstrap/planning/current-work.json` per scoprire eventuale
  lavoro persistente; se concluso, usa `$memoria-roadmap-selector` per scegliere
  dalle sezioni post-MVP delle roadmap, senza leggere tutta la cronologia.
- Un micro-incremento verificabile alla volta: obiettivo, write set, prova
  mirata e stop condition. `memoria-engine` contiene runtime e test;
  `memoria-bootstrap` pianificazione; `memoria-sources` registry;
  `memoria-rules` regole; `memoria-knowledge` dominio;
  `memoria-workspace` descriptor, non dati reali.
- Usa `$memoria-session` per lavori sostanziali multi-step; non per typo o
  review read-only. Una skill verticale alla volta, quando pertinente.
- Preferisci fixture offline, preview prima di apply, idempotenza, audit,
  provenance e test che falsifichino il cambiamento. Non avviare grandi
  scansioni, refactor estesi o nuovi scraping senza scope esplicito.

## Modelli, delega e token

Policy: `memoria-bootstrap/docs/model-routing-policy.md` (v3.1).
Parent `gpt-6-luna/low`; lavora direttamente per discovery, documentazione e
fix minimi ben circoscritti. Sol/medium per implementazioni sostanziali o
review indipendenti necessarie; Astra/low per trade-off architetturali complessi.
**Non creare subagent per principio**: delega solo per lavoro separabile,
review indipendente ad alto rischio o contesto che giustifica l'overhead.
Registra disponibilita' e fallback espliciti; i nomi del config non garantiscono
l'accesso al modello. Passa riferimenti a file e risultati, non dump integrali.

Per task OCR apri soltanto la sezione pertinente di
`memoria-bootstrap/docs/playbooks/codex-document-analysis-core.md`;
preflight Ollama WSL solo se e' prevista inferenza VLM. La soglia T42
provisional `1.0` non e' discriminante, non abilita `machine_pass`, claim o
pubblicazione. Il gate formale OCR resta separato.

## Chiusura

Riporta: incremento, file cambiati, test fatti/non fatti, risultati, limiti e
prossimo candidato. Aggiorna solo i documenti direttamente impattati.
