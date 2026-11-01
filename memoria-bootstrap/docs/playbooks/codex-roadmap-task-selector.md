# Codex Roadmap Task Selector — post-MVP

Scegliere un incremento solo quando il planner corrente e' chiuso o invalido.
Il sommario in `memoria-bootstrap/docs/current-next-increment.md` e la sezione
"Post-MVP" di `docs/roadmap/02-technical-roadmap.md` sono i primi entrypoint.

Priorita': T45 igiene/contratto end-to-end -> T46 OCR/documenti -> T47
prima run online+offline -> T48 entita' luogo/evento -> T49 feedback/evaluation.
I gate T41 OCR formali e Q2 refactor restano paralleli e non bloccano il
percorso integrato, salvo sicurezza o regressioni documentate.

Non riaprire T29-T34b: la golden run e il pacchetto finanziatori sono chiusi.
Non introdurre fonti indiscriminatamente: selezionare una fonte online gia'
registrata e un documento offline identificabile. Una search result generica
non genera claim. L'aggiornamento del profilo resta preview con review umana.

Usa ricerca mirata (`rg`) anziche' leggere i documenti per intero. Restituisci
ID, dipendenze, confine dei file, test minimo, prova attesa e stop condition.
