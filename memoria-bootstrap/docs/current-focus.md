# Focus operativo Me.Mo.Ri.A. — 2026-11-14

Questo è il **punto di ingresso breve** per selezionare lavoro post-MVP.
La roadmap tecnica resta la fonte di verità del backlog; i log T29-T52 sono
storici. Non aggiornare questo documento per ogni sessione: aggiornalo solo
quando cambia una priorità o si completa una milestone.

## Decisione di prodotto

- **Priorità P0:** rendere ripetibile il percorso fonte online/offline ->
  `SourceDocument` -> `EvidenceClaim` -> riconciliazione -> review -> feedback ->
  memoria di ricerca. Misurare esiti reali, non quantità di CLI o connettori.
- **Sospesi senza data:** T41 OCR formale e T27/T28 pCloud. Non selezionarli
  automaticamente; restano backlog differito fino a nuova decisione utente.
- **MVP finanziatori:** T29-T33 chiusi. T34/T34b e T45-T54/T56 chiusi secondo gli
  artifact e i gate registrati. Nessuna nuova golden run come prerequisito.
- **T55:** completato 2026-11-15 con dossier Bendini review-only. Sei claim accettati come candidati; identita e divergenze non risolte. Il PDF T47 resta SearchResult.

- **Dati veri:** fuori da Git. Prima di agire su documenti/profili reali,
  verificare la disponibilità del data root operativo e il consenso sul perimetro.

## Sequenza proposta, una slice per sessione

| ID | Prio | Obiettivo e criterio di uscita |
|---|---|---|
| T53 | P0 | Completato 2026-11-14: baseline read-only. |
| T54 | P0 | Completato 2026-11-14: claims-build multi-attempt idempotente. |
| T55 | P0 | Completato 2026-11-15: dossier Bendini e 6 decisioni accept_candidate; nessuna canonizzazione. |
| T56 | P1 | Completato 2026-11-14: relazioni candidate tipizzate. |
| T57a | P1 | Completato 2026-11-15: CLI verifica receipt/artifact; risolve relocation T52 e diagnostica catalog drift. |
| T57b | P1 | Completato 2026-11-15: vista deterministica da due sessioni; 15 decisioni, 3 divergenze, feedback assente esplicito, no canonical write. |
| T58a | P2 | Completato 2026-11-15: matrice offline di local_docx, storia_memoria_bo e partigiani_italia; report in `docs/reports/t58a-source-family-certification-2026-11-15.md`. |
| T59a | P1 | Completato 2026-11-15: verifica exact-match delle citazioni; sul dossier T55 3 esatte e 3 non esatte, senza modifiche alle decisioni. |
| T59b | P1 | Completato 2026-11-15: preview di lineage esplicita tra SourceDocument; membership read-only e stato unreviewed. |
| T59c | P1 | Completato 2026-11-15: memory view include lineage e quote-check con provenance degli artifact. |

**Dipendenze:** T53 -> T54 -> T55 -> T56 -> T57a -> T57b -> T58a -> T59a -> T59b -> T59c. T59c e' chiuso; prossimo candidato da selezionare dai gap misurati.
T41 e T27/T28 restano sospesi. T57a e T57b sono capability CLI chiuse; la vista resta read-only.

## Evidenze T53-T58a

- Rapporti: `docs/reports/t53-workspace-baseline-2026-11-14.md` e
  `docs/reports/t55-bendini-pilot-readiness-2026-11-14.md`; dossier T55 nel run persistente `t55-bendini-dossier-20261115`.
- Il data root reale resta autoritativo per profili e catalogo; la copia indice
  nel repository non va usata per correggere o sostituire dati operativi.
- T55 receipt: sei `accept_candidate` nel wizard per birth date (DOCX ambiguo e
  pagina), death date (11/12 ottobre) e formazione. Nessun claim promosso.
- T57a: `memoria review memory-inventory` verifica T52/T55; 8 artifact verificati,
  relocation risolta da manifest, snapshot catalogo T52 in drift storico. Tre test PASS.
- T57b: `memoria review memory-view` ripetuta in processi separati: 15 decisioni,
  3 conflitti, feedback not_provided, canonical_write_allowed=false; 2 test PASS.
- T58a: tre famiglie certificate offline; report capability e gap in `docs/reports/t58a-source-family-certification-2026-11-15.md`. Nessun live run.
- T59a: `memoria review evidence-verify` sul dossier T55: 3/6 quote exact-match e 3/6 non esatte. Report diagnostico nel run T55; claim e receipt invariati.
- T59b: `memoria review source-lineage-preview` genera `CandidateSourceDocumentLineageSet` da coppie esplicite, verifica gli ID nel catalogo read-only, rifiuta missing/duplicate e marca i legami `unreviewed`. Due test offline PASS; preview T55 collega local capture e ID online citato dal sidecar, senza applicare il legame al catalogo.
- T59c: `memoria review memory-view` accetta artifact lineage e quote-verification ripetibili e ne riporta status, hash e riferimento; 3 test mirati PASS. Vista T55: 1 lineage link e 6 quote (3 exact, 3 not exact). Nessuna promozione claim o scrittura canonica.
- T54 deduplica solo a parità di ID e payload semantico; non deduplica per solo
  valore.
- T56 compone link candidati con `memoria documents relationship-preview`;
  la preview non verifica l'esistenza del SourceDocument nel catalogo.

## Note per T54 e T55

- Il fail-closed T51 `claims-build` su report T49 con due attempt può rifiutare
  claim ID duplicati: verificare prima semantica di ID, quote, provenienza e
  report; non deduplicare per il solo valore di una proprietà. Non perdere
  `attempt_id`, source document o collisioni non equivalenti.
- T47 Bendini contiene candidate e un PDF individuato ma **non registrato**:
  non considerarlo SourceDocument fino alla registrazione identificabile.
  Riusare il materiale autorizzato già disponibile; nuove ricerche live solo
  con fonte, strategia e query esplicitamente autorizzate.
- Review umana = decisione effettiva, mai simulata. Claim unreviewed != fatto.

## Come usarlo

1. `python memoria-bootstrap/planning/current-work-summary.py` (solo lettura).
2. Se l'incremento è aperto e valido, riprenderlo; se completato, scegliere
   da questo focus + sezione T53-T58 della roadmap tecnica.
3. Registrare l'envelope nel planner **solo all'avvio**; preservare note
   storiche e non aggiungere cronache prolisse.
4. Applicare il quality gate mirato e chiudere con prove e prossimo candidato.

Dettaglio storico: `docs/current-next-increment.md` (append-only),
`docs/roadmap/02-technical-roadmap.md` e `docs/decision-log.md`.
