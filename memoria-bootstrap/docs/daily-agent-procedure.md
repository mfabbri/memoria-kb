# Daily Agent Procedure — source-first 2026-11-21

Per modifiche puntuali richieste dall'utente: applica la modifica e verifica,
senza aprire roadmap, planner o subagent se non necessari.

Per task guidati dalla roadmap:

1. `AGENTS.md` + `docs/current-focus.md` + summary del planner.
2. Se presente un task aperto, verifica coerenza con la strategia attuale;
   se chiuso T84, seleziona T85-T89 e non T53-T84.
3. Definisci evidenza storica attesa, scope, rischi, test essenziale e stop.
4. Leggi solo i file pertinenti. Model routing v3.2 on-demand: Sol/medium
   default, Luna/low per task meccanici, Astra/medium solo per vera ambiguita'.
5. Usa CLI `memoria` su data root reale se accessibile e autorizzato;
   SourceResult non e' documento e claim non equivale a verified fact.
6. Se manca autorizzazione live, review umana o accesso al data root,
   ferma la slice con blocker preciso; niente fixture come surrogato.
7. Registra planner solo all'avvio/chiusura, preserva lo storico e riferisci
   esito documentale o blocker. Non aprire task di hardening consequenziali.

T41 OCR e T27/T28 pCloud sospesi; le procedure verticali sono on-demand.
