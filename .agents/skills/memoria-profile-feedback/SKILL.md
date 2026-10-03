---
name: memoria-profile-feedback
description: Build preview-only profile feedback and candidate profile updates.
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
