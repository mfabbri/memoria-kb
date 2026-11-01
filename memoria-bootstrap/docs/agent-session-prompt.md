# Prompt quotidiano Codex — post-MVP

Da usare in Codex **dalla radice del workspace Me.Mo.Ri.A**, contenente
`AGENTS.md` e le sei directory `memoria-*`.

```text
Leggi AGENTS.md e memoria-bootstrap/planning/current-work.json.

Se c'e' un incremento selected/in_progress valido, riprendilo. Se e' completed,
usa $memoria-roadmap-selector per selezionare dalla direzione post-MVP T45-T49
il piu' piccolo incremento utile al percorso fonti -> documenti -> evidenze ->
riconciliazione -> review -> feedback.

Definisci objective, write_set, test mirato e stop condition. Carica solo le
sezioni di roadmap, skill e contratti pertinenti. Esegui la modifica e i test
nella sessione, salvo blocco riproducibile. Non delegare per principio: usa
$memoria-model-router soltanto se serve cambiare modello o assegnare un task
sostanziale a uno specialista. Registra in planner il routing dei nuovi task
(policy 3.1) e verifica la disponibilita' effettiva del modello.

Preserva provenance, review umana, preview/apply e audit. Non generare fatti
storici da risultati di ricerca o da OCR provisional. Per task OCR consulta
soltanto le sezioni pertinenti del playbook codex-document-analysis-core.md;
preflight Ollama WSL solo per inferenza VLM. Non riaprire il pilot T42 chiuso;
la validazione statistica formale resta separata.

Concludi con diff, test e risultato, limiti, planner aggiornato e prossimo passo.
```

Il testo operativo OCR completo, inclusi review visiva, Hunspell, glossario,
preflight VLM in WSL, limiti del pilot T42 e `manual_review_cap_exceeded`, vive in
`memoria-bootstrap/docs/playbooks/codex-document-analysis-core.md`.
Non copiarlo nel prompt quotidiano: riduce duplicazioni e divergenze.
