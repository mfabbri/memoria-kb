# Engine Architecture

Il motore espone una CLI e moduli Python. Deve restare indipendente dai dati reali e usare contratti di input/output.

Pipeline target:

```text
source registry → raw document → OCR → chunks → extraction candidates → rules validation → JSON-LD → historian review → feedback queries
```
