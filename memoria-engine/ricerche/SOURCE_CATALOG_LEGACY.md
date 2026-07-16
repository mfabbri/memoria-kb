# Source Catalog Legacy Removed

Data: 2026-07-06

Le directory seguenti erano duplicati legacy del catalogo fonte ora primario in
`../memoria-sources` e sono state rimosse in T8:

- `source_profiles/`;
- `source_strategies/`;
- `source_result_logic/`;
- `source_detail_logic/`.

Non usare piu' `memoria-engine/ricerche` per cataloghi, profili o logiche fonte.

La posizione primaria e' `../memoria-sources`. Il file
`camalanca_fonti.yaml` rimasto in questa cartella e' solo un fallback storico di
compatibilita' e non deve essere usato come default operativo.
