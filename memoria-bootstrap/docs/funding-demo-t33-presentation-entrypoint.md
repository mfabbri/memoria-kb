# T33 Funding Presentation Entrypoint

Data: 2026-08-09

Stato: bozza T33 riallineata alla golden run canonica a tre casi promossa il
2026-08-09. La presentazione resta una demo revisionabile e non pubblicabile:
puo' ora usare la run `funding-demo-golden-3cases-v1-pipeline`, ma deve ancora
essere provata come racconto in sei schermate prima di bando, importo o
finanziatore.

## Scopo

Questa e' la pagina da usare per costruire e provare la presentazione ai
finanziatori. Non e' la domanda di finanziamento e non sostituisce la golden
run tecnica.

La presentazione deve rispondere, in questo ordine, a tre domande:

1. quale problema culturale affronta Me.Mo.Ri.A;
2. cosa e' gia' stato dimostrato;
3. quale lavoro resta da rendere ripetibile.

Non deve iniziare da comandi, JSON, nomi di artefatti o safety flag. Questi
restano disponibili nell'appendice tecnica.

## I due oggetti

| Oggetto | Pubblico | Funzione | Perimetro |
|---|---|---|---|
| Golden run tecnica | team, storici, valutatori tecnici | provare provenance, riconciliazione, review, patch preview e feedback loop | 3 casi selezionati e 5 documenti nella stessa run canonica |
| Presentazione finanziatori | decisori culturali e finanziatori | mostrare patrimonio disponibile, risultati del pilota, valore del metodo e lavoro ancora necessario | stessa run canonica per i 3 casi; coorte pilota di 5 profili e patrimonio di 57 come contesto |

I due oggetti hanno pubblico e linguaggio differenti, non lineage differenti.
La presentazione usa gli stessi tre casi della golden run e aggiunge il contesto
di ampiezza senza sostenere che tutti i 57 profili siano stati elaborati o
revisionati.

## Numeri da presentare

I numeri seguenti derivano da viste read-only del workspace e dagli artefatti
gia' presenti nella run canonica.

| Livello | Numero | Significato corretto |
|---|---:|---|
| Patrimonio indicizzato | 57 profili caricati | perimetro disponibile, non 57 schede complete |
| Fonti online | 18 abilitate | capacita' di ricerca configurata, non copertura completa dei 57 profili |
| Coorte pilota | 5 profili | casi sui quali esistono schede modello e materiali di review |
| Materiale pilota | 13 documenti collegati | documenti raccordati ai profili nel ledger del pilota |
| Analisi pilota | 24 link persona-documento e 55 claim candidati | segnali da sottoporre a controllo storico |
| Lavoro curatoriale pilota | 114 item di review | coda esplicita e misurabile sui 5 profili pilota |
| Decisioni registrate nel pilota | 10 accettate, 104 pending | review avviata, non completata sulla coorte pilota |
| Risultato controllato nel pilota | 8 verified facts preview | fatti non canonici e non pubblicabili della coorte pilota |
| Review della golden run a tre casi | 15 accettate, 68 pending | profondita' dimostrativa, ancora non pubblicabile |

## Presentazione in sei schermate

### 1. Il problema

Messaggio:

```text
La memoria storica locale e' distribuita fra documenti, tabelle, archivi e
fonti online che non parlano la stessa lingua. Ricostruire una persona richiede
tempo, confronto fra fonti e decisioni che devono restare verificabili.
```

Mostrare solo il problema e i beneficiari: storici, archivi, istituti culturali
e comunita' locali.

### 2. Il patrimonio gia' disponibile

Messaggio:

```text
Il workspace contiene 57 profili caricati e 18 fonti online abilitate. Questo
e' il perimetro di partenza, non un insieme di biografie gia' concluse.
```

Questa schermata mostra l'ampiezza potenziale senza confonderla con il risultato
del pilota.

### 3. La coorte pilota

Messaggio:

```text
Su cinque profili pilota il sistema ha collegato 13 documenti, prodotto 24 link
persona-documento e 55 claim candidati, trasformandoli in una coda di 114
decisioni storiche esplicite.
```

Mostrare i cinque casi come un piccolo portafoglio con stati differenti:

- 4 profili `ready_for_review`;
- 1 profilo `needs_signal_review`;
- 2 profili con decisioni accettate e verified facts preview;
- 3 profili che rendono visibile il lavoro ancora necessario.

Fonte operativa:

