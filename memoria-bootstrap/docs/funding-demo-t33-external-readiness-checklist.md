# T33 External Readiness Checklist

Data: 2026-08-09

Stato: checklist riallineata alla golden run canonica a tre casi promossa.
La demo tecnica e' pronta per uso interno; la prova asciutta del racconto in
sei schermate e' completata, ma resta una nuova revisione umana prima dell'uso
esterno. Il blocco sulla pubblicazione storica resta invariato.

## Scope

Questa checklist traduce il go/no-go generato nella run canonica in una lettura
editoriale usabile prima di una presentazione esterna. Non sostituisce il
descriptor, non approva decisioni storiche e non rende pubblicabile nessuna
scheda.

Vincoli rispettati:

- nessuna scrittura nel data root esterno;
- nessuna pipeline, OCR o ricerca live;
- nessuna modifica a profili canonici;
- nessuna promozione di claim o verified facts canonici;
- nessuna applicazione di `ProfilePatch`;
- nessuna copia di documenti reali nei repository.

## Verdetto

| Livello | Stato | Significato |
|---|---|---|
| Presentazione finanziatori | `pending_human_review` | La prova asciutta delle sei schermate e' passata; il racconto non e' ancora approvato per uso esterno. |
| Demo interna tecnica | `ready_for_internal_demo` | Il descriptor attivo conferma run, artefatti e safety flag preview-only. |
| Pubblicazione storica | `blocked` | Restano decisioni storiche pending e output preview non approvati. |
| Schede canoniche | `not_authorized` | Nessuna patch e nessun fatto canonico devono essere applicati da T33. |

## Esito della prima revisione umana

La review del 2026-07-18 ha rilevato due problemi distinti:

- la sequenza di 14 materiali richiede troppa conoscenza interna del motore;
- il racconto Andreoli/Balboni non rende visibile che il workspace contiene 57
  profili e che la run pilota dispone gia' di 5 schede modello.

La correzione mantiene separati il linguaggio tecnico e quello finanziatori, ma
non crea due lineage. Andreoli, Balboni e Bendini sono ora nella stessa golden
run canonica promossa; resta da verificare che il racconto orale sia chiaro,
breve e non trasformi gli output preview in risultati pubblicabili.

Il valore del pacchetto esterno e' mostrare una prova controllata:

```text
fonti eterogenee
  -> documenti identificati
  -> claim con provenance
  -> riconciliazione multi-fonte
  -> decisione storica
  -> verified fact e ProfilePatch preview
  -> feedback loop con esito auditabile
```

## Gate approvabili

| Gate | Stato | Evidenza |
|---|---|---|
| Golden run corrente unica dichiarata | `pass` | `memoria_mvp_demo.active.json` punta a `funding-demo-golden-3cases-v1-pipeline` |
| Golden run canonica a tre casi | `pass` | 1 profilo principale, 2 complementari e 5/5 documenti nella run promossa |
| Merge multi-fonte visibile | `pass` | `mvp_demo_reconciliation_table.md`, 3 famiglie fonte e 5/5 documenti coperti |
| Decisione storica presente | `pass_with_pending` | `historian_review/review_decisions.validation.md`: 15 accettate, 68 pending |
| Verified facts solo preview | `pass` | `historian_review/verified_facts.preview.md` |
| ProfilePatch solo preview | `pass` | `historian_review/profile_patch.preview.md` |
| Feedback loop chiuso | `pass` | `historian_review/feedback_loop_outcome.t31-demo.md`, outcome `needs_manual_review` |
| Dossier e indice presenti | `pass` | `funding_package_index.md`, `mvp_funding_dossier.md` |
| Brief editoriale esterno presente | `pass` | `funding-demo-t33-external-brief.md` |
| Roadmap uso fondi presente | `pass` | `funding-demo-t33-funding-roadmap.md` |
| Pubblicabilita' storica | `blocked` | `mvp_go_no_go_checklist.md`, stato `go_with_review_blockers` |

