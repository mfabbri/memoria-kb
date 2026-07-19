# T33 External Funding Brief

Data: 2026-07-18

Stato: sorgente editoriale T33; non approvata come entrypoint della
presentazione esterna. Usare il nuovo
`funding-demo-t33-presentation-entrypoint.md` per la sequenza T33b.

## Scope

Questo brief conserva messaggi e guardrail editoriali da riusare nella
presentazione. Non e' piu' la pagina di ingresso: la prima review umana ha
mostrato che il racconto deve distinguere la golden run tecnica dalla coorte
pilota e dal patrimonio disponibile. Non approva decisioni storiche e non rende
pubblicabile alcuna scheda.

Vincoli rispettati:

- nessuna scrittura nel data root esterno;
- nessuna pipeline, OCR o ricerca live;
- nessuna modifica a profili canonici;
- nessuna promozione di claim o verified facts canonici;
- nessuna applicazione di `ProfilePatch`;
- nessuna copia di documenti reali nei repository.

## Messaggio in 60 secondi

Me.Mo.Ri.A dimostra un metodo controllato per trasformare fonti eterogenee in
evidenze revisionabili. Il workspace contiene 57 profili caricati; una coorte
pilota di 5 profili collega 13 documenti, 24 link persona-documento e 55 claim
candidati a una coda di 114 decisioni storiche. La nuova golden run, dopo la
promozione, approfondisce tre casi nella stessa lineage e mostra provenance,
divergenze, decisioni, verified facts e ProfilePatch preview, oltre a un
feedback loop con esito auditabile.

Il pacchetto prova il metodo, ma la presentazione esterna resta in revisione.
Lo stato tecnico corretto e':

```text
go_with_review_blockers
publication_ready=false
preview_only=true
```

## Cosa mostrare

| Punto | Messaggio | Evidenza |
|---|---|---|
| Problema | Le informazioni storiche sono disperse in fonti non omogenee. | 4 documenti selezionati da `legacy_csv`, `local_docx`, `partigiani_italia`. |
| Metodo | Ogni claim resta collegato a documento, fonte e metodo. | `mvp_demo_reconciliation_table.md`. |
| Valore | Il merge non cancella divergenze o incertezze. | Compatibilita' `corroborated`, `divergent`, `single_source`. |
| Controllo storico | Lo storico decide prima di ogni uso forte. | `review_decisions_summary.md`. |
| Sicurezza editoriale | Fatti e patch restano preview, non canonici. | `verified_facts.preview.md`, `profile_patch.preview.md`. |
| Apprendimento | La review genera una nuova ricerca o un esito tracciato. | `feedback_loop_outcome.t31-demo.md`. |
| Finanziamento | I fondi servono a scalare il metodo, non a sostituire la review. | `funding-demo-t33-funding-roadmap.md`. |

## Apertura consigliata

Formula breve per avviare la presentazione:

```text
Questa demo non presenta schede pronte per la pubblicazione. Presenta una catena
auditabile: fonti diverse, documenti identificati, claim con provenance,
riconciliazione multi-fonte, decisione storica, patch preview e feedback loop.
Il finanziamento serve a rendere questa catena ripetibile su piu' casi, con
storici e curatori al centro del processo.
```

## Chiusura consigliata

Formula breve per chiudere la presentazione:

```text
Il risultato non e' una biografia automatica, ma un metodo gia' dimostrato in
piccolo. Il passo finanziato e' portarlo da caso controllato a pratica
curatoriale: piu' profili, piu' documenti, piu' review, mantenendo provenance,
decision trail e blocco alla pubblicazione automatica.
```

## Cosa non dire

- Non dire che le schede sono pronte per la pubblicazione.
- Non dire che il sistema risolve automaticamente i conflitti storici.
- Non trasformare `needs_manual_review` in una conclusione storica.
- Non presentare claim `unreviewed` come decisioni storiche.
- Non promettere nuove fonti o automazioni non ancora sottoposte a quality gate.

## Legame con il pacchetto

Questo brief va letto insieme a:

1. `funding-demo-t33-package-entrypoint.md`;
2. `funding-demo-t33-demo-case-card.md`;
3. `funding-demo-t33-evidence-flow-diagram.md`;
4. `funding-demo-t33-funding-roadmap.md`;
5. `funding-demo-t33-external-readiness-checklist.md`;
6. `P:\Comune\Me.Mo.Ri.a\risultati\runs\prova-preview-profili-5-reviewed-01-pipeline\mvp_funding_dossier.md`.

Il dossier generato resta la base auditabile. Questo brief serve a evitare che
la presentazione parta da conteggi tecnici o da materiali ancora marcati
`unreviewed`, mantenendo chiaro il confine fra demo finanziabile e
pubblicazione storica.

## Criterio T33 coperto

```text
dossier finanziatori breve collegato alla golden run
```

Il criterio e' soddisfatto come brief editoriale esterno preview-only. La
pubblicazione storica resta bloccata finche' rimangono decisioni pending,
output preview non canonici e feedback outcome `needs_manual_review`.

## Validazione

Validazione read-only prevista:

```powershell
cd memoria-engine
.\.venv\Scripts\memoria.exe mvp demo --data-root "P:\Comune\Me.Mo.Ri.a"
```

Esito atteso:

- descriptor presente e JSON valido;
- status `ready_for_internal_demo`;
- 3 famiglie fonte coperte;
- 4/4 documenti coperti;
- safety flag preview-only confermate;
- nessun file del data root esterno modificato.
