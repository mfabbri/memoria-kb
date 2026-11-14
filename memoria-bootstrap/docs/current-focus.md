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
- **Blocco operativo:** T55 richiede registrazione CLI di SourceDocument da un
  file locale generico; il comando disponibile gestisce immagini, OCR o fonti
  online. Il PDF Bendini di T47 resta SearchResult e non è stato acquisito.
- **Dati veri:** fuori da Git. Prima di agire su documenti/profili reali,
  verificare la disponibilità del data root operativo e il consenso sul perimetro.

## Sequenza proposta, una slice per sessione

| ID | Prio | Obiettivo e criterio di uscita |
|---|---|---|
| T53 | P0 | Completato 2026-11-14: baseline read-only; rapporto in `docs/reports/t53-workspace-baseline-2026-11-14.md`. |
| T54 | P0 | Completato 2026-11-14: `claims-build` multi-attempt idempotente, provenance conservata e collisioni incompatibili rifiutate. |
| T55 | P0 | Bloccato: manca una CLI preview/apply per registrare file locali generici come `SourceDocument`; dettaglio in `docs/reports/t55-bendini-pilot-readiness-2026-11-14.md`. |
| T56 | P1 | Completato 2026-11-14: preview tipizzata documento-riferimento/Person/Place/Event; identity match distinto da menzione e fatto storico. |
| T57 | P1 | Rendere recuperabili in sessioni successive evidenze, decisioni e feedback, con vista consolidata e applicazione canonica soltanto autorizzata/auditata. |
| T58 | P2 | Certificare tre famiglie/fonte già nel registry sul percorso end-to-end con fixture, prove e stati `no_results` documentati. |

**Dipendenze:** T53 -> T54 -> T55; T56 è chiuso sulle fixture software e T57
resta dipendente dal dossier T55. T58 viene dopo il primo dossier operativo.
Prima di riprendere T55 serve delimitare il micro-incremento CLI per registrare
un SourceDocument locale esplicito con preview/apply, hash e verifica
idempotente. T27/T28 e T41 restano sospesi.

## Evidenze T53-T56

- Rapporti: `docs/reports/t53-workspace-baseline-2026-11-14.md` e
  `docs/reports/t55-bendini-pilot-readiness-2026-11-14.md`.
- Il data root reale resta autoritativo per profili e catalogo; la copia indice
  nel repository non va usata per correggere o sostituire dati operativi.
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
