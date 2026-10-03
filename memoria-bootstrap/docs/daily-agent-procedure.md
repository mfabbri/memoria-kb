# Daily Agent Procedure

Data aggiornamento: 2026-10-02

## Scopo

Permettere all'agent di riprendere o selezionare un micro-incremento senza
caricare contesto non necessario.

## Avvio

1. Applicare `AGENTS.md`.
2. Leggere `memoria-bootstrap/planning/current-work.json`.
3. Se lo stato e `selected`/`in_progress`, verificare solo i file e i riferimenti
   necessari a capire se il lavoro e ancora valido.
4. Se serve ricalcolare, usare `$memoria-roadmap-selector`: cercare intestazioni
   e dipendenze con `rg`, poi aprire solo le sezioni pertinenti.
5. Caricare al massimo una skill verticale per il task corrente.

Roadmap e decision log restano autoritativi, ma non sono letture obbligatorie
integrali a ogni sessione.

## Ciclo operativo

1. Delimitare objective, read/write set, test minimo e stop condition.
2. Se c'e delega o write sostanziale, eseguire `$memoria-model-router` una volta.
3. Registrare il routing nel planner.
4. Eseguire un solo micro-incremento.
5. Validare prima con il test piu mirato; ampliare solo per rischio/failure.
6. Aggiornare planner e documentazione realmente impattata.

## Guardrail

- niente dati reali nei repository Git;
- niente OCR/pipeline fuori dallo scope autorizzato;
- niente patch canoniche o `verified_facts` senza incremento, review e audit;
- niente risoluzione automatica di conflitti storici;
- niente refactor ampi o nuove fonti per semplice opportunismo;
- un solo subagent per default.

## Chiusura

Dichiarare file modificati, test eseguiti/non eseguiti, risultato, rischi residui
e prossimo candidato. Non rileggere roadmap complete solo per formulare il
messaggio finale.
