# Me.Mo.Ri.A Multi-Repository Workspace

Me.Mo.Ri.A e' un meta-motore archivistico per ricercare, registrare,
riconciliare e revisionare evidenze sulla Resistenza italiana.

## Repository

- `memoria-bootstrap`: roadmap, decisioni, playbook e contratti;
- `memoria-engine`: package Python, CLI, pipeline, store, report e test;
- `memoria-workspace`: descriptor del workspace operativo, senza corpus reale;
- `memoria-knowledge`: conoscenza storica, glossari e modelli;
- `memoria-rules`: regole deterministiche e contratti LLM;
- `memoria-sources`: registry, strategie e logiche specifiche delle fonti.

Il corpus reale resta esterno a Git. Backend locale compatibile:

```text
P:\Comune\Me.Mo.Ri.a
```

## Priorita' corrente

La rifattorizzazione multi-repo e la baseline diagnostica sono sostanzialmente
chiuse. La direzione corrente e' costruire una golden run per la richiesta di
finanziamento:

```text
T29 contratto golden path
T30 run canonica con merge multi-fonte
T31 feedback loop storico chiuso
T32 hardening e prova generale
T33 pacchetto finanziatori
```

Documenti principali:

- `memoria-bootstrap/docs/roadmap/00-roadmap-master.md`;
- `memoria-bootstrap/docs/roadmap/01-mvp-roadmap.md`;
- `memoria-bootstrap/docs/roadmap/02-technical-roadmap.md`;
- `memoria-bootstrap/docs/funding-demo-golden-path.md`;
- `memoria-bootstrap/docs/current-next-increment.md`.

## Principio metodologico

```text
fonti -> documenti -> evidenze -> riconciliazione -> revisione -> feedback
```

Nessun risultato generico diventa fatto storico. Nessuna patch viene applicata
automaticamente. Nessun output preview e' pubblicabile senza revisione e
approvazione esplicite.
