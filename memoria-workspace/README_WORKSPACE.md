# Workspace operativo

## Cartelle principali

- `inbox/`: nuovi file in arrivo.
- `raw/`: documenti normalizzati per fonte.
- `processed/ocr/`: testo OCR e metadati.
- `processed/chunks/`: segmenti testuali.
- `processed/candidates/`: candidate entities generate dall'AI.
- `graph/jsonld/`: entità JSON-LD validate o in review.
- `historian_review/`: dashboard, decisioni, conflitti e feedback.
- `snapshots/`: congelamenti periodici riproducibili.

## External data root

This workspace points to the external operational folder:

```text
P:\Comune\Me.Mo.Ri.a
```

Do not copy the full data corpus into this repository. Use `MEMORIA_DATA_ROOT` or `config/project.local.yaml` to bind the descriptor repo to the external data root.
