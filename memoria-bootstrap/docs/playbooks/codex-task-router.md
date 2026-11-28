# Codex task router — v3.2, 2026-11-21

Fonte canonica: `../model-routing-policy.md`.

- **Default lavori sostanziali:** parent GPT-6.2 Sol / medium, senza delega.
- **Edit breve e deterministico:** passa a Luna / low in `/model`, se disponibile.
- **Review indipendente mirata:** Sol / medium solo per rischio non coperto da test.
- **Trade-off architetturale complesso:** Astra / medium, senza fan-out rituale.
- **Visuale/UI:** Terra / medium solo se il task e' veramente visuale.

La presenza di sei file agent non richiede sei subagent. Prima di delegare,
confronta overhead di contesto con il beneficio. Non duplicare file nei
handoff, non usare un model ID API che `/model` non offre, non inventare
risparmi. Nuove route planner v3.2; storico intatto.

Prima di modificare il runtime serve un blocco storico concreto, evidenza
attesa e test minimo. Dopo: dossier/feedback migliorato o blocker riproducibile.
