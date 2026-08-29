# Agent Session Prompt

Prompt quotidiano consigliato:

```text
Lavora nel repository Me.Mo.Ri.A.

Leggi AGENTS.md e usa le skill $memoria-session, $memoria-planner e
$memoria-model-router. Controlla memoria-bootstrap/planning/current-work.json.

Se contiene un incremento selected o in_progress, verifica nel repository che
sia ancora aperto e coerente con roadmap e decision log. Altrimenti usa
$memoria-roadmap-selector per scegliere un unico micro-incremento.

Produci il task envelope. Classifica il task con $memoria-model-router e registra
nel planner tier, agent, modello, reasoning e motivazione prima di delegare.

Il parent Luna/medium e' il router/controller:
- discovery e docs semplici -> agent Luna;
- implementazione runtime -> implementer Terra/medium;
- quality review -> test_reviewer Terra/high;
- architettura o migrazione -> architect Sol/high.

Registra escalation/fallback prima della nuova delega. Non sostituire
silenziosamente un modello non disponibile.

Non modificare dati reali, non approvare claim, non fondere profili e non
pubblicare schede. Esegui test mirati, aggiorna il planner e chiudi con il
riepilogo previsto da AGENTS.md.
```
