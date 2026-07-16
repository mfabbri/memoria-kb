# memoria-sources

Cataloghi e wrapper delle fonti Me.Mo.Ri.A.

Contiene descrizioni delle fonti, profili OCR, mapping dei metadati, downloader
e wrapper. Non contiene necessariamente il dataset scaricato: i file reali vanno
nel workspace o nel data root esterno.

## Catalogo fonti

Il catalogo dichiarativo migrato da `memoria-engine/ricerche` vive in:

- `registry/camalanca_fonti.yaml`;
- `registry/camalanca_fonti.md`;
- `source_profiles/`;
- `source_strategies/`;
- `source_result_logic/`;
- `source_detail_logic/`.

`memoria-engine` risolve questa posizione come primaria e mantiene
`memoria-engine/ricerche` solo come fallback legacy durante la transizione.
