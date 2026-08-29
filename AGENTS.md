# AGENTS.md — Me.Mo.Ri.A

Questo file è l'entrypoint operativo per Codex e per gli altri coding agent.
Le regole più specifiche possono essere aggiunte con `AGENTS.md` locali nelle
sottocartelle, senza duplicare qui i dettagli del dominio.

## Bootstrap minimo

All'inizio di una sessione:

1. leggi questo file;
2. leggi `memoria-bootstrap/planning/current-work.json`;
3. usa le skill `$memoria-session`, `$memoria-planner` e `$memoria-model-router`;
4. riprendi l’incremento solo se è ancora aperto e coerente con roadmap e decision log;
5. altrimenti usa `$memoria-roadmap-selector` e aggiorna il planner;
6. carica una sola skill verticale, solo quando il task la richiede.

Non leggere automaticamente tutte le roadmap, tutti i playbook o le run reali.

Su Windows:

1. usa `apply_patch` per le modifiche manuali solo quando la sandbox processuale di Codex e' operativa;
2. se compare un errore infrastrutturale come `windows sandbox`, `spawn setup refresh`, `setup refresh had errors` o `helper_unknown_error`, non ritentare lo stesso `apply_patch` e non entrare in un ciclo di escalation: segnala il blocco infrastrutturale e interrompi i tool che richiedono quella sandbox;
3. se i normali processi partono ma fallisce solo `apply_patch`, e la modifica resta confinata ai repository Git, e' ammesso un solo fallback deterministico tramite Python o `git apply`, seguito da `git diff --check`, diff mirato e test pertinenti;
4. non usare `Set-Content`, `Out-File` o riserializzazione JSON come fallback;
5. sui JSON modificati esegui `json.tool`; controlla il BOM solo se il parser lo segnala;
6. non confondere la sandbox processuale di Codex con le modalita' applicative Me.Mo.Ri.A denominate `--sandbox`, che restano preview-only e seguono i propri contratti.


## Routing modelli Codex

La sessione principale usa `gpt-5.6-luna` con reasoning `medium` come
router/controller a basso costo. Il parent deve classificare e delegare il
lavoro sostanziale al custom agent appropriato; non deve eseguire direttamente
task `medium`, `review` o `high`.

Prima di delegare o modificare file, `$memoria-model-router` classifica il task
in base alla forma e al rischio del lavoro, non alla dimensione del repository:

- `low`: discovery read-only -> `scanner` / Luna `low`;
- `low`: verifica documentale -> `docs_reviewer` / Luna `medium`;
- `low`: modifica solo docs/planner/config agent -> `docs_editor` / Luna `medium`;
- `medium`: codice o micro-feature entro contratti esistenti -> `implementer` / Terra `medium`;
- `review`: regressioni, edge case, provenance o quality gate -> `test_reviewer` / Terra `high`;
- `high`: architettura, migrazioni o trade-off multi-repository -> `architect` / Sol `high`.

Ogni selezione intenzionale va registrata in
`memoria-bootstrap/planning/current-work.json` nel blocco `routing`.
Escalation e fallback devono essere registrati prima della nuova delega.

La traccia runtime effettiva e' separata dal planner: gli hook Codex registrano
il model slug realmente usato per sessione e subagent in
`memoria-bootstrap/planning/.runtime/model-routing.ndjson`. Il file runtime e'
locale e ignorato da Git; il planner conserva invece la decisione auditabile.

Non usare profili project-local `[profiles.*]`: Codex li ignora nella
`.codex/config.toml` del progetto.

## Principio archivistico

```text
fonti -> documenti -> evidenze -> riconciliazione -> schede
       -> revisione umana -> pubblicazione
```

Nessun fatto storico diventa pubblicabile senza fonte tracciabile e decisione
umana. Una pagina risultati produce candidati, non fatti. Solo un documento o
record identificabile può sostenere un `EvidenceClaim`.

## Confini dei repository

- `memoria-engine`: codice, modelli, CLI, test e migrazioni.
- `memoria-workspace`: configurazione operativa e manifest; niente logica.
- `memoria-knowledge`: conoscenza documentata e contratti semantici.
- `memoria-rules`: regole deterministiche derivate da conoscenza approvata.
- `memoria-sources`: registry e definizioni dichiarative delle fonti.
- `memoria-bootstrap`: roadmap, decisioni, procedure e configurazione agent.

Il codice non deve incorporare dati storici reali. I dati reali restano nel
workspace esterno configurato dall'utente.

## Regole operative

- Un solo micro-incremento per sessione.
- Scope, file candidati, test e stop condition devono essere dichiarati prima
  della modifica.
- Preferire fixture offline e test mirati.
- Non ampliare il numero di fonti salvo richiesta esplicita.
- Non fare scraping aggressivo né salvare credenziali, cookie o token.
- Non approvare claim, risolvere conflitti storici o pubblicare schede.
- Le patch ai profili sono `preview-only` fino a revisione e audit.
- Mantenere compatibili CLI e wrapper pubblici; evitare nuove catene manuali di
  parametri quando la CLI può offrire discovery o workflow guidato.
- Aggiornare solo la documentazione direttamente impattata.
- Il planner conserva stato operativo, ma roadmap e decision log restano autoritativi.
- Aggiornare `memoria-bootstrap/planning/current-work.json` all’apertura e alla chiusura della sessione.

## Ordine preferito

```text
knowledge -> rules -> tests -> engine -> workspace sample -> report
```

## Chiusura obbligatoria

Riporta:

```text
micro-incremento:
file modificati:
test eseguiti:
risultato:
rischi residui:
documentazione verificata/aggiornata:
prossimo passo candidato:
```
