# AGENTS.md — Me.Mo.Ri.A

Questo file è l'entrypoint operativo per Codex e per gli altri coding agent.
Le regole più specifiche possono essere aggiunte con `AGENTS.md` locali nelle
sottocartelle, senza duplicare qui i dettagli del dominio.

## Bootstrap minimo

All'inizio di una sessione:

1. leggi questo file;
2. leggi `memoria-bootstrap/planning/current-work.json`;
3. usa le skill `$memoria-session` e `$memoria-planner`;
4. riprendi l’incremento solo se è ancora aperto e coerente con roadmap e decision log;
5. altrimenti usa `$memoria-roadmap-selector` e aggiorna il planner;
6. carica una sola skill verticale, solo quando il task la richiede.

Non leggere automaticamente tutte le roadmap, tutti i playbook o le run reali.

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
