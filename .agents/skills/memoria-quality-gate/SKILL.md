---
name: memoria-quality-gate
description: Run the targeted quality gate after a Me.Mo.Ri.A micro-increment.
---

# Quality Gate

Controlla, nell'ordine:

1. test mirato e fixture offline;
2. compatibilità dei contratti pubblici;
3. presenza di `source_document_id`, provenance, confidence e review status;
4. assenza di promozione automatica da candidate result a fatto storico;
5. separazione repository e assenza di dati reali nel codice;
6. aggiornamento della sola guida operativa impattata;
7. diff piccolo e coerente con il task envelope.

Un test verde con guida operativa incoerente non chiude l'incremento.

## Chiusura e consumer della soglia OCR provisional

Per il pilot T42 chiuso il 2026-11-01, verifica che il report e la guida
dichiarino cutoff `1.0`, scope esatto tedesco/PP-OCRv5/`numbered_report`, 10/10
pagine accepted provisionalmente e 0/10 review manuali nel pilot. La misura
riportata è 63 eventi di correzione su 11.616 parole candidate stimate (~0,54%),
con pagina peggiore 10/1.117 (~0,90%); non chiamarla WER gold o garanzia futura.

Il cutoff `1.0` include ogni score valido [0,1] nello scope: segnala esplicitamente
che è non discriminante e non generalizzarlo ad altri profili. Verifica che il
consumer CLI mantenga `machine_pass`, `human_verified` e claim extraction
disattivati. Il gate formale 5%/95% resta separato e richiede il suo percorso
con reference adjudicate e holdout indipendente.

Il limite manuale del 3% è fail-closed: oltre il limite il workflow produce
`manual_review_cap_exceeded` e non autorizza la richiesta di review. Non
presentarlo come completamento del batch entro il 3%; un batch che supera il cap
è bloccato e va risolto prima di proseguire.
