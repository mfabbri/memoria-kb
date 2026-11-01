# Evoluzione routing Codex 3.0 -> 3.1 (2026-11-01)

La migrazione 3.0 del 2026-10-02 ha introdotto i modelli GPT-6 e skill
focalizzate. La v3.1 conserva i modelli configurati ma elimina il presupposto
che ogni modifica debba essere delegata.

- Parent Luna/low per discovery, docs e fix meccanici direttamente eseguibili.
- Sol/medium per implementazioni sostanziali e review con rischio concreto.
- Astra/low per decisioni ambigue di architettura.
- Skill su richiesta; OCR dettagliato solo in `codex-document-analysis-core.md`;
  `AGENTS.md` e prompt quotidiano sono ridotti.
- Record storici 2.x/3.0 invariati; nuovi routing `policy_version: 3.1`.
- La cache dei prompt della Responses API non e' una configurazione Codex;
  misurare token/costi e non promettere risparmi senza baseline.

## Validazione Windows dalla radice del workspace

```powershell
& .\memoria-engine\.venv\Scripts\python.exe .\memoria-bootstrap\planning\validate-codex-model-routing.py
python -m json.tool .\memoria-bootstrap\planning\current-work.json
git diff --check
```

Se la validazione `jsonschema` non e' disponibile, il validatore emette WARN:
non considerarla una validazione completa. Dopo aggiornamenti hook, usare
`/hooks`; per verificare un modello, usare `/model`.
