# Prompt quotidiano Codex — post-MVP

Da usare in Codex **dalla radice del workspace Me.Mo.Ri.A**, contenente
`AGENTS.md` e le sei directory `memoria-*`.

```text
Leggi AGENTS.md e memoria-bootstrap/planning/current-work.json.

Se c'e' un incremento selected/in_progress valido, riprendilo. Se e' completed,
usa $memoria-roadmap-selector per selezionare dalla direzione post-MVP T45-T49
il piu' piccolo incremento utile al percorso fonti -> documenti -> evidenze ->
riconciliazione -> review -> feedback.

Definisci objective, write_set, test mirato e stop condition. Carica solo le
sezioni di roadmap, skill e contratti pertinenti. Esegui la modifica e i test
nella sessione, salvo blocco riproducibile. Non delegare per principio: usa
$memoria-model-router soltanto se serve cambiare modello o assegnare un task
sostanziale a uno specialista. Registra in planner il routing dei nuovi task
(policy 3.1) e verifica la disponibilita' effettiva del modello.

Se l'utente chiede N incrementi, eseguili in sequenza, ciascuno con planner e
quality gate separati; dopo l'N-esimo, riporta in breve lo stato rispetto alla
roadmap. Non interrompere la sequenza per chiedere scelte gia' deducibili dal
planner o dalla roadmap.

Per eseguire o verificare comandi Me.Mo.Ri.A usa sempre il launcher installato
(`memoria` o `.venv/Scripts/memoria.exe`), mai `python -m`, import diretti o
chiamate alle funzioni applicative. Una prova con fixture verifica il software,
non produce una misura reale. Se T49 ha la toolchain pronta ma mancano ricerca,
review e outcome effettivamente collegati, non simulare quei dati: porta le
candidate reali all'utente per la decisione umana e fermati prima di una nuova
ricerca, salvo che action, fonte e strategia/query siano già autorizzate.
`BUONA`/`DUBBIA` classificano l'action e non concedono da sole il permesso di
cercare.

Preserva provenance, review umana, preview/apply e audit. Non generare fatti
storici da risultati di ricerca o da OCR provisional. Per task OCR consulta
soltanto le sezioni pertinenti del playbook codex-document-analysis-core.md;
preflight Ollama WSL solo per inferenza VLM. Non riaprire il pilot T42 chiuso;
la validazione statistica formale resta separata.

Per una ricerca reale parti da un `source_id` abilitato in
`memoria-sources/registry/camalanca_fonti.yaml` e dal database operativo già
configurato: non sostituirli con una fonte non catalogata o un DB scratch senza
motivo esplicito. Consulta la procedura completa in
`memoria-bootstrap/docs/playbooks/online-source-research-review.md`.
Salva sempre tutti gli artifact di una ricerca o review reale nella destinazione
operativa persistente `P:\Comune\Me.Mo.Ri.a\risultati\runs\<run-id>\`, usando
un nuovo ID stabile per ogni run. La regola comprende report, documenti acquisiti,
claim, queue, manifest, receipt, preview e feedback. Non usare `.tmp`,
`.tmp-tests` o altre directory del workspace per dati o review reali: sono
riservate a fixture sintetiche e smoke test. Se la destinazione persistente non
è disponibile o scrivibile, fermati e segnala il blocco; non ripiegare su una
cartella temporanea. Mantieni gli output della stessa run sotto la medesima
directory radice e comunica il percorso e il comando CLI successivo.
Registra una pagina online con `memoria documents register-online-source`,
prima in preview e poi con `--apply`; non scrivere nel database via script.
Genera la preview Place/Event con il comando CLI e passa il suo manifest a
`memoria documents preview-review-wizard`. Il wizard mostra evidenza e
provenienza, raccoglie solo le decisioni della persona e scrive la receipt dopo
conferma. Spiega sempre all'utente dove il CLI ha salvato gli artifact, cosa
contengono e quale comando usare dopo. Non chiedere di creare o compilare JSON
né inventare decisioni se il wizard non è disponibile/interattivo.
Genera claim solo quando l'affermazione riguarda esplicitamente l'entità
principale selezionata, come una persona o un luogo; titoli, descrizioni e dati
generici del portale non sono claim dell'entità. Se chiedi una decisione su un
claim, spiega prima eventuali termini poco chiari. Una risposta esplicita come
«accetto come candidata» è la decisione per l'elemento presentato: registrala
come accettazione candidata, senza trasformarla in fatto verificato e senza
richiederne una seconda conferma.

Quando serve una decisione o un dato dall'utente, usa come procedura normale
una domanda per messaggio. Prima della domanda riassumi il contesto e le
evidenze rilevanti, indica che cosa la risposta sblocca e presenta le opzioni
con le rispettive conseguenze quando sono note. Se la sequenza di decisioni è
già identificabile, dichiara quante domande totali ci sono e quante ne restano;
aggiorna il conteggio dopo ogni risposta. Se il numero può cambiare, dillo
esplicitamente. Attendi la risposta prima di porre la domanda successiva, non
accorpare decisioni indipendenti e non considerare il silenzio come consenso.
Se l'interfaccia non rende visibile la domanda, ripresentala nel messaggio
successivo con il contesto essenziale e lo stato della sequenza. Continua nel
frattempo le attività indipendenti dalla risposta.

Concludi con diff, test e risultato, limiti, planner aggiornato e prossimo passo.

Per modifiche a `current-work.json`, esegui
`memoria-bootstrap/planning/validate-codex-model-routing.py` nell'ambiente
Python di sviluppo che contiene `jsonschema` (dipendenza dev di
`memoria-engine`). Se compare `schema validation skipped`, il controllo
strutturale del routing non equivale alla validazione JSON Schema: installa
`jsonschema>=4.20` nell'ambiente attivo e ripeti il comando.

Per T49 carica la sezione "Raccolta delle misure T49" del playbook
`memoria-bootstrap/docs/playbooks/codex-person-profile-feedback-loop-core.md`;
non inferire timestamp, claim, token o costi mancanti.
```

Il testo operativo OCR completo, inclusi review visiva, Hunspell, glossario,
preflight VLM in WSL, limiti del pilot T42 e `manual_review_cap_exceeded`, vive in
`memoria-bootstrap/docs/playbooks/codex-document-analysis-core.md`.
Non copiarlo nel prompt quotidiano: riduce duplicazioni e divergenze.
