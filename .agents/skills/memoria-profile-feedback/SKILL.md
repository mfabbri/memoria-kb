---
name: memoria-profile-feedback
description: Implementa feedback preview-only, CandidateProfileUpdate e CandidateNewProfile con revisione e audit.
---

# Profile Feedback

Mantieni separati:

- `seed` e `searchHints`: memoria di ricerca, non pubblicabile;
- `evidenceClaims`: pubblicabili soltanto dopo revisione;
- `relatedPersonHints`: proposte di nuova indagine;
- `verifiedFacts`: claim approvati e riconciliati.

Flusso obbligatorio:

```text
EvidenceClaim / SourceDocument
  -> CandidateProfileUpdate / CandidateNewProfile
  -> revisione umana
  -> ProfilePatch
  -> merge controllato e auditato
```

Nessun aggiornamento automatico dei profili reali. Ogni patch deve essere
riproducibile, revisionabile e associata alla decisione che l'ha autorizzata.
