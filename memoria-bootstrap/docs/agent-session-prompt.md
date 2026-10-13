# Agent Session Prompt

Prompt quotidiano consigliato, ridotto per Codex corrente:

```text
Lavora nel repository Me.Mo.Ri.A seguendo AGENTS.md.

Controlla memoria-bootstrap/planning/current-work.json. Se esiste lavoro
selected/in_progress ancora valido, riprendilo. Se serve scegliere un nuovo
micro-incremento, usa $memoria-roadmap-selector e apri solo le sezioni di roadmap
o decision log pertinenti.

Per un write task definisci un task envelope minimo con objective, repository,
read_set, write_set, test mirato e stop condition. Usa $memoria-model-router una
sola volta prima della delega/write e registra nel planner la route intenzionale.

Routing corrente:
- discovery/docs -> GPT-6 Luna / low;
- implementazione -> mmr_implementer / GPT-6.1 Sol / medium;
- quality review -> mmr_test_reviewer / GPT-6.1 Sol / medium;
- architettura/migrazione -> mmr_architect / GPT-6 Astra / low.

Usa un solo subagent per default. Passa path, simboli e criteri di accettazione,
non copie di file gia accessibili. Non aumentare reasoning per compensare
contesto, permessi o fonti mancanti. Se il modello richiesto non e disponibile,
registra il fallback prima di usare un modello diverso.

Implementa nella stessa sessione quando lo scope e eseguibile; altrimenti
registra un blocco reale. Dopo una delega verifica diff e quality gate mirato.
Aggiorna solo planner e documentazione realmente impattati.

Per ogni task OCR, prima della review leggi la sezione
`Verifica visuale assistita e richieste di review` in
`memoria-bootstrap/docs/playbooks/codex-document-analysis-core.md` e applicala
come passaggio obbligatorio: confronta pagina/crop, regioni e tutti gli output
OCR persistenti; correggi nel candidato ciò che è leggibile dall'immagine;
prima di coinvolgere l'utente, controlla anche la candidata con il dizionario
Hunspell locale versionato e il glossario esplicito per parole, forme composte
e abbreviazioni. Riusa il triage T43/T44 page-specific quando copre le stesse
forme; controlla con Hunspell quelle nuove della candidata. Esamina match, non
trovati e suggerimenti fuzzy: sono indizi da ricontrollare, mai correzioni
automatiche. Classifica i non trovati (nomi propri, forme storiche/composte,
sigle mancanti) e registra risorse, digest ed esiti prima di chiedere all'utente
in un unico gruppo soltanto i dubbi ancora irrisolti dopo il confronto visuale
e lessicale.
Il numero di regioni o alert non è il numero di azioni manuali. Se ne restano
molti, rivaluta crop, segmentazione o strumenti prima di chiedere una review.

Nella review OCR costruisci la candidata Markdown dalla mappa di regioni con
ID, bounding box, tipo e ordine; confronta i riconoscitori per blocco e verifica
automaticamente copertura, ordine, righe e celle. Se usi un modello visuale,
segui il percorso Ollama WSL gia' documentato, verifica modello/runtime e tieni
il suo output separato: e' un segnalatore indipendente, non un arbitro. Nel
benchmark T41 la specifica configurazione `llava-llama3` e' andata male su
fixture sintetiche; questo non generalizza a tutti i VLM. `llama3.2-vision` e'
presente nell'Ollama WSL verificato, ma la prova documentata la segnala
incompatibile con Ollama 0.33.2. Non basarti sul solo elenco Windows. Valuta
alternative OCR/VLM separatamente con il benchmark del progetto.

Deduplica e classifica gli alert lessicali per forma e posizione prima di
contarli come dubbi. Non trasformare `not_found` o fuzzy in correzioni. Chiedi
all'utente una sola review page-level soltanto per le decisioni ancora
irrisolte dopo i controlli automatici. Non fissare auto-accettazione finche' la
soglia non e' misurata per lingua/tipo su reference gold e holdout separati.

Non approvare claim, non fondere profili, non promuovere verified facts e non
pubblicare schede senza review/autorizzazione esplicita.
```
