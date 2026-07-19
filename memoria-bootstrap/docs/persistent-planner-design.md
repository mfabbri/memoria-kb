# Persistent planner design

## Decisione

Aggiungere uno stato operativo persistente e minimale, senza creare una seconda
roadmap statica.

## Motivazione

La rilettura completa delle roadmap a ogni sessione consuma contesto. Al tempo
stesso una lista `next-increment` mantenuta come backlog indipendente tende a
diventare obsoleta. Il planner risolve il problema conservando soltanto:

- incremento attualmente selezionato;
- base documentale della selezione;
- stop condition e verifiche;
- stato e prossimo tipo di azione.

## Regola di invalidazione

L'incremento viene ricalcolato quando:

- è completato o superseded;
- i file o presupposti citati non esistono più;
- una roadmap o decisione successiva ne cambia la priorità;
- la stop condition risulta già soddisfatta;
- il task richiederebbe ampliare lo scope dichiarato.

## Non-obiettivi

Il planner non:

- approva claim o decisioni storiche;
- conserva dati reali;
- sostituisce roadmap, decision log o issue tracker;
- pianifica automaticamente una catena di incrementi;
- autorizza merge o pubblicazione.
