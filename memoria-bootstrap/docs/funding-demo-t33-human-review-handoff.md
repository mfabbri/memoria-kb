# T33 Human Review Handoff

Data: 2026-08-25

Stato: traccia per revisione umana del racconto; non approva la presentazione
esterna e non autorizza bando, importo, finanziatore o pubblicazione.

## Scopo

Questo handoff prepara la revisione umana della presentazione T33 in sei
schermate dopo la prova asciutta narrativa. Serve a raccogliere un verdetto
esplicito sui blocchi narrativi prima di impaginazione finale o uso esterno.

La revisione riguarda solo il racconto. Non legge o modifica il data root
esterno, non applica `ProfilePatch`, non crea verified facts canonici e non
modifica profili canonici.

## Materiali da leggere

Prima della revisione compilare il preflight repository-only: `funding-demo-t33-human-review-preflight.md`. Il preflight controlla la prontezza dei materiali ma non sostituisce il verdetto umano.


1. `funding-demo-t33-presentation-entrypoint.md`
2. `funding-demo-t33-presentation-dry-run.md`
3. `funding-demo-t33-current-state-operator-note.md`

L'appendice tecnica va aperta solo se il revisore chiede di verificare un
percorso operativo o un artefatto specifico.

## Domande di revisione

| Blocco | Domanda | Esito atteso |
|---|---|---|
| Problema | Il problema culturale e' chiaro senza partire da comandi o artefatti? | approva / rivedi |
| Patrimonio | Il racconto include persone, luoghi, eventi e documenti senza presentare i 57 profili come schede complete? | approva / rivedi |
| Cinque storie | Le cinque storie fanno capire l'utilita' della ricerca senza ricorrere a stati o glossario tecnico? | approva / rivedi |
| Caso concreto | Andreoli rende visibile un collegamento tra fonti e un dubbio documentato, senza affermare fatti non pubblicabili? | approva / rivedi |
| Limiti | Il lavoro in corso e la non pubblicabilita' aumentano fiducia invece di sembrare una scusa tecnica? | approva / rivedi |
| Passo successivo | La standardizzazione di persone, luoghi ed eventi e' chiara e resta ancorata alle fonti? | approva / rivedi |

## Blocchi da non superare

- Non descrivere schede preview come pubblicabili.
- Non fondere coorte pilota, golden run a tre casi e patrimonio disponibile.
- Non aggiungere bando, importo o finanziatore.
- Non promettere completamento dei 57 profili.
- Non applicare `ProfilePatch`.
- Non creare verified facts canonici.
- Non modificare profili canonici.

## Esiti ammessi

| Esito | Significato | Prossimo passo |
|---|---|---|
| `approved_for_layout` | Il racconto puo' passare a impaginazione, restando non pubblicabile. | Preparare layout o scaletta visuale senza bando/importo/finanziatore. |
| `revise_before_layout` | Il racconto e' valido ma uno o piu' blocchi richiedono riscrittura. | Aggiornare solo le schermate indicate e ripetere prova asciutta. |
| `blocked` | Il racconto confonde prova tecnica, preview o pubblicazione. | Fermare T33 presentazione e riaprire il contratto narrativo. |

Nessuno di questi esiti autorizza pubblicazione storica, promozione di claim,
applicazione di patch o modifica del descriptor attivo.

## Nota per il verbale

Il verbale della revisione deve indicare:

- data e revisore;
- esito scelto;
- blocchi approvati;
- blocchi da correggere;
- conferma esplicita che non sono stati introdotti bando, importo,
  finanziatore o pubblicazione.

Per raccogliere il verbale usare funding-demo-t33-human-review-response-template.md. Il template resta vuoto finche non viene compilato da un revisore umano e non autorizza da solo impaginazione, pubblicazione o modifica di artefatti canonici.
