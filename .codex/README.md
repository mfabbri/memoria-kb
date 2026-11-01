# Codex agent e routing — Me.Mo.Ri.A v3.1

Configurazione unica alla radice del workspace: `.codex/config.toml`;
non creare altre directory `.codex` nei sei repository figli.

Il controller e' GPT-6 Luna/low. I custom agent sono **disponibili**, non
obbligatori: le operazioni brevi sono dirette, gli incrementi runtime
sostanziali usano Sol/medium, la review indipendente solo quando giustificata,
i trade-off complessi Astra/low. Vedi
`memoria-bootstrap/docs/model-routing-policy.md`.

`/model` verifica la disponibilita' effettiva; la configurazione non garantisce
che un modello possa essere avviato nell'account. Il planner registra la route
intenzionale, gli hook trusted `/hooks` registrano eventi runtime in
`memoria-bootstrap/planning/.runtime/model-routing.ndjson`. Non assumere che il
model id sia sempre presente nell'evento. Le route storiche 2.x e 3.0 restano.

Validazione:

```powershell
& .\memoria-engine\.venv\Scripts\python.exe .\memoria-bootstrap\planning\validate-codex-model-routing.py
python -m json.tool .\memoria-bootstrap\planning\current-work.json
git diff --check
```

Per risparmiare token: skill e contratti on-demand, handoff solo con path e
criteri, nessun fan-out automatico e niente ripetizione del playbook OCR nel
prompt di avvio. Per misurare costi e cache vedi la policy v3.1.
