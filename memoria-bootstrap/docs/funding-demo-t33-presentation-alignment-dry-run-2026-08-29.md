# T33 Presentation Alignment Dry Run

Data: 2026-08-29

Stato: prova asciutta repository-only dopo revisione umana approvata. Non
autorizza pubblicazione, bando, importo, finanziatore, ProfilePatch, verified
facts canonici o modifiche ai profili canonici.

## Scopo

Questa nota verifica che l'entrypoint della presentazione T33 sia stato
allineato meccanicamente ai due testi approvati nel verbale umano del
2026-08-28:

- blocco 3, Cinque storie;
- blocco 5, Limiti e non pubblicabilita'.

La prova non legge e non modifica il data root esterno. Non esegue pipeline,
OCR, ricerche live o impaginazione finale.

## Controlli

| Controllo | Esito | Nota |
|---|---|---|
| Blocco 3 allineato | pass | L'entrypoint usa il testo approvato su persone, luoghi, documenti ed eventi provenienti da fonti diverse e disomogenee. |
| Blocco 5 allineato | pass | L'entrypoint esplicita suggerimenti del motore, revisione degli storici, fonti da verificare e chiusura del ciclo solo dopo confronto e decisioni documentate. |
| Distinzione perimetri | pass | Patrimonio di 57 profili, coorte pilota di 5 e golden run di 3 casi restano distinti. |
| Guardrail editoriali | pass | La presentazione resta non pubblicabile e senza bando, importo o finanziatore. |
| Modifiche canoniche | pass | Nessuna ProfilePatch applicata, nessun verified fact canonico creato e nessun profilo canonico modificato. |

## Verdetto

L'entrypoint e' coerente con il verbale umano `approved_for_layout` del
2026-08-28 per i soli blocchi narrativi 3 e 5. Il materiale puo' passare alla
preparazione del layout interno non pubblicabile.

## Stop Condition

Stop condition raggiunta: testi approvati presenti nell'entrypoint, coerenza
narrativa verificata in asciutto e guardrail confermati senza pubblicazione,
senza nuove fonti e senza modifiche canoniche.
