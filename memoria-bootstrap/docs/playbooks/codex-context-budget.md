# Codex Context Budget — euristiche v3.1

Non esiste una quota rigida di file valida per ogni task: il criterio e' la
**quantita' di contesto utile per correggere/verificare il cambiamento**.

- `discovery-lite`: `rg --files`, simboli e snippet; niente dump ricorsivi.
- docs/config breve: parent Luna/low, nessuna delega per principio.
- code slice: leggere il modulo target, contratto pubblico e test pertinenti;
  Sol/medium se la modifica e' sostanziale.
- review: indipendente solo per rischio concreto (provenance, idempotenza,
  dati canonici, storage, regressione ampia).
- architettura: Astra/low per trade-off che coinvolgono piu' repository e
  decisioni difficili; evitare l'uso per semplice scrittura documentale.

Token: skill su richiesta, dettagli verticali nei playbook, handoff con path e
criteri, output strumenti brevi, checkpoint dopo compaction, niente agent
paralleli su stessi file, evitare test e letture gia' conclusi senza motivo.
Misurare esiti e costi completi prima di dichiarare una riduzione percentuale.
