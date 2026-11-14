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
- **MVP finanziatori:** T29-T33 chiusi. T34/T34b e T45-T52 chiusi secondo gli
  artifact e i gate registrati. Nessuna nuova golden run come prerequisito.
- **Dati veri:** fuori da Git. Prima di agire su documenti/profili reali,
  verificare la disponibilità del data root operativo e il consenso sul perimetro.

## Sequenza proposta, una slice per sessione

| ID | Prio | Obiettivo e criterio di uscita |
|---|---|---|
| T53 | P0 | Baseline read-only del data root reale vs indici e catalogo dichiarati; inventario gap e prove riproducibili, nessuna modifica canonica. |
| T54 | P0 | Deduplica multi-attempt in `claims-build`: accorpa soltanto claim effettivamente equivalenti conservando tutti gli attempt; rifiuta ID collision incoerenti; fixture e test CLI. |
| T55 | P0 | Pilot Bendini: collegare almeno due documenti identificabili online/offline, confrontare claim, mostrare conflitti e review candidate, dossier unico senza canonizzazione. |
| T56 | P1 | Relazioni candidate Person/Place/HistoricalEvent tipizzate, con source document, evidenza e review; nessuna equivalenza inventata. |
| T57 | P1 | Rendere recuperabili in sessioni successive evidenze, decisioni e feedback, con vista consolidata e applicazione canonica soltanto autorizzata/auditata. |
| T58 | P2 | Certificare tre famiglie/fonte già nel registry sul percorso end-to-end con fixture, prove e stati `no_results` documentati. |

**Dipendenze:** T53 -> T54 -> T55; T56 e T57 si appoggiano ai gap misurati da
T55; T58 dopo il primo dossier operativo. I task T54-T58 sono roadmap **non
implementazione già avvenuta**. Eseguire solo il primo incremento non concluso
la cui dipendenza è soddisfatta e che resta allineato alla decisione utente.

## T53: primo incremento selezionabile (non già avviato)

- Read-only: confrontare profili e indice canonico nel data root con i file
  distribuiti dal repo, inventariare catalogo `SourceDocument`, ricerca Bendini
  T47 e report Toni T49. Contrassegnare artefatti non disponibili, non inventarli.
- Output: matrice `presente/verificato/mancante/non accessibile`, hash/ID delle
  prove accessibili, gap reali per T54/T55 e rischio su futuri apply.
- Gate: nessuna scrittura sul data root, nessuna query live, differenze e comandi
  di verifica riportati; test solo se cambiano script o contratti.
- Non correggere i 57 profili copiati dal vecchio ZIP come fossero canonici:
  la migrazione effettiva 2026-11-08 è attestata nel data root esterno.

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
