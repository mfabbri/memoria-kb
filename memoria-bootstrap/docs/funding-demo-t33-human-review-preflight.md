# T33 Human Review Preflight

Data: 2026-08-28

Stato: checklist preparatoria per la revisione umana del racconto T33. Non e'
un verbale compilato, non contiene un verdetto reale e non autorizza layout,
pubblicazione, bando, importo o finanziatore.

## Scopo

Questo preflight verifica che i materiali della revisione umana T33 siano
coerenti prima che un revisore compili il verbale. Serve a evitare che la
revisione parta da file mancanti, blocchi narrativi non allineati o guardrail
ambigui.

Il controllo resta repository-only: non legge il data root esterno, non copia
dati storici, non avvia pipeline, OCR, scraping o ricerche live.

## Materiali Minimi

| Materiale | Stato atteso prima della review | Esito preflight |
|---|---|---|
| `funding-demo-t33-presentation-entrypoint.md` | contiene sei schermate e criteri di revisione umana | `[ok/da correggere]` |
| `funding-demo-t33-presentation-dry-run.md` | documenta la prova asciutta del racconto | `[ok/da correggere]` |
| `funding-demo-t33-current-state-operator-note.md` | conferma run canonica e guardrail preview-only | `[ok/da correggere]` |
| `funding-demo-t33-andreoli-visual-layout.md` | limita la schermata Andreoli a tracce e dubbi | `[ok/da correggere]` |
| `funding-demo-t33-human-review-handoff.md` | elenca domande, esiti ammessi e blocchi da non superare | `[ok/da correggere]` |
| `funding-demo-t33-human-review-response-template.md` | resta vuoto e compilabile dal revisore umano | `[ok/da correggere]` |

## Controlli Di Coerenza

| Controllo | Criterio | Esito preflight |
|---|---|---|
| Sei blocchi narrativi | problema, patrimonio, cinque storie, caso concreto, limiti, passo successivo sono presenti in handoff e template | `[ok/da correggere]` |
| Esiti ammessi | `approved_for_layout`, `revise_before_layout` e `blocked` sono gli unici verdetti espliciti | `[ok/da correggere]` |
| Coorte e run | patrimonio di 57 profili, coorte pilota di 5 profili e golden run a 3 casi restano distinti | `[ok/da correggere]` |
| Caso Andreoli | il caso mostra collegamenti e dubbi, non una biografia conclusa | `[ok/da correggere]` |
| Guardrail editoriali | bando, importo e finanziatore restano assenti | `[ok/da correggere]` |
| Guardrail archivistici | nessun `ProfilePatch`, verified fact canonico o profilo canonico viene modificato | `[ok/da correggere]` |

## Esito Del Preflight

Selezionare un solo esito tecnico-preparatorio:

- [ ] `ready_for_human_review`
- [ ] `needs_material_fix`
- [ ] `blocked_before_review`

Nota del preflight:

```text
[compilare solo durante il controllo preparatorio]
```

## Azioni Ammesse

| Esito preflight | Azione ammessa |
|---|---|
| `ready_for_human_review` | consegnare handoff e template a un revisore umano |
| `needs_material_fix` | correggere solo i materiali indicati e ripetere il preflight |
| `blocked_before_review` | fermare la revisione e riaprire il confine narrativo T33 |

Questo esito non sostituisce il verdetto umano. Anche con
`ready_for_human_review`, il racconto resta non approvato finche' il template non
viene compilato da un revisore umano.

## Blocchi Da Confermare

- [ ] Nessun dato storico reale e' stato copiato nel repository.
- [ ] Nessun file del data root esterno e' stato letto o modificato durante il
      preflight.
- [ ] Nessun bando, importo o finanziatore e' stato introdotto.
- [ ] Nessuna scheda preview e' descritta come pubblicabile.
- [ ] Nessun `ProfilePatch` e' stato applicato.
- [ ] Nessun verified fact canonico e' stato creato.
- [ ] Nessun profilo canonico e' stato modificato.

## Limite

Il preflight misura la prontezza dei materiali, non la qualita' storica o
narrativa del racconto. La qualita' del racconto viene decisa solo nella
revisione umana effettiva tramite
`funding-demo-t33-human-review-response-template.md`.