## Gate comunicativi T33b

| Gate | Stato | Evidenza o azione |
|---|---|---|
| Golden run e presentazione separate | `pass_draft` | `funding-demo-t33-presentation-entrypoint.md` |
| Unico `run_id` per tecnica e presentazione | `pass` | `funding-demo-golden-3cases-v1-pipeline` |
| Coorte pilota di 5 profili visibile | `pass_draft` | schermata 3 del nuovo entrypoint |
| Patrimonio di 57 profili contestualizzato | `pass_draft` | dichiarato come perimetro disponibile, non come risultato |
| Percorso ridotto a sei schermate | `pass_draft` | nuovo entrypoint della presentazione |
| Prova orale comprensibile | `pass_dry_run` | prova asciutta completata; resta la revisione umana |
| Via libera alla presentazione esterna | `blocked` | richiede nuova approvazione umana |

## Condizioni per presentare

Prima di una nuova revisione umana, l'operatore deve:

1. verificare lo stato attivo con `funding-demo-t33-current-state-operator-note.md`;
2. aprire da `funding-demo-t33-presentation-entrypoint.md`;
3. mostrare il patrimonio disponibile e la coorte pilota prima del caso tecnico;
4. usare i tre casi della stessa golden run per mostrare capacita' differenti;
5. tenere comandi, path e stati interni nell'appendice tecnica;
6. distinguere sempre patrimonio, pilota, review e pubblicazione;
7. fermarsi prima di bando, importo e finanziatore.

## Frasi consentite

- Me.Mo.Ri.A dimostra un metodo tracciabile per trasformare fonti eterogenee in
  evidenze revisionabili.
- La golden run conserva provenance, divergenze e decision trail.
- Il pacchetto e' finanziabile come demo controllata, ma non e' una
  pubblicazione storica.
- Il finanziamento serve a scalare review, trattamento documentale,
  riconciliazione e confezionamento curatoriale.

## Frasi da evitare

- Le schede sono pronte per la pubblicazione.
- Il sistema ha risolto automaticamente i conflitti storici.
- `needs_manual_review` dimostra presenza o assenza di un fatto.
- Le patch possono essere applicate senza revisione.
- Il finanziamento serve a sostituire storici, archivi o curatori.

## Blocker dichiarati

| Blocker | Effetto | Come si chiude dopo T33 |
|---|---|---|
| Review incompleta: 68 pending nella golden run attiva; 104 pending nella coorte pilota usata come contesto | Impedisce di presentare schede o claim come pubblicabili. | Sessione di review storica dedicata, con decisioni registrate e nuovo go/no-go. |
| Output preview non canonici | Impedisce promozione automatica a profili o fatti verificati. | Incremento dedicato con backup, audit trail e approvazione curatoriale. |
| Esito feedback `needs_manual_review` | Dimostra il loop, non una conclusione storica. | Nuova review della fonte/sessione collegata e registrazione dell'esito. |

## Uso nel walkthrough

Questa checklist va letta dopo:

1. `funding-demo-t33-package-entrypoint.md`;
2. `funding-demo-t33-demo-case-card.md`;
3. `funding-demo-t33-evidence-flow-diagram.md`;
4. `funding-demo-t33-funding-roadmap.md`;
5. `funding-demo-t33-external-brief.md`.

Serve come controllo finale prima di aprire o inviare il pacchetto a
finanziatori.

## Validazione

Validazione read-only richiesta:

```powershell
cd memoria-engine
.\.venv\Scripts\memoria.exe mvp demo --data-root "P:\Comune\Me.Mo.Ri.a"
```

Esito atteso:

- descriptor presente e JSON valido;
- status `ready_for_internal_demo`;
- ledger standard attivo;
- 3 famiglie fonte coperte;
- 5/5 documenti selezionati coperti;
- safety flag preview-only confermate;
- nessun file del data root esterno modificato.
