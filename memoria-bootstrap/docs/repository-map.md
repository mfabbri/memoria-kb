# Repository Map

## memoria-bootstrap

Metodo operativo, playbook, roadmap, decisioni, ADR e contratti multi-repo.

## memoria-engine

Package Python installabile: CLI, OCR orchestration, parser, chunking,
extraction, source execution, evidence/review store, JSON-LD preview, reporting
e test.

## memoria-workspace

Repository descriptor-only. Contiene manifest e documentazione per risolvere il
workspace operativo; non contiene documenti, OCR, run, database o profili reali.

Il corpus operativo vive fuori da Git, oggi con backend locale compatibile:

```text
P:\Comune\Me.Mo.Ri.a
```

## memoria-knowledge

Conoscenza di dominio: contesto storico, ontologie, glossari, criteri
storiografici, modelli di scheda e terminologia.

## memoria-rules

Regole deterministiche: merge policy, confidence, alias, provenance, review
status, entity lifecycle, validation e contratti LLM versionabili.

## memoria-sources

Registry e logica delle fonti: profili, strategie, result logic, detail logic,
metadata, rate limit e wrapper specifici.

## Regola trasversale

```text
repository leggeri e versionabili
  !=
workspace operativo con dati reali
```

Gli artefatti della golden run sono referenziati dal data root e non copiati nei
repository.