```text
P:\Comune\Me.Mo.Ri.a\risultati\runs\prova-preview-profili-5-reviewed-01-pipeline\mvp_pilot_cards_digest.md
```

### 4. Tre casi in profondita'

I tre casi devono mostrare capacita' differenti:

| Caso | Ruolo nel racconto | Condizione |
|---|---|---|
| Andreoli | catena completa e feedback loop | presente nella golden run canonica a tre casi |
| Balboni | corroborazione e confronto multi-fonte | presente nella golden run canonica a tre casi |
| Bendini | decisione su contesto incerto e limiti documentali visibili | presente nella golden run canonica a tre casi, con review ancora parziale |

Per ogni caso mantenere la stessa griglia di lettura, senza forzare lo stesso
esito su tutti i profili:

```text
documento
  -> claim con fonte
  -> confronto con altri documenti
  -> decisione dello storico quando presente
  -> esito preview quando presente
  -> proposta di aggiornamento non applicata quando presente
  -> nuova domanda di ricerca tracciata o pending esplicito
```

Non aprire tutti gli artefatti. Per ciascun caso mostrare al massimo una
divergenza o informazione significativa, una decisione e il relativo esito
preview. Il dettaglio completo resta nel percorso tecnico.

### 5. Cosa dimostra e cosa non dimostra

| Dimostrato | Non ancora dimostrato |
|---|---|
| Collegamento auditabile fra profili, documenti e claim | trattamento completo dei 57 profili |
| Confronto multi-fonte senza cancellare divergenze | schede storiche pubblicabili |
| Decisioni umane registrate | completamento delle decisioni pending del pilota e della golden run |
| Fatti e patch prodotti in preview | applicazione automatica ai profili canonici |
| Feedback di ricerca con esito tracciato | ciclo operativo ripetuto su una coorte estesa |

Questa schermata deve aumentare credibilita', non giustificare tecnicamente il
progetto.

### 6. Il passo successivo

Messaggio:

```text
Il motore ha dimostrato la catena su una coorte controllata. Il passo successivo
e' trasformarla in una pratica curatoriale ripetibile: selezione dei profili,
trattamento documentale, review storica, misurazione della qualita' e produzione
di dossier approvati.
```

In questa fase non inserire ancora un bando, un importo o un finanziatore. La
presentazione deve prima ottenere approvazione sul racconto e sulla prova.

## Materiali dei due percorsi

Prima di lavorare sulla presentazione, leggere la nota operativa corrente:

```text
memoria-bootstrap/docs/funding-demo-t33-current-state-operator-note.md
```

### Percorso presentazione

Usare nell'ordine:

1. questo entrypoint;
2. `funding-demo-t33-current-state-operator-note.md` per verificare quale run e'
   attiva e quali guardrail restano validi;
3. `funding-demo-t33-external-brief.md` come sorgente editoriale;
4. `funding-demo-t33-demo-case-card.md` come base dei primi due casi;
5. `funding-demo-t33-three-case-runbook.md` come storico della promozione a una
   sola golden run a tre casi;
6. `funding-demo-t33-funding-roadmap.md` solo per la schermata finale.

### Appendice tecnica

Usare solo su richiesta di approfondimento:

1. `funding-demo-t33-current-state-operator-note.md`;
2. `funding-demo-t33-package-entrypoint.md`;
3. `funding-demo-t33-evidence-flow-diagram.md`;
4. `funding-demo-t33-external-readiness-checklist.md`;
5. artefatti della golden run nel workspace operativo.

## Criteri per la prossima revisione umana

La presentazione puo' passare alla fase di impaginazione solo se:

- i due oggetti restano chiaramente separati;
- i cinque profili pilota sono visibili come coorte;
- i 57 profili sono dichiarati come patrimonio disponibile, non come risultato;
- i tre casi hanno ruoli differenti e superano i criteri di profondita';
- tutti gli artefatti mostrati puntano allo stesso `run_id` canonico;
- comandi, percorsi e stati interni restano fuori dalle sei schermate;
- entro due minuti e' comprensibile cosa esiste oggi e cosa manca;
- nessuna scheda preview e' descritta come pubblicabile.

## Vincoli

- Nessun dato reale aggiunto ai repository: questo documento riporta solo
  conteggi aggregati e riferimenti gia' documentati.
- Nessuna scrittura nel data root esterno.
- Nessuna pipeline, OCR o ricerca live.
- Nessuna modifica a profili canonici.
- Nessuna applicazione di `ProfilePatch` o promozione di verified facts.
