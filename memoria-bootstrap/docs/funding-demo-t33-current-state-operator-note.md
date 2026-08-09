# T33 Current State Operator Note

Data: 2026-08-09

## Scopo

Questa nota serve a orientare rapidamente un operatore prima di lavorare sulla
demo finanziatori. Non sostituisce il runbook T33 e non autorizza pubblicazione,
ProfilePatch o verified facts canonici.

## Stato semplice

La demo ufficiale attiva e' ora la golden run a tre casi:

```text
funding-demo-golden-3cases-v1-pipeline
```

Questa run e' una demo revisionabile e non pubblicabile. Mostra il metodo:
provenance, riconciliazione multi-fonte, review umana, verified facts preview,
ProfilePatch preview e feedback loop. Non modifica i profili canonici.

## Cosa e' stato ottenuto

- la demo attiva usa 3 profili: 1 principale e 2 complementari;
- usa 5 documenti sorgente;
- copre 3 famiglie fonte: `legacy_csv`, `local_docx`, `partigiani_italia`;
- dichiara 12 artefatti e li trova tutti presenti;
- il ledger attivo della demo contiene 3 profili;
- i 57 profili del patrimonio restano disponibili come contesto, non come
  schede complete o pubblicabili.

## Cosa non e' stato fatto

- nessuna ProfilePatch applicata;
- nessun verified fact canonico creato;
- nessun profilo canonico modificato;
- nessuna scheda pubblicata;
- nessuna decisione storica pending trasformata in fatto.

## Verifica minima

Da `memoria-engine`:

```powershell
.\.venv\Scripts\memoria.exe mvp status --data-root "P:\Comune\Me.Mo.Ri.a"
```

Righe da controllare:

```text
Run canonica: funding-demo-golden-3cases-v1-pipeline
Artefatti presenti: 12
Preview-only: true
Publication ready: false
Profili ledger attivo: 3
```

Per una verifica piu' dettagliata:

```powershell
.\.venv\Scripts\memoria.exe mvp demo --data-root "P:\Comune\Me.Mo.Ri.a"
```

Righe da controllare:

```text
Profili principali: 1
Profili contrasto: 2
Documenti sorgente: 5
Famiglie fonte: legacy_csv, local_docx, partigiani_italia
applies_profile_patch: false
creates_canonical_verified_facts: false
modifies_canonical_profiles: false
publication_ready: false
```

## Backup della promozione

Prima della promozione e' stato creato questo backup del descriptor attivo:

```text
P:\Comune\Me.Mo.Ri.a\database\memoria_mvp_demo.active.before-funding-demo-golden-3cases-v1-20260809-170417.json
```

Usarlo solo per rollback esplicito e motivato.

## Come aggiungere nuovi dati

Non modificare direttamente la golden run attiva.

Per aggiungere dati, aprire una nuova run candidata preview-only:

```text
nuovi documenti
  -> nuova run candidata
  -> claim candidati
  -> review umana
  -> verified facts preview / ProfilePatch preview
  -> eventuale nuova candidata golden
  -> promozione solo dopo approvazione esplicita
```

Percorso consigliato:

1. mettere i nuovi documenti nel data root esterno, non nei repository Git;
2. fare un preflight read-only dei documenti e dei profili coinvolti;
3. lanciare una run piccola e nominata, mai una pipeline massiva indistinta;
4. produrre review queue e claim candidati;
5. passare dalla review umana;
6. generare solo preview;
7. promuovere un nuovo descriptor solo dopo gate tecnico e approvazione
   esplicita.

## Primo comando utile per nuove run

Prima di decidere il perimetro:

```powershell
.\.venv\Scripts\memoria.exe sources offline status --data-root "P:\Comune\Me.Mo.Ri.a"
```

Serve a vedere lo stato superficiale dei documenti offline senza creare run,
senza OCR e senza modificare il data root.

## Dove si trova questa nota

Questa nota e' collegata da:

- `funding-demo-t33-presentation-entrypoint.md`;
- `funding-demo-t33-package-entrypoint.md`;
- `current-next-increment.md`.
