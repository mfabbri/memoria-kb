# AGENTS.md — Me.Mo.Ri.A (source-first, 2026-11-21)

## Contratto storico (sempre)

`fonti -> documenti identificabili -> EvidenceClaim -> riconciliazione ->
revisione umana -> feedback -> nuova ricerca`. Un `SourceResult` generico
non prova fatti. Ogni claim conserva `source_document_id`, provenance, metodo,
confidence e review status; un claim non revisionato non e' verificato.
Conflitti e alias non si risolvono per somiglianza di nome. Mai scrivere
profili canonici, accettare claim, simulare una decisione dello storico o
pubblicare senza i gate espliciti del dominio.

Dati reali, segreti, corpus OCR e run pesanti restano fuori da Git. Registry
fonte di verita': `memoria-sources/registry/camalanca_fonti.yaml`, con
`source_profiles`, `source_strategies`, `source_result_logic`,
`source_detail_logic`. Solo dettaglio/documento identificabile puo' diventare
`SourceDocument` e produrre claim candidati. Per operazioni di prodotto usare
il launcher installato `memoria`, non chiamate Python interne.

## Priorita' e selezione (lavoro guidato dalla roadmap)

1. Leggi `memoria-bootstrap/docs/current-focus.md` e l'output breve di
   `python memoria-bootstrap/planning/current-work-summary.py`.
2. Se esiste lavoro aperto, riprendilo solo se coerente con la decisione
   source-first; altrimenti valuta T85-T89 nella sezione **corrente** della
   roadmap tecnica. Il planner T84 e' chiuso: non riprendere T53-T84.
3. L'uscita della slice deve essere un risultato storico osservabile o un
   blocker reale. Un micro-test, una nuova CLI o una rifinitura di provenance
   senza dossier/feedback sbloccato non sono un risultato di prodotto.
4. T41 OCR e T27/T28 pCloud sospesi, golden run T29-T33 completata.
   Riattivarli solo con decisione esplicita dell'utente.
5. Prima di partire: obiettivo, set minimo di file, evidenza attesa,
   test, stop condition. Non creare un nuovo record nel planner prima
   dell'avvio effettivo. Non aprire automaticamente il task successivo.

Per dati reali e run online: usa
`memoria-bootstrap/docs/playbooks/online-source-research-review.md`; chiedi
l'autorizzazione per fonte, query e attempt specifici. Non lanciare nuove
ricerche live autonomamente. La sola preview non equivale a review umana.

## Codex: modelli e contesto

Policy v3.2: `memoria-bootstrap/docs/model-routing-policy.md`.
Per task sostanziali parti con GPT-6.2 Sol/medium; per modifica meccanica
breve puoi usare GPT-6 Luna/low; GPT-6.2 Astra/medium solo per problemi
multi-repo ambigui o review ad alto impatto non risolvibili da test mirati.
Il modello effettivo dipende da `/model`: niente fallback silenzioso.
Delega solo lavoro indipendente che giustifica token/overhead extra.

Carica skill e contratti per domanda, non a pacchetto. Non aprire i ~160 KB
di roadmap tecnica, il planner integrale o i run ZIP per un normale avvio.
Usa ricerca per simbolo/path e output brevi; ferma loop di lettura/test senza
nuova evidenza. Non riaprire OCR, pCloud o refactor estesi per riempire il
backlog. Per sessioni sostanziali: `$memoria-session`.

## Chiusura

Riporta artefatto storico ottenuto o blocker specifico, file cambiati,
provenance, test mirati, stato della review/autorizzazioni, limiti e prossimo
candidato. Non dichiarare risparmi token senza metriche comparabili.
