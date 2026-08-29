# Persistent session planner

`current-work.json` conserva lo stato operativo minimo tra una sessione e la
successiva. Non sostituisce le roadmap e non è una backlog indipendente.

## Autorità

1. roadmap e decision log definiscono direzione e priorità;
2. `current-work.json` registra l'incremento selezionato e il suo avanzamento;
3. codice e test mostrano lo stato implementativo reale.

In caso di conflitto prevalgono roadmap, decisioni e stato verificabile del
repository. Il planner deve essere marcato `superseded` e ricalcolato.

## Ciclo

- `uninitialized`, `completed` o `superseded`: ricalcolare dalle roadmap;
- `selected` o `in_progress`: verificare che sia ancora valido e riprenderlo;
- `blocked`: non aggirare il blocco; scegliere un altro incremento solo se la
  roadmap lo consente e registrare la decisione;
- a fine sessione aggiornare test, risultato, note e `next_action`.

## Regole

- un solo incremento attivo;
- ogni incremento attivo registra il routing model/agent prima della delega;
- escalation e fallback aggiornano la routing trace senza salvare chain-of-thought;
- nessun fatto storico o decisione editoriale nel planner;
- percorsi relativi al repository;
- date ISO 8601 UTC;
- aggiornamenti piccoli e leggibili in diff;
- non riscrivere il file con una copia template durante gli aggiornamenti del
  pacchetto Codex.

La struttura è validabile con `current-work.schema.json`. Se `jsonschema` è
installato:

```bash
python -m jsonschema -i planning/current-work.json planning/current-work.schema.json
```
