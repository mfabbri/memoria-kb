# Focus operativo Me.Mo.Ri.A — 2026-11-24

## Decisione di prodotto (prevale sulle priorita' storiche)

**MVP T29-T33 completato; T53-T84 sono storico implementativo.** Dopo T84
sono stati consegnati dossier, viste e report T86-T89. Il problema aperto e'
dimostrare nuova evidenza utile e cicli ripetibili su piu' casi reali.
Un incremento `completed` puo' chiudere una consegna o un attempt senza
risolvere il problema storico. Lo stato del task corrente va letto dalla
summary del planner, non dedotto dal vecchio snapshot T84.
T41 OCR e T27/T28 pCloud restano **sospesi senza data**. Non proporre
scansioni/OCR, nuovi backend cloud o nuove golden run come prerequisiti.

**P0:** applicare un criterio di uscita per *risultato storico*, non numero
di test, CLI, fixture, adapter o task chiusi. Non riaprire T53-T84 salvo
regressione reale che impedisce il nuovo percorso.

## T85-T89: consegne e prove residue al 2026-11-22

| ID | Priorita' | Consegna riscontrata | Cosa resta da dimostrare |
|---|---|---|---|
| T85 | P0 | Governance/routing v3.2 presenti; allineamento documentale dello stato completato il 22 novembre | Chiusura integrale dei gate originari non attestata da questa sessione; configurazione e validator non provano disponibilita' effettiva in `/model` |
| T86 | P0 | Dossier Bendini: 3 documenti esistenti, 2 famiglie di portali e DOCX locale; 5 receipt pregresse, 18 decisioni; 3 quote corrette T61 esatte | Indipendenza archivistica a monte, identita', date e formazione restano aperte; consolidamento offline, nessuna nuova acquisizione T86 |
| T87 | P0 | Vista consegnata con 4 link candidati persona/luoghi/evento, su 3 documenti | I link della nuova vista sono `unreviewed`; identita', identificazione dei luoghi e partecipazione storica non dimostrate |
| T88 | P0 | Un ciclo live chiuso: feedback umano -> piano -> attempt autorizzato -> `no_results` -> review utilita' DUBBIA -> memoria recuperabile | Zero documenti/claim nuovi; lacuna storica aperta. Il ciclo operativo e' provato anche con esito vuoto, l'arricchimento no |
| T89 | P1 | Report completato su 4 casi, con quote-check e review candidate distinte per caso | Un solo caso con feedback live nella coorte; ripetibilita' multi-caso e nuova evidenza da feedback non dimostrate; tempi umani/costi token comparabili non disponibili |

T86-T89 non sono piu' backlog interamente da avviare. Le note di completamento
del planner restano storiche: non equivalgono a fatti verificati o a tutte le
capacita' dimostrate. I criteri originari e i limiti attuali sono nella sezione
T85-T89 di `roadmap/02-technical-roadmap.md`; non servono nuovi layer tecnici
finche' il launcher esistente consente il caso reale.

## Evidenze e ultimo esito

