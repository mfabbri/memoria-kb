---
name: memoria-session
description: Avvia e chiude una sessione Me.Mo.Ri.A con contesto minimo, task envelope e guardrail archivistici.
---

# Me.Mo.Ri.A Session

## Input minimo

Leggi:

1. `AGENTS.md`;
2. `memoria-bootstrap/docs/current-next-increment.md`;
3. il contratto di confine pertinente, solo se il task attraversa repository.

## Task envelope

Prima di modificare file produci:

```yaml
mode: discovery-lite | scoped-fix | feature-slice | quality-slice | architecture-review
objective: una frase verificabile
roadmap_basis: sezione o decisione, se necessaria
repositories: []
read_set: []
write_set: []
test_command: ""
documentation_touchpoint: []
stop_conditions: []
```

Limiti consigliati:

- `discovery-lite`: massimo 10 file, nessuna modifica;
- `scoped-fix`: massimo 20 file letti e 5 modificati;
- `feature-slice`: massimo 30 file letti e 8 modificati;
- `quality-slice`: test/audit mirati, nessuna espansione funzionale.

Supera il budget solo dichiarando il motivo.

## Routing

Dopo il task envelope usa `$memoria-model-router`. Registra il routing nel
planner prima di delegare o modificare file. Il parent Luna e' un router:
delega task medium/review/high al custom agent corrispondente quando disponibile.
Se la delega non e' disponibile, puo' eseguire direttamente solo un micro-slice
medium gia' delimitato, registrando un fallback esplicito e mantenendo invariati
write_set e quality gate. Review e high restano fuori da questo fallback.

## Stop condition

Fermati prima di: approvare claim, aggiornare `verified_facts`, fondere profili,
risolvere conflitti storici, pubblicare schede, usare credenziali o avviare
scraping massivo.

## Chiusura

Aggiorna `memoria-bootstrap/docs/current-next-increment.md` come nota sintetica di sessione, non
come backlog. Aggiorna il decision log solo per decisioni architetturali o
metodologiche effettive.
