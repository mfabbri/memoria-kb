# T58a - Certificazione offline di tre famiglie source

Data: 2026-11-15. Nessuna ricerca live o accesso a dati reali eseguito.

## Matrice capability

| Famiglia | Search | Detail/document | Claim/review | Feedback | Negativi e limiti |
|---|---|---|---|---|---|
| `local_docx` | Non applicabile: selezione manuale di un singolo file, nessun connettore. | Registrazione preview/apply del file esplicito, hash e provenance; text-extract supporta DOCX. | Claim richiedono estrazione/evidenza esplicita; review wizard generico. Nessuna promozione. | Feedback outcome CLI generico, non integrato automaticamente con intake locale. | `no_results` e dettaglio web non applicabili; retry identico/collisione coperti dal test registrazione. |
| `storia_memoria_bo` | Ricerca persone via Playwright, strategia e result logic dichiarative; fixture di hit. | Pagina detail estraibile e registrabile; il sidecar acquisito non prova da solo fedelta o catalog membership. | Claim candidati e review manuale; nessuna scrittura canonica automatica. | Feedback outcome auditabile disponibile ma non legato automaticamente alla pagina. | `no_results` dichiarato dal result logic; detail blocked/missing richiede review; registrazione online storica puo fallire su ID in conflitto. |
| `partigiani_italia` | Ricerca pubblica via form GET; dettaglio usa sessione autenticata manuale/persistente. | Detail fields dichiarativi; autenticazione e handoff manuale. | Claim candidati con receipt; review necessaria. | Feedback outcome generico disponibile, non automatico. | `no_results` dichiarato; login/detail bloccato produce `detail_needs_manual_review`; non si aggira l'autenticazione. |

Le tre famiglie non sono tre connettori equivalenti: `local_docx` e intake file-only; Storia e Memoria ha ricerca/detail pubblici; Partigiani d'Italia ha ricerca pubblica e dettaglio autenticato. Due documenti del dossier T55 non dimostrano indipendenza delle fonti.

## Evidenze offline

- Registry completo valido: `test_sources_registry_validation.py::test_real_registry_is_valid_from_memoria_sources` PASS. Quattro livelli `local_docx` parsati; `detail_level` usa un valore ammesso `detail_document_only`.
- Intake locale/idempotenza: `test_local_source_registration.py` 3 PASS.
- Parser/logic detail e stati blocked: `test_detail_page_logic.py` e `test_authenticated_session.py` inclusi nel gate, 27 test complessivi PASS assieme a search result logic e validator registry.
- Connettori Storia e Memoria e ricerca Partigiani: `test_connectors.py -k "storia_memoria_bo or search_form_get_name_source_builds_public_search_url"`, 5 PASS, 20 deselected.
- Launcher installato: `memoria sources online run --help` verificato; non eseguito alcun comando di ricerca.
- `git diff --check` e planner validator PASS.

## Stop condition e limiti

Certificazione completata solo per i contratti/fixture offline elencati. Non misura disponibilita live, tassi reali `no_results`, accuratezza estrazione o indipendenza archivistica. Nessun profilo/canone modificato; T41 OCR e T27/T28 pCloud restano sospesi. Prossimo candidato va selezionato dai gap misurati, senza aprire milestone automaticamente.