Riferimenti nel data root esterno `P:\Comune\Me.Mo.Ri.a\risultati\runs\`:

- `t86-bendini-dossier-20261121/dossier.md`: 3 documenti e review pregresse;
  T55 resta 3/6 exact nella versione originaria, T61 conserva 3/3 correzioni
  esatte senza sovrascrivere le vecchie receipt.
- `t87-bendini-purocielo-relations-20261121/review-notes.md`: link candidati.
- `t88-bendini-feedback-handoff-20261121/utility-review/closure-audit.json`:
  chiusura del ciclo; l'audit iniziale con review pending resta storico.
- `t89-purocielo-cohort-baseline-20261121/cohort-baseline.md`: Bendini,
  Balboni, Andreoli e Battaglia di Purocielo; completato il confronto, non la
  replica di un feedback live su tutti i casi.
- `bendini-noi-partigiani-formazione-20261122/outcome-audit.json`: follow-up
  del 22 novembre sulla formazione, fonte `noi_partigiani`, attempt
  `nome-completo-wordpress`, query `s=Bendini Ateo`. Un attempt autorizzato,
  zero retry, hit, documenti nuovi e claim nuovi; le due richieste T61 di
  ulteriore evidenza restano aperte. Non e' il ciclo T88 del 21 novembre.
- `bendini-formation-gap-offline-20261122/formation-gap-handoff.md`: scheda
  **fuori procedura, non validata**: prodotta con script diretti e lettura
  `view_image`, non con `memoria`. Conservata come appunto storico, esclusa
  dagli input validati. Il precedente `completed/passed` e' rettificato sotto.
- `bendini-formation-cli-recheck-20261122/`: nuovi output prodotti solo dal
  launcher installato: `text/`, `quote-check-local/`, `quote-check-online/`,
  `quote-check-partigiani/`. Validano i controlli testuali, non la vecchia scheda.
- `bendini-transcription-review-20261124-recto/`: trascrizione manuale del solo
  campo Formazione del recto e receipt, salvate da `memoria` dopo decisione e
  conferma finale dell'utente. Una `accept_transcription`, `review_complete=true`;
  verso escluso, nessuna nuova EvidenceClaim o applicazione canonica.

Verifica mirata del 22 novembre: 41/41 riferimenti SHA-256 corrispondenti fra
manifest T89 (29), chiusura T88 (5) e ultimo outcome (7). Questo controllo
attesta l'integrita' dei riferimenti, non la correttezza storica dei contenuti.
Era un controllo ausiliario con script: non equivale a rianalisi documentale
tramite CLI e non sana il metodo della scheda fuori procedura.

## Rettifica procedurale e rianalisi CLI — 2026-11-22

**Bendini: scheda di riscontro sulla formazione Bianconcini/Bonvicini.**

- **Parte rifatta via CLI:** `memoria documents text-extract` sui tre sidecar
  esistenti: 3/3 documenti estratti. `memoria review evidence-verify` sui claim
  T61 locali (1/1 exact), T61 online (1/1 exact) e set T52 (9/9 exact).
  Il set T52 contiene nove claim: non sono nove prove nuove sulla formazione.
- **Limite:** questi output verificano testo e citazioni; non interpretano
  il manoscritto, non validano dipendenza delle fonti o segnatura archivistica
  e non rendono conforme l'appunto precedente. Nessuna lettura dell'immagine
  viene confermata o riproposta come risultato validato.
- **Blocker rilevato il 22 novembre:** mancava un percorso CLI di trascrizione
  manuale con review; `text-extract` non legge immagini e i workflow OCR/VLM
  esistenti non erano eseguibili nel perimetro autorizzato.
- **Stato della rianalisi del 22 novembre:** `blocked`, verifica `partial`; il vecchio
  `completed/passed` non vale come validazione documentale. Nuovi output CLI
  preservati separatamente; nessuna rete, OCR/VLM, nuova EvidenceClaim,
  decisione umana o modifica canonica.

## Percorso manuale disponibile — 2026-11-24

Su autorizzazione esplicita, implementato `memoria documents transcription-wizard`:
report di acquisizione e ID delle immagini espliciti, verifica di hash/parent/
sidecar, testo inserito da una persona, poi decisione e conferma del reviewer.
Riusato il builder di trascrizione; nessuna scansione o inferenza OCR/VLM.
Draft, ProcessedDocumentText, manifest e receipt sono versionati in un nuovo
run; ID immagine e flag degli originali restano preservati. Una conferma
attesta soltanto la lettura della porzione dichiarata, non un fatto storico.

**Consegna tecnica completata:** 12 test mirati, con subprocess del launcher
su fixture sintetiche, e 14 test di compatibilita' dei contratti esistenti.
Rimosso il blocker di disponibilita' CLI; quella consegna era solo tecnica.
La successiva sessione umana e il suo perimetro sono descritti sotto.
L'appunto fuori procedura resta non validato, escluso dagli input del wizard.

## Review umana della trascrizione del recto completata — 2026-11-24

Sessione guidata esclusivamente tramite `memoria documents transcription-wizard`.
L'utente ha fornito testo e identificativi, confermato la lettura e autorizzato
il salvataggio finale senza nota. Copertura parziale: solo campo Formazione
del recto; reviewer e trascrittore dichiarati coincidono, non autenticati.
Il verso e' escluso su richiesta dell'utente, senza trascrizione o attribuzione
della sua annotazione. La prima sessione su due immagini e' stata annullata
senza scritture; la sessione sul solo recto e' stata salvata nel nuovo run.

Artifact: `image-1.text.json`, `transcription-draft.json`,
`transcription-manifest.json`, `transcription-review-receipt.json` nel run
esterno sopra indicato. Il launcher ha verificato i binding/hash degli input
e restituito `review_complete=true`, una decisione, flag claim/promozione/
scrittura canonica/identita' risolta/machine pass tutti falsi. Non e' una
decisione storica di accettazione del claim, ne' una validazione retroattiva
della scheda fuori procedura o una soluzione dei conflitti T52/T61.

**Prossimo candidato, non avviato:** confronto versionato fra questa lettura
umana e l'attestazione del portale per un'eventuale nuova decisione storica,
conservando gli ID delle rispettive fonti e le receipt pregresse. Procedura
nel playbook. Nessun nuovo claim o task aperto automaticamente; nessuna
ricerca o OCR/VLM, T41 resta sospeso.

## Avvio quotidiano (solo 3 passi)

1. Leggi questo file e `AGENTS.md`.
2. Esegui `python memoria-bootstrap/planning/current-work-summary.py`.
3. Se nessun lavoro aperto coerente: valuta una lacuna residua T86-T89 in base
   al primo *blocco documentale reale*, senza riavviare le consegne concluse;
   registra nel planner solo quando avvii la slice autorizzata.

Per ricerche reali, leggere `docs/playbooks/online-source-research-review.md`.
Per il feedback, `docs/playbooks/codex-person-profile-feedback-loop-core.md`.
Per modello/delega, `docs/model-routing-policy.md` (v3.2).

## Stop non negoziabili

Nessuna ricerca live prima di autorizzazione per fonte/query/attempt; nessuna
review fittizia; nessuna promozione automatica da search result a documento o
claim; nessuna canonizzazione, risoluzione conflitti o pubblicazione autonoma.
Se mancano data root, documento, review o autorizzazione: esito `blocked`
con prova del blocco e prossimo passo eseguibile, non nuovo micro-task tecnico.
