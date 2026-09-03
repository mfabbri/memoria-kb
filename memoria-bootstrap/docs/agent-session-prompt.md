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

Valuta il deliverable primario e l'avanzamento reale della roadmap. Se una
review architetturale ha gia' approvato il confine e non esiste un blocco reale,
riprendi l'implementazione dello stesso candidato. Non trasformare le
condizioni di qualita' in un incremento separato solo preparatorio: accorpa test
e implementazione quando condividono confine, rischio e quality gate. Se scegli
un incremento test-only, registra nel task envelope il blocco che lo rende
necessario o il valore indipendente che produce.

Il parent Luna/medium e' il router/controller:
- discovery e docs semplici -> agent Luna;
- implementazione runtime -> mmr_implementer Terra/medium;
- quality review -> mmr_test_reviewer Terra/high;
- architettura o migrazione -> mmr_architect Sol/high.

Se un subagent non e' disponibile, il parent puo' eseguire direttamente solo un
micro-slice runtime `medium` gia' delimitato dal planner, registrando il
fallback e mantenendo write_set, stop condition e quality gate. Review e high
restano bloccati senza l'agente dedicato. Non sostituire silenziosamente un
modello non disponibile.

Per un incremento runtime `medium` selected o in_progress, la selezione e il
planner sono soltanto precondizioni: nella stessa sessione devi produrre un
diff runtime entro il write set e il relativo quality gate, oppure registrare
un blocco reale e riproducibile. Non chiudere e non usare `next_action: resume`
per rinviare un task eseguibile; una modifica solo documentale non conta come
avanzamento dell'implementazione.

Una delega non e' una chiusura: dopo ogni delega il parent deve attendere la
restituzione oppure registrare un blocco reale, controllare il diff effettivo
nel worktree condiviso, eseguire il quality gate del task e aggiornare il
planner con risultato, file e rischi residui. Non rispondere all'utente finche'
questi passaggi non sono conclusi; se l'agente ha modificato il codice, la
risposta deve riportare esplicitamente quei file e i test eseguiti.

Non modificare dati reali, non approvare claim, non fondere profili e non
pubblicare schede. Esegui test mirati, aggiorna il planner e chiudi con il
riepilogo previsto da AGENTS.md.
```
