# AGENTS.md — Me.Mo.Ri.A

Entry point operativo per Codex. Mantieni qui solo regole valide per quasi ogni
task; dettagli e workflow verticali vivono nelle skill e nei contratti dedicati.

## Bootstrap minimo

1. Leggi questo file.
2. Leggi `memoria-bootstrap/planning/current-work.json` solo per capire se esiste
   lavoro persistente da riprendere.
3. Carica documenti e skill in modo contestuale, non preventivo.
4. Per un write task o una delega usa `$memoria-session`; usa
   `$memoria-model-router` una sola volta dopo che scope e rischio sono chiari.
5. Usa `$memoria-planner` solo quando devi aprire, aggiornare o chiudere lavoro
   persistente. Carica al massimo una skill verticale pertinente.

Non leggere automaticamente tutte le roadmap, tutti i playbook o le run reali.

## Routing Codex

Policy canonica: `memoria-bootstrap/docs/model-routing-policy.md`.

```text
focused/read-only/docs -> GPT-6 Luna / low
implementation        -> GPT-6.1 Sol / medium
quality review         -> GPT-6.1 Sol / medium
architecture/migration -> GPT-6 Astra / low
```

Il parent usa `gpt-6-luna` / `low` come controller. Delega lavoro sostanziale al
custom agent appropriato. Non aumentare reasoning per compensare file, permessi
o requisiti mancanti. Se un modello non e disponibile, registra il fallback
prima dell'esecuzione; non sostituirlo silenziosamente.

Token/context: un solo subagent per default, messaggi inter-agent compatti,
path/simboli al posto di file copiati, letture e test mirati prima di scansioni o
suite ampie.

## Principio archivistico

```text
fonti -> documenti -> evidenze -> riconciliazione -> schede
       -> revisione umana -> pubblicazione
```

Una pagina risultati produce candidati, non fatti. Solo un documento o record
identificabile puo sostenere un `EvidenceClaim`; la pubblicazione richiede
provenance e decisione umana.

## Confini repository

- `memoria-engine`: codice, CLI, test e migrazioni.
- `memoria-workspace`: configurazione/manifest, niente logica di dominio.
- `memoria-knowledge`: conoscenza documentata e contratti semantici.
- `memoria-rules`: regole deterministiche e contratti LLM.
- `memoria-sources`: registry e definizioni delle fonti.
- `memoria-bootstrap`: roadmap, decisioni, procedure e configurazione agent.

I dati storici reali restano nel workspace esterno configurato dall'utente, non
nel codice o nelle fixture Git.

## Regole operative

- Un solo micro-incremento verificabile per sessione di modifica.
- Prima del write: scope, write_set, test minimo e stop condition chiari.
- Preferire fixture offline e parsing deterministico.
- Non fare scraping aggressivo; non salvare credenziali, cookie o token.
- Non approvare claim, risolvere conflitti storici o pubblicare schede.
- Le patch ai profili restano preview-only fino a review e audit.
- Non fare refactor ampi senza decisione esplicita.
- Aggiornare solo la documentazione direttamente impattata.

## Windows sandbox

Per validare `current-work.json` e il routing su Windows, usa sempre
`memoria-engine/.venv/Scripts/python.exe` per eseguire
`memoria-bootstrap/planning/validate-codex-model-routing.py`. `jsonschema` 4.26.0
e' installato in quel virtualenv; il Python globale puo' non averlo e non deve
essere usato per concludere che il pacchetto manchi. Dettagli in
`memoria-bootstrap/planning/README.md`.

Usa `apply_patch` quando la sandbox Codex e operativa. Se fallisce solo
`apply_patch` per un errore infrastrutturale, e ammesso un solo fallback
riproducibile via Python o `git apply`, limitato al repository, seguito da diff
e test pertinenti. Non usare riserializzazioni distruttive come fallback.

## Chiusura

Riporta in forma concisa:

```text
micro-incremento:
file modificati:
test eseguiti:
risultato:
rischi residui:
documentazione verificata/aggiornata:
prossimo passo candidato:
```
