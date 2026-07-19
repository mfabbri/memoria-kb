# Agent Session Prompt

Prompt quotidiano consigliato:

```text
Lavora nel repository Me.Mo.Ri.A.

Leggi AGENTS.md e usa le skill $memoria-session e $memoria-planner.
Controlla planning/current-work.json.

Se contiene un incremento selected o in_progress, verifica nel repository che
sia ancora aperto, coerente con roadmap e decision log, poi completa soltanto
quello. Non considerare il planner autoritativo rispetto alle roadmap.

Se il planner è uninitialized, completed, superseded, non valido o incoerente,
usa $memoria-roadmap-selector per scegliere un unico micro-incremento e
registralo nel planner prima delle modifiche.

Produci il task envelope con scope, file minimi, test, documentation touchpoint
e stop condition. Usa il profilo fast per discovery, standard per
implementazione e deep solo per trade-off architetturali o migrazioni. Puoi
delegare scansione, test e controllo documentale ai subagent configurati.

Non modificare dati reali, non approvare claim, non fondere profili e non
pubblicare schede. Esegui test mirati, aggiorna planning/current-work.json e
chiudi con il riepilogo previsto da AGENTS.md.
```
