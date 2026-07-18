# T33 External Readiness Checklist

Data: 2026-07-16

Stato: sotto-incremento T33 completato; checklist approvabile per presentazione
finanziatori, con blocco esplicito sulla pubblicazione storica.

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
| Demo finanziatori | `approvabile_con_guardrail` | Il pacchetto puo' essere usato per mostrare il metodo, i limiti e il bisogno di finanziamento. |
| Demo interna tecnica | `ready_for_internal_demo` | Il descriptor attivo conferma run, artefatti e safety flag preview-only. |
| Pubblicazione storica | `blocked` | Restano decisioni storiche pending e output preview non approvati. |
| Schede canoniche | `not_authorized` | Nessuna patch e nessun fatto canonico devono essere applicati da T33. |

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
| Golden run unica dichiarata | `pass` | `memoria_mvp_demo.active.json` |
| Perimetro demo piccolo | `pass` | 1 profilo principale, 1 contrasto leggero, 4 documenti, 3 famiglie fonte |
| Merge multi-fonte visibile | `pass` | `mvp_demo_reconciliation_table.md`, 4/4 documenti coperti |
| Decisione storica presente | `pass` | `historian_review/review_decisions_summary.md` |
| Verified facts solo preview | `pass` | `historian_review/verified_facts.preview.md` |
| ProfilePatch solo preview | `pass` | `historian_review/profile_patch.preview.md` |
| Feedback loop chiuso | `pass` | `historian_review/feedback_loop_outcome.t31-demo.md`, outcome `needs_manual_review` |
| Dossier e indice presenti | `pass` | `funding_package_index.md`, `mvp_funding_dossier.md` |
| Brief editoriale esterno presente | `pass` | `funding-demo-t33-external-brief.md` |
| Roadmap uso fondi presente | `pass` | `funding-demo-t33-funding-roadmap.md` |
| Pubblicabilita' storica | `blocked` | `mvp_go_no_go_checklist.md`, stato `go_with_review_blockers` |

## Condizioni per presentare

Prima di una presentazione a finanziatori, l'operatore deve:

1. aprire dal documento di ingresso T33, non dai JSON tecnici;
2. dichiarare all'inizio che il pacchetto e' preview-only;
3. mostrare `publication_ready=false` e `go_with_review_blockers`;
4. usare la scheda caso demo come racconto del metodo, non come biografia;
5. mostrare almeno una riga di riconciliazione con fonte e documento;
6. mostrare una decisione storica e una incertezza o divergenza;
7. mostrare la patch preview come proposta non applicata;
8. chiudere con la roadmap uso fondi e non con una promessa di automazione.

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
| 104 decisioni pending nel pacchetto generato | Impedisce di presentare schede o claim come pubblicabili. | Sessione di review storica dedicata, con decisioni registrate e nuovo go/no-go. |
| Output preview non canonici | Impedisce promozione automatica a profili o fatti verificati. | Incremento dedicato con backup, audit trail e approvazione curatoriale. |
| Esito feedback `needs_manual_review` | Dimostra il loop, non una conclusione storica. | Nuova review della fonte/sessione collegata e registrazione dell'esito. |

## Uso nel walkthrough

Questa checklist va letta dopo:

1. `funding-demo-t33-package-entrypoint.md`;
2. `funding-demo-t33-demo-case-card.md`;
3. `funding-demo-t33-evidence-flow-diagram.md`;
4. `funding-demo-t33-funding-roadmap.md`.
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
- 4/4 documenti selezionati coperti;
- safety flag preview-only confermate;
- nessun file del data root esterno modificato.
