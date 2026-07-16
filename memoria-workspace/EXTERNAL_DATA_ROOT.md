# External Data Root

`memoria-workspace` is a descriptor repository. It must not contain the real Me.Mo.Ri.a data corpus.

The operational data root is external:

```text
P:\Comune\Me.Mo.Ri.a
```

## Path resolution order

Tools should resolve the data root in this order:

1. explicit CLI argument, for example `--data-root "P:\Comune\Me.Mo.Ri.a"`;
2. environment variable `MEMORIA_DATA_ROOT`;
3. `memoria-workspace/manifest.yml` with `workspace.provider: local` and
   `workspace.root`;
4. legacy `data_root.windows_path` in `memoria-workspace/manifest.yml`;
5. fallback to the documented default path above.

The manifest may describe future providers such as pCloud with a
`credentials_ref`, but it must not store tokens or credentials.

## Data policy

- Real PDFs, scans, OCR outputs, generated JSON-LD, review dashboards and backups remain under `P:\Comune\Me.Mo.Ri.a`.
- The Git repository stores only configuration, manifests, templates and validation scripts.
- Never commit personal, archival or licensed source documents unless explicitly approved.
