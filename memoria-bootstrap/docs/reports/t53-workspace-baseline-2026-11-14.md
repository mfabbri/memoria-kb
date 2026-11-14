# T53 — Baseline read-only del workspace (2026-11-14)

## Perimetro e metodo

Verifica read-only del data root `P:\Comune\Me.Mo.Ri.a`, del descriptor,
dell'indice profili, del catalogo SQLite, degli artifact T47/T49 e del registry.
Nessuna query live, scrittura nel data root, review o modifica canonica.
Il launcher globale `memoria` non è nel PATH; i controlli sono stati eseguiti
con `memoria-engine/.venv/Scripts/memoria.exe` e `--data-root` esplicito.

## Matrice delle evidenze

| Oggetto | Stato | Evidenza |
|---|---|---|
| Data root operativo | presente/verificato | `memoria inventory --section all --output markdown`: le tre sezioni attese sono raggiungibili. |
| Indice profili operativo | presente/verificato | `memoria profiles status`: 60/60 profili caricati, 0 file mancanti. Status: 3 candidate/accepted/unpublished, 57 unknown; nessuna inferenza di approvazione. |
| Copia indice nel repository | presente, divergente | Hash diverso dall'indice operativo; non sostituirli né copiarli. |
| Catalogo SourceDocument / database | presente, contenuto non verificato | `database/evidence.sqlite` esiste; questa baseline non ha eseguito query sul database. |
| T47 Bendini | artifact presente; registrazione non attestata | `t47-run.json` e `t47-summary.md` esistono. Il focus operativo registra che il PDF individuato non era stato registrato come SourceDocument; T47 non vale da registrazione. |
| T49 Toni, Storia e Memoria | artifact presente; apply receipt presente | Run, report e `source-registration-apply.txt` presenti. La baseline non ha interrogato il catalogo per verificare la riga persistita. |
| T49 Toni, Partigiani | artifact presente; apply receipt presente | Run, report e ricevuta `registration-apply-toni.json` presenti. La baseline non ha interrogato il catalogo per verificare la riga persistita. |
| Registry fonti | presente/verificato come file | `memoria-sources/registry/camalanca_fonti.yaml` presente; nessun cambiamento apportato. |

## Hash SHA-256

| Artifact | SHA-256 |
|---|---|
| Data root `ricerche/person_profiles/purocielo.index.jsonld` | `D8C0111E0D3C8C772650D55CC5319CB69C59DBF1CD2331EF985FC1662C5EE08C` |
| Repo `memoria-engine/ricerche/person_profiles/purocielo.index.jsonld` | `22CDBC6CBB8D827EDCD32467BDCF85AF7F55DA86DF55D7BCC118D7AA9B2ED13F` |
| T47 `t47-run.json` | `3B276FD1DFE6FFE993356CF12307E8D1970F2C4CB0F65CDD0B0DF85B224A7165` |
| T47 `t47-summary.md` | `BB4047690B767DBAF3888E84F02299C954CA3E738F1BC75557B95A819501E0D6` |
| T49 Storia e Memoria `source-registration-apply.txt` | `C44900B39D4BC13E18E964EB6B90D5AC62EACC3ABB10EF5772FFD0FF658D88FC` |
| T49 Partigiani `registration-apply-toni.json` | `FF10446D00539BD69677851C3546E65E58E06CDB034FEF1BAD786A49880B3F69` |
| Data root `database/evidence.sqlite` | `847F2CE218F6BC083E7C51C376E21CBC3159D291FA6488C6354FF2A07D58CAFC` |
| Registry `camalanca_fonti.yaml` | `827273CF3BA8E6FC91AC0BAE3B6CC7D61262012608A83731A4CA60ACBBFA93ED` |

## Gap e implicazioni

- Il data root e gli artifact necessari sono accessibili; il suo indice profili
  è la baseline operativa e differisce dalla copia distribuita nel repository.
- T47 Bendini non prova una registrazione SourceDocument: prima di T55 occorre
  usare un documento identificabile già disponibile e registrarne la provenienza
  tramite CLI, oppure delimitare la registrazione come micro-incremento.
- Per Toni esistono ricevute di apply T49, ma non è stata verificata la
  persistenza nel catalogo SQLite; la CLI esistente non espone in questa
  baseline una vista catalogo mirata. Non assumere che una ricevuta equivalga
  alla verifica del record.
- La deduplica T54 va provata su fixture offline; questa baseline non legge
  contenuti di claim né decide equivalenze.

## Comandi e limiti

Eseguiti tramite launcher installato:

```text
memoria.exe inventory --data-root P:\Comune\Me.Mo.Ri.a --section all --output markdown
memoria.exe profiles status --data-root P:\Comune\Me.Mo.Ri.a --output markdown
```

`memoria data-root` e `memoria inventory` senza path esplicito hanno fallito
perché il launcher globale non è nel PATH e l'ambiente non espone
`MEMORIA_DATA_ROOT`; il rerun esplicito sul data root ha avuto esito positivo.
Nessun test eseguito: nessuno script o contratto è cambiato.
