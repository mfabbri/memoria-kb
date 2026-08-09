# T33 Presentation Dry Run

Data: 2026-08-09

Stato: prova asciutta narrativa; non approva la presentazione esterna e non
autorizza bando, importo, finanziatore o pubblicazione.

## Scopo

Questa nota registra una prova asciutta del racconto T33 in sei schermate,
usando l'entrypoint della presentazione e i materiali editoriali gia'
riallineati alla golden run canonica a tre casi.

La prova controlla solo coerenza narrativa e guardrail. Non legge o modifica il
data root esterno, non applica `ProfilePatch`, non crea verified facts canonici
e non modifica profili canonici.

## Perimetro verificato

| Elemento | Esito |
|---|---|
| Run canonica dichiarata | `funding-demo-golden-3cases-v1-pipeline` |
| Separazione golden run/presentazione | pass |
| Coorte pilota visibile | pass, con conteggi esplicitati come pilota |
| Tre casi in profondita' | pass con attenzione a non promettere esiti identici per ogni caso |
| Guardrail preview-only | pass |
| Bando, importo, finanziatore | assenti |
| Pubblicabilita' | esplicitamente negata |

## Esito per schermata

| Schermata | Verdetto | Nota di prova |
|---|---|---|
| 1. Il problema | pass | Apre sul problema culturale e non su comandi, JSON o artefatti tecnici. |
| 2. Il patrimonio gia' disponibile | pass | I 57 profili sono presentati come patrimonio disponibile, non come schede complete. |
| 3. La coorte pilota | pass | I 5 profili, 13 documenti, 24 link, 55 claim e 114 decisioni sono leggibili come scala pilota. |
| 4. Tre casi in profondita' | pass con cautela | Andreoli, Balboni e Bendini hanno ruoli distinti; il testo ora evita di imporre fact, patch e feedback completi a ogni caso. |
| 5. Cosa dimostra e cosa non dimostra | pass | La schermata aumenta credibilita' dichiarando decisioni pending, output preview e assenza di pubblicazione. |
| 6. Il passo successivo | pass | Chiude sul lavoro curatoriale ripetibile senza introdurre bando, importo o finanziatore. |

## Correzioni applicate durante la prova

- Nel blocco dei numeri, i conteggi `10 accettate, 104 pending` e `8 verified
  facts preview` sono stati marcati come riferiti alla coorte pilota.
- Aggiunto il conteggio della golden run a tre casi: `15 accettate, 68
  pending`.
- La schermata 4 ora parla di griglia di lettura comune, non di esiti identici
  per ogni profilo.
- La schermata 5 evita di associare tutte le decisioni pending a un solo
  perimetro.

## Verdetto

La presentazione e' pronta per una revisione umana del racconto, non per
presentazione esterna finale. Il passaggio successivo deve essere una revisione
umana dei sei blocchi narrativi con attenzione a:

- tenere separati coorte pilota, golden run a tre casi e patrimonio disponibile;
- non trasformare output preview in fatti pubblicabili;
- non introdurre bando, importo o finanziatore prima dell'approvazione del
  racconto.

## Stop condition

Stop condition raggiunta: la prova asciutta produce un verdetto per tutte le
sei schermate, segnala le cautele residue e conferma che non sono state eseguite
scritture nel data root esterno, applicazioni di patch, promozioni canoniche o
pubblicazioni.
