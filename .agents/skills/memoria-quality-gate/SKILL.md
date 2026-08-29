---
name: memoria-quality-gate
description: Verifica test, contratti, provenance, audit e documentazione dopo un micro-incremento.
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
