# External Data Root — Me.Mo.Ri.A

Il data root operativo del progetto è:

```text
P:\Comune\Me.Mo.Ri.a
```

`memoria-workspace` non deve duplicare questa cartella. Deve solo descriverla tramite `manifest.yml` e script di validazione.

## Struttura attesa

```text
P:\Comune\Me.Mo.Ri.a\
├── inbox\
├── raw\offline\
├── raw\online\
├── processed\ocr_raw\
├── processed\ocr_normalized\
├── processed\chunks\
├── processed\extraction_candidates\
├── graph\jsonld\
├── graph\indexes\
├── graph\snapshots\
├── historian_review\pending\
├── historian_review\approved\
├── historian_review\rejected\
├── reports\
├── exports\
├── logs\
├── config\
└── backups\
```

## Risoluzione path

Ordine consigliato:

1. parametro CLI `--data-root`;
2. variabile ambiente `MEMORIA_DATA_ROOT`;
3. `memoria-workspace/manifest.yml`;
4. errore bloccante.
