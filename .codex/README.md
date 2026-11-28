# Codex — Me.Mo.Ri.A policy v3.2

**Una sola configurazione alla root** `.codex/config.toml`. Non creare
`.codex` nei repository figli. Snapshot 2026-11-21: planner T84 `completed`,
nuove slice T85-T89; OCR T41 e pCloud T27/T28 sospesi.

Default GPT-6.2 Sol/medium per lavoro sostanziale; Luna/low selezionabile per
edit deterministici; Astra/medium solo per architettura ambigua. Subagent
specializzati **opzionali**, non obbligatori. La disponibilita' effettiva
va verificata con `/model` prima di affidarsi alla configurazione: modelli
visibili nell'API non garantiscono supporto in Codex/ChatGPT.

Per validare senza modificare dati storici:

```powershell
python .\memoria-bootstrap\planning\current-work-summary.py
python .\memoria-bootstrap\planning\validate-codex-model-routing.py
# Se jsonschema non installato, il validator avverte: non chiamare PASS il gate schema.
git diff --check
```

`/hooks` abilita, se trusted, l'audit runtime in
`memoria-bootstrap/planning/.runtime/model-routing.ndjson`; un evento puo'
non contenere model ID. La route intenzionale e' nel planner, lo storico
2.x/3.0/3.1 non si riscrive. Permessi custom agent ereditati dalla sessione:
read-only nelle istruzioni non e' isolamento tecnico.

Contesto piccolo: `AGENTS.md` -> `current-focus.md` -> planner summary;
skill e contratti mirati, niente dump del planner o roadmap integrale.
Dettagli in `memoria-bootstrap/docs/model-routing-policy.md`.
