# Post-migration validation

Note: this filename contains the historical typo `velidation`. The updated
checklist for the current validation run is `post-migration-validation.md`.

## Layout
- [ ] memoria-bootstrap exists
- [ ] memoria-engine exists
- [ ] memoria-knowledge exists
- [ ] memoria-rules exists
- [ ] memoria-sources exists
- [ ] memoria-workspace exists

## External data root
- [ ] P:\Comune\Me.Mo.Ri.a exists
- [ ] Data root contains risultati
- [ ] Data root contains documenti_da_processare
- [ ] Data root contains documenti_processati
- [ ] Data root contains docs
- [ ] Data root contains logs
- [ ] Data root contains ricerche
- [ ] Data root contains archivi
- [ ] Data root contains secure
- [ ] Data root contains database

## Engine
- [ ] Python virtualenv created
- [ ] pip install -e . works
- [ ] pytest runs
- [ ] no hardcoded dependency on old root path
- [ ] no dependency on copied data files

## Safety
- [ ] no WordPress folders copied
- [ ] no PDF corpus copied into Git repos
- [ ] no OCR bulk output copied into Git repos
- [ ] no personal/secure files copied into Git repos
