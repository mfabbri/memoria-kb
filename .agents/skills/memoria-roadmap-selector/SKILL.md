---
name: memoria-roadmap-selector
description: Select a verifiable post-MVP increment when current-work is completed or invalid.
---

# Roadmap selector post-MVP

1. Controlla solo lo stato in `memoria-bootstrap/planning/current-work.json` e
   il sommario iniziale di `docs/current-next-increment.md`.
2. Se il lavoro e' ancora valido e aperto, riprendilo. Altrimenti cerca con `rg`
   le sezioni T45-T49 e le dipendenze in `docs/roadmap/02-technical-roadmap.md`;
   consulta il master solo per i vincoli strategici interessati.
3. Proponi 2-3 micro-incrementi con output falsificabile, scegli il piu'
   piccolo che sblocca il **percorso integrato** (fonte offline/online -> documento
   -> claim candidato -> entity linking -> review -> feedback).
4. Non fare nuovi scraping estesi o variazioni ai canonici; distinguere
   ingestion OCR e revisione dalla validazione storica. Q2 e OCR formale
   proseguono come workstream secondari motivati dal rischio.
5. Registra il nuovo task envelope nel planner solo quando effettivamente avvii
   l'incremento; non falsificare la chiusura dello storico.

Output: ID, scope, file, evidenza di partenza, test, stop condition e decisioni
che richiedono lo storico.
