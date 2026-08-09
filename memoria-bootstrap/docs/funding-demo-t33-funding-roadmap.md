# T33 Funding Roadmap

Data: 2026-08-09

Stato: roadmap uso fondi riallineata alla golden run canonica promossa a tre
casi; materiale editoriale preview-only per il pacchetto finanziatori.

## Scope

Questo documento spiega cosa dimostra oggi la golden run, cosa richiede
finanziamento e quali risultati misurabili attendersi. E' una roadmap di
sviluppo, non una promessa di pubblicazione automatica.

Vincoli rispettati:

- nessuna scrittura nel data root esterno;
- nessuna pipeline, OCR o ricerca live;
- nessuna modifica a profili canonici;
- nessuna promozione di claim o verified facts canonici;
- nessuna applicazione di `ProfilePatch`;
- nessuna copia di documenti reali nei repository.

## Punto di partenza

Golden run:

```text
funding-demo-golden-3cases-v1-pipeline
```

Descrittore:

```text
P:\Comune\Me.Mo.Ri.a\database\memoria_mvp_demo.active.json
```

La demo e' pronta per uso interno come prova finanziabile:

- 1 profilo principale e 2 profili complementari;
- 5 documenti selezionati;
- 3 famiglie fonte coperte;
- review parziale con 15 decisioni accettate e 68 pending;
- 1 verified fact preview;
- 1 ProfilePatch preview non applicata;
- feedback loop T31 chiuso con esito auditabile `needs_manual_review`;
- `publication_ready=false`.

## Capacita' attuali

| Area | Capacita' dimostrata oggi | Evidenza |
|---|---|---|
| Golden run unica | Tutti gli artefatti demo puntano a una run canonica dichiarata. | `memoria_mvp_demo.active.json` |
| Provenance | Ogni claim resta collegato a documento, famiglia fonte e metodo. | `mvp_demo_reconciliation_table.md` |
| Merge multi-fonte | Fonti locali e online contribuiscono alla stessa scheda di lavoro senza cancellare divergenze. | `legacy_csv`, `local_docx`, `partigiani_italia` |
| Review storica | Decisioni umane sono registrate con reviewer, stato e collegamento all'evidenza; la review resta parziale. | `review_decisions.validation.md` |
| Preview facts | Alcune decisioni producono fatti preview non canonici. | `verified_facts.preview.md` |
| Patch preview | Il sistema propone aggiornamenti senza applicarli. | `profile_patch.preview.md` |
| Feedback loop | Una lacuna produce una ricerca tracciata e un esito auditabile. | `feedback_loop_outcome.t31-demo.md` |
| Guardrail editoriali | Il pacchetto distingue automatico, revisionato e pubblicabile. | `mvp_go_no_go_checklist.md` |

## Limiti attuali

| Limite | Perche' conta | Stato |
|---|---|---|
| Decisioni pending | La demo e' finanziabile, ma non pubblicabile: restano decisioni storiche da completare. | `go_with_review_blockers` |
| Perimetro piccolo | Il caso dimostra il metodo su pochi profili e documenti, non ancora su un corpus esteso. | MVP controllato |
| Output preview | Verified facts e ProfilePatch non sono fatti o patch canonici. | Safety flag attivi |
| Feedback manuale | Il loop T31 registra un esito `needs_manual_review`, non una nuova acquisizione automatica. | Auditabile, non conclusivo |
| Confezionamento esterno | Il dossier e i materiali sono riallineati alla run promossa, ma il racconto in sei schermate richiede prova asciutta e review umana. | T33 ancora aperto |

## Uso dei fondi

