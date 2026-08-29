---
name: memoria-source-registry
description: Modifica una fonte nel registry dichiarativo a quattro livelli con fixture e parsing offline.
---

# Source Registry

Ogni fonte passa dal registry YAML e mantiene separati:

```text
source_profiles
source_strategies
source_result_logic
source_detail_logic
```

La lista risultati può produrre soltanto stati/candidati. `SourceDocument` ed
`EvidenceClaim` possono derivare solo dal dettaglio o da un documento
identificabile. Aggiungi fixture offline e test deterministici; i test live sono
opzionali. Fonti autenticate o dinamiche restano `manual_review` o sessioni
assistite, senza automazione incontrollata.
