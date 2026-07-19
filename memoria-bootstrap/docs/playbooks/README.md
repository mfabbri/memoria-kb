# Playbook e skill Codex per Me.Mo.Ri.A

La procedura ordinaria usa le capacità native di Codex e un contesto minimo.

## Entrypoint

```text
AGENTS.md
$memoria-session
$memoria-roadmap-selector   # solo quando l'incremento non è già definito
```

Aggiungere al massimo una skill verticale:

- `$memoria-source-registry` per fonti e registry;
- `$memoria-profile-feedback` per feedback e patch ai profili;
- `$memoria-quality-gate` per la chiusura e la review.

## Profili consigliati

```text
fast      ricognizione, ricerca simboli, controllo documentale leggero
standard  fix e micro-feature ordinarie
deep      architettura, migrazioni, conflitti tra contratti
review    review finale di cambiamenti ad alto impatto
```

Se il client Codex supporta i profili, selezionarli dalla configurazione locale
`.codex/config.toml`. Non usare il modello più costoso per scansioni meccaniche.

## Playbook legacy

I file `01-start-session.md` ... `09-continuous-refactor.md` e i vecchi
`codex-*-core.md` restano temporaneamente disponibili per compatibilità, ma non
sono letture iniziali. Le regole attive devono convergere in `AGENTS.md`, skill e
contratti di repository.

## Regola sintetica

```text
1 sessione = 1 micro-obiettivo
1 micro-obiettivo = 1 skill verticale massimo
1 implementazione = 1 test mirato
1 fatto storico = 1 fonte tracciabile + revisione umana
```