| Linea di investimento | Obiettivo | Risultato atteso |
|---|---|---|
| Revisione storica assistita | Trasformare decisioni pending in decisioni curate, mantenendo incertezza e conflitti quando necessari. | Pacchetti review completati per casi prioritari, con audit trail. |
| Trattamento documentale controllato | Estendere il percorso documenti -> claim -> evidence store senza scansioni massive non governate. | Nuovi documenti incorporati con provenance e quality gate. |
| Riconciliazione multi-fonte | Rafforzare regole e viste per confrontare fonti eterogenee senza appiattirle. | Schede di lavoro piu' leggibili per storico e curatore. |
| Feedback loop operativo | Rendere ripetibile il ciclo review -> nuova ricerca -> esito -> memoria di ricerca. | Riduzione delle ricerche duplicate e tracciamento degli esiti negativi o incerti. |
| Confezionamento curatoriale | Preparare materiali presentabili per istituti, musei, scuole e partner. | Dossier esterni, walkthrough e schede revisionate chiaramente non automatiche. |
| Infrastruttura condivisibile | Portare il workspace verso backend pluggable e collaborazione controllata. | Accesso piu' stabile e auditabile, senza copiare dati reali nei repository. |

## Risultati attesi

### Entro 1-2 mesi

- completare la review storica del caso demo;
- rifinire il dossier finanziatori esterno;
- preparare una checklist di readiness approvabile;
- consolidare il protocollo editoriale che distingue preview, review e
  pubblicazione.

### Entro 3-6 mesi

- estendere il metodo a un primo insieme controllato di profili prioritari;
- ripetere il feedback loop su piu' casi, includendo anche `no_results`
  tracciati quando pertinenti;
- stabilizzare viste e report di riconciliazione multi-fonte;
- ridurre dipendenza da percorsi manuali non documentati.

### Entro 6-12 mesi

- trasformare il metodo in una pipeline curatoriale robusta e replicabile;
- integrare nuove fonti solo con criteri di qualita', provenance e sostenibilita';
- preparare pacchetti tematici per partner istituzionali;
- valutare backend condivisi senza spostare dati reali in Git.

## Attuale, finanziato, visione

| Piano | Descrizione | Cosa non promette |
|---|---|---|
| Capacita' attuale | MVP locale con golden run unica, merge multi-fonte, review, patch preview e feedback loop auditabile. | Non produce schede pubblicabili definitive. |
| Sviluppo finanziato | Estensione controllata del metodo a piu' profili, documenti e cicli review, con strumenti piu' ergonomici per storici e curatori. | Non elimina la decisione umana e non risolve automaticamente conflitti storici. |
| Visione di piattaforma | Ambiente condivisibile per memoria storica, ricerca documentale e pubblicazione curatoriale tracciabile. | Non e' un motore generativo che sostituisce fonti, storici o istituzioni. |

## Messaggio finanziatori

Il finanziamento non serve a trasformare una demo in una fabbrica automatica di
biografie. Serve a scalare un metodo gia' provato in piccolo:

```text
fonte identificata
  -> claim tracciabile
  -> riconciliazione visibile
  -> decisione storica
  -> patch preview
  -> nuova ricerca o esito documentato
```

Il valore e' mantenere questa catena leggibile quando aumentano profili, fondi,
istituti e documenti.

## Uso nel walkthrough

Questa roadmap soddisfa i criteri T33:

```text
roadmap dell'uso dei fondi e risultati attesi
distinzione esplicita fra capacita' attuali, sviluppo finanziato e visione
```

Ordine consigliato:

1. mostrare la golden run con `memoria mvp demo`;
2. raccontare il caso con `funding-demo-t33-demo-case-card.md`;
3. mostrare il flusso con `funding-demo-t33-evidence-flow-diagram.md`;
4. chiudere con questa roadmap per spiegare cosa finanziare.

## Guardrail

- Non presentare la roadmap come impegno a pubblicare automaticamente schede.
- Non usare il finanziamento per bypassare review storica o provenance.
- Non aggiungere fonti indiscriminatamente senza criteri di qualita'.
- Non trasformare output preview in fatti canonici senza workflow dedicato.

## Validazione

Validazione read-only prevista:

```powershell
cd memoria-engine
.\.venv\Scripts\memoria.exe mvp demo --data-root "P:\Comune\Me.Mo.Ri.a"
```

Esito atteso:

- descriptor presente e JSON valido;
- status `ready_for_internal_demo`;
- safety flag preview-only confermate;
- nessun file del data root esterno modificato.
