# Daily Agent Procedure — post-MVP (2026-11-14)

Per una piccola correzione richiesta direttamente dall'utente non serve
selezionare un incremento, né caricare le roadmap complete.

Per il lavoro **guidato dalla roadmap**:

1. `AGENTS.md`, `docs/current-focus.md`, quindi
   `python memoria-bootstrap/planning/current-work-summary.py`.
2. Riprendi l'incremento aperto solo se ancora coerente; se `completed`, usa
   `$memoria-roadmap-selector` e la sezione T53-T58 della roadmap tecnica.
3. Definisci obiettivo, write set, test, criterio di uscita; registra nel planner
   soltanto all'avvio. Non riscrivere lo storico T29-T52.
4. Leggi gli entrypoint del codice e i test pertinenti; carica una skill
   verticale solo se serve. Nessun fan-out automatico di subagent.
5. Esegui e verifica lo slice fino al criterio di uscita, correggendo gli errori
   introdotti; non interromperti per approvazioni già coperte dal task.
6. Ferma il lavoro davanti a review umana, dati reali non accessibili, scritture
   canoniche o query live non autorizzate; registra un blocker concreto.
7. Chiudi con test effettivi, diff, stato planner e prossima slice candidata.

OCR T41 e pCloud T27/T28 sono sospesi. Procedure verticali storiche restano
consultabili ma non sono istruzioni di avvio generale.
