# Codex model routing per Me.Mo.Ri.A

Configurazione compatibile con Codex autenticato tramite account ChatGPT:

- sessione principale: `gpt-5.5`;
- esplorazione leggera: `gpt-5.6-luna`;
- implementazione e revisione tecnica: `gpt-5.6-terra`;
- profilo di ragionamento profondo opzionale: `gpt-5.6-sol`.

L'alias ambiguo `gpt-5.6` non deve essere usato. Utilizzare sempre uno degli ID completi oppure `gpt-5.5`.

Profili disponibili:

```powershell
codex --profile standard
codex --profile luna
codex --profile terra
codex --profile sol
```
