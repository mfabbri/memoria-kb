# T33 Human Review Preflight Record

Data: 2026-08-28

Controllo preparatorio: Codex

Stato: `ready_for_human_review`

Questo record attesta soltanto la coerenza preparatoria dei materiali. Non
contiene un verdetto umano sul racconto e non autorizza layout, pubblicazione,
bando, importo o finanziatore.

## Materiali

| Materiale | Esito |
|---|---|
| Entrypoint della presentazione | ok |
| Prova asciutta narrativa | ok |
| Nota sullo stato operativo | ok |
| Scaletta visuale Andreoli | ok |
| Handoff di revisione | ok |
| Template del verbale | ok |

## Coerenza

| Controllo | Esito |
|---|---|
| Sei blocchi narrativi presenti e allineati | ok |
| Esiti ammessi coerenti tra handoff e template | ok |
| Patrimonio di 57 profili, coorte pilota di 5 e golden run a 3 casi distinti | ok |
| Andreoli presentato come collegamento e domanda aperta | ok |
| Bando, importo e finanziatore non introdotti | ok |
| Stato preview-only e non pubblicabile esplicito | ok |

## Guardrail

- [x] Nessun dato storico reale copiato nel repository durante il preflight.
- [x] Nessun file del data root esterno letto o modificato durante il preflight.
- [x] Nessuna pipeline, OCR, ricerca live o chiamata cloud eseguita.
- [x] Nessun `ProfilePatch` applicato.
- [x] Nessun verified fact canonico creato.
- [x] Nessun profilo canonico modificato.
- [x] Nessuna pubblicazione autorizzata.

## Esito

- [x] `ready_for_human_review`
- [ ] `needs_material_fix`
- [ ] `blocked_before_review`

Prossima azione ammessa: sottoporre i sei blocchi narrativi a un revisore umano
e registrarne le decisioni in un verbale datato separato.
