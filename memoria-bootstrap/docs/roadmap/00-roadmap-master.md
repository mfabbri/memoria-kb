# Roadmap Master Post-Migrazione

Data: 2026-07-12

Scope: architettura multi-repo Me.Mo.Ri.A in `D:\CaDiMalanca\me.mo.ri.a-kb`.

## Architettura di riferimento

La workspace e' organizzata in repository separati:

- `memoria-bootstrap`: metodo operativo, playbook, roadmap, decisioni e contratti;
- `memoria-engine`: codice installabile e testabile, inclusa la CLI Python `memoria`;
- `memoria-workspace`: descrittore della workspace, senza dati reali versionati;
- `memoria-knowledge`: conoscenza di dominio, glossari, criteri e modelli;
- `memoria-rules`: regole deterministiche di provenance, merge, review e validazione;
- `memoria-sources`: cataloghi, wrapper e metadata delle fonti.

Il workspace operativo reale resta esterno ai repository Git. Il backend locale
compatibile e':

```text
P:\Comune\Me.Mo.Ri.a
```

La destinazione architetturale non e' un drive specifico: il workspace e' una
risorsa logica con backend configurabile. Il backend locale resta la superficie
pratica per l'MVP; provider cloud futuri non devono bloccare la demo.

## Principio MVP

L'MVP non e' produzione automatica di schede pubblicabili definitive.

L'MVP deve dimostrare un percorso verificabile:

```text
documenti grezzi e fonti eterogenee
  -> documenti identificabili
  -> evidenze con provenance
  -> riconciliazione multi-fonte
  -> decisione dello storico
  -> scheda/profilo revisionabile e patch preview
  -> feedback di ricerca
  -> nuova interrogazione o esito documentato
```

Ogni output deve distinguere evidenza, proposta automatica, decisione umana e
stato di pubblicabilita'.

## Criteri obbligatori per l'MVP finanziatori

La demo e' finanziabile solo quando mostra nello stesso caso di studio:

1. almeno due documenti provenienti da fonti o famiglie documentali differenti;
2. una vista unica che mantiene provenance, divergenze e incertezze;
3. almeno una decisione storica esplicita su un claim;
4. almeno un `verified_fact` o equivalente esclusivamente preview;
5. almeno una `ProfilePatch` preview collegata a documento, claim e decisione;
6. almeno un feedback loop chiuso, dalla richiesta di nuova ricerca all'esito;
7. una sola run canonica e ripetibile usata da tutti gli artefatti della demo.

Il merge multi-fonte non significa appiattire le fonti. Significa ricondurre
claim compatibili o conflittuali allo stesso soggetto, conservando sempre il
contributo specifico di ciascun documento.

Il feedback loop non e' dimostrato dalla sola generazione di centinaia di query.
Deve esistere almeno un percorso auditabile:

```text
gap o conflitto
  -> decisione dello storico `request_more_sources` o equivalente
  -> piano di ricerca fonte-specifico
  -> esecuzione controllata
  -> nuovo documento/evidenza oppure `no_results` documentato
  -> aggiornamento della memoria di ricerca del profilo
```

## Sequenza roadmap aggiornata

1. Stabilizzare il perimetro post-migrazione. **Completato**.
2. Rendere `memoria-engine` installabile, testabile e diagnosticabile.
   **Completato**.
3. Separare codice, workspace, knowledge, rules e sources. **Completato**.
4. Esporre orientamento read-only tramite CLI Python. **Completato per il
   perimetro attuale**.
5. Definire il contratto della golden run finanziatori. **T29, prioritario**.
6. Produrre una run canonica con merge multi-fonte e artefatti coerenti. **T30**.
7. Chiudere almeno un feedback loop storico. **T31**.
8. Correggere incoerenze, test e presentazione della demo. **T32**.
9. Preparare il pacchetto finanziatori e il walkthrough. **T33**.
10. Riprendere storage cloud, nuove fonti o micro-refactor non bloccanti solo
    dopo T33 o su richiesta esplicita.

## Direzione CLI

La superficie canonica futura e' il console script Python installabile
`memoria`, utilizzabile su Windows e Linux. I wrapper OS-specifici devono
progressivamente diventare facciate sottili.

Per l'MVP finanziatori, i workflow PowerShell gia' validati possono restare la
superficie operativa per le azioni preview che scrivono artefatti. La CLI Python
fornisce orientamento e stato read-only. La migrazione completa dei workflow non
deve ritardare T29-T33.

## Stato corrente

Completato:

- struttura multi-repo;
- data root esterno;
- package installabile e suite test ampia;
- CLI `memoria` con diagnostica e bridge read-only;
- catalogo fonti in `memoria-sources`;
- knowledge in `memoria-knowledge`;
- prompt e contratti LLM in `memoria-rules`;
- evidence/review store e output preview gia' presenti;
- interfaccia `WorkspaceStorage` e driver locale;
- manifest provider-aware.

Capacita' gia' osservabili ma non ancora confezionate in una golden run unica:

- documenti e claim candidati;
- decisioni di review;
- verified facts preview;
- profile patch preview;
- piani di feedback;
- dossier e report MVP distribuiti fra run differenti.

## Focus immediato

Il focus e' T29-T33. Fino alla chiusura del pacchetto finanziatori:

- T26-T28 cloud restano in hold;
- Q2 e altri refactor sono ammessi solo se bloccano direttamente la golden run;
- non si aggiungono nuove fonti salvo quelle indispensabili al caso selezionato;
- non si amplia il numero di profili prima di avere una storia dimostrativa
  coerente.

Documento operativo di riferimento:

```text
memoria-bootstrap/docs/funding-demo-golden-path.md
```

## Fuori scope per la golden run

- produzione massiva di schede;
- pubblicazione automatica;
- risoluzione automatica dei conflitti storici;
- migrazione cloud massiva;
- nuove acquisizioni indiscriminate;
- modifica canonica dei profili reali senza backup, decisione e audit;
- presentazione di output preview come fatti pubblicabili.
