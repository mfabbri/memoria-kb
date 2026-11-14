---
name: memoria-roadmap-selector
description: Seleziona il prossimo micro-incremento post-MVP quando il planner è chiuso o non valido.
---

# Selezione roadmap — T53-T58

1. Leggi `memoria-bootstrap/docs/current-focus.md` e lo stato conciso ottenuto
   con `python memoria-bootstrap/planning/current-work-summary.py`.
2. Se un incremento `selected/in_progress` è coerente, riprendilo. Se è
   `completed`, consulta **solo** la sezione T53-T58 della roadmap tecnica.
3. Seleziona la prima slice che riduce un gap concreto del percorso documenti
   -> claim -> riconciliazione -> review -> memoria; rispetta dipendenze,
   capacità e dati effettivamente accessibili.
4. Tratta T41 OCR e T27/T28 pCloud come sospesi, non candidati automatici.
   T29-T52 sono storico; Q2 solo per regressioni motivate.
5. Restituisci ID, prova attesa, scope, write set, test e stop condition;
   apri l'envelope nel planner **all'avvio**, senza riscrivere le sessioni storiche.

Non autorizzare query live, review dello storico o modifiche canoniche per
il solo fatto di aver selezionato un incremento.
