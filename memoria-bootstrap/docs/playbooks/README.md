# Playbook e skill Codex per Me.Mo.Ri.A

La procedura ordinaria usa contesto minimo e progressive disclosure.

## Entrypoint

Codex legge `AGENTS.md`. Non caricare automaticamente tutti i playbook o tutte
le skill.

Usa on-demand:

- `$memoria-session` per un write task o una sessione multi-step;
- `$memoria-planner` quando devi aprire/chiudere lavoro persistente;
- `$memoria-model-router` prima di una delega o di un cambio modello;
- una sola skill verticale pertinente (`$memoria-source-registry`,
  `$memoria-profile-feedback`, `$memoria-quality-gate`, ...).

## Routing corrente

```text
focused/docs       GPT-6 Luna / low
implementation     GPT-6.1 Sol / medium
quality review     GPT-6.1 Sol / medium
architecture       GPT-6 Astra / low
```

Non usare `[profiles.*]` nel `.codex/config.toml` del progetto. I profili Codex
moderni sono file separati sotto `CODEX_HOME`; Me.Mo.Ri.A usa custom agent.

## Playbook legacy

I playbook dettagliati restano compatibili ma non sono letture iniziali. Le
regole attive devono convergere in `AGENTS.md`, skill focalizzate e contratti di
repository.

## Regola sintetica

```text
1 sessione di modifica = 1 micro-obiettivo
1 micro-obiettivo = 1 skill verticale massimo
1 implementazione = 1 test mirato prima della suite ampia
1 fatto storico = 1 fonte tracciabile + revisione umana
```
