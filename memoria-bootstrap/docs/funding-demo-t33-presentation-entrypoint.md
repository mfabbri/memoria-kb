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
Me.Mo.Ri.A parte dalle persone, in particolare dai partigiani, ma non si ferma
alle biografie. Raccoglie e mette in relazione anche luoghi, eventi e documenti,
per ricostruire contesti e percorsi di memoria.
```

I 57 profili e le 18 fonti abilitate restano il perimetro disponibile, non un
insieme di biografie gia' concluse.

### 3. La coorte pilota

Messaggio:

```text
Cinque storie come punto di partenza. Me.Mo.Ri.A mette in relazione
informazioni su persone, luoghi, documenti ed eventi provenienti da fonti
diverse, che usano criteri e linguaggi non omogenei, per costruire un percorso
di ricerca chiaro e verificabile.
```

I numeri e gli stati della coorte restano nel percorso tecnico: nelle sei
schermate conta il valore del percorso di ricerca, non il glossario interno.

### 4. Un caso concreto: Dino Andreoli

```text
Nel caso di Dino Andreoli, fonti diverse riportano lo stesso nome e aprono piste
di ricerca sul suo contesto. Alcune informazioni coincidono, altre richiedono
ancora confronto. Me.Mo.Ri.A non sceglie automaticamente: mantiene visibili
fonti, collegamenti e dubbi, perche' sia lo storico a ricostruire il quadro.
```

Questo esempio usa soltanto i collegamenti persona-documento confermati nella
golden run e le divergenze documentate; non presenta dati biografici, date o
ricostruzioni come conclusioni storiche pubblicabili.

Per la composizione interna della schermata con le tre tracce selezionate usare
memoria-bootstrap/docs/funding-demo-t33-andreoli-visual-layout.md.
Per la composizione complessiva usare anche il brief interno non pubblicabile
memoria-bootstrap/docs/funding-demo-t33-internal-layout-brief.md.

### 5. Cosa dimostra e cosa non dimostra

Il lavoro mostra un metodo e primi risultati. I suggerimenti del motore e la
revisione degli storici aprono nuove piste e indicano nuove fonti da verificare.
Un ciclo di ricerca si chiude solo quando le fonti disponibili sono state
confrontate, le decisioni documentate e lo storico ritiene concluse le verifiche
prioritarie. Dubbi e lacune restano visibili; nessun contenuto diventa
pubblicabile senza fonti tracciabili e validazione umana.

### 6. Il passo successivo

Messaggio:

```text
Stiamo dando una forma comune alle informazioni su persone, luoghi ed eventi,
mantenendo sempre il legame con le fonti. Cosi' diventa possibile raccontare
storie piu' complete, trovare collegamenti prima nascosti e aprire nuove
riflessioni, senza perdere il rigore della verifica storica.
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
