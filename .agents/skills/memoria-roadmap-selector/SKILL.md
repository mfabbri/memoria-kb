---
name: memoria-roadmap-selector
description: Seleziona un solo micro-incremento dalle roadmap autorevoli senza caricarle integralmente.
---

# Roadmap Selector

1. Cerca nelle roadmap con `rg` intestazioni, priorità, gap, milestone, criteri
   di ingresso/uscita e riferimenti a CLI, review store, merge multi-fonte e
   feedback loop.
2. Apri solo le sezioni pertinenti alla fase corrente.
3. Estrai 2-4 candidati.
4. Scegli quello che massimizza: sblocco MVP, provenance/audit, testabilità
   offline, riduzione del rischio, avanzamento reale della roadmap e minimo
   numero di file.
5. Evita nuove fonti live, pubblicazione, merge automatici e decisioni storiche.
6. Non selezionare un incremento test-only se i test sono soltanto prerequisiti
   per un'implementazione già delimitata e non esiste un blocco reale. In quel
   caso accorpa test e implementazione nello stesso micro-incremento. Se il
   test-only è necessario, registra il blocco o il valore indipendente nel
   task envelope.

Output:

```text
micro-incremento scelto:
sezioni roadmap:
motivazione:
scope:
file candidati:
test:
documentazione/CLI touchpoint:
stop condition:
```
