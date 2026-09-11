# Codex Session Contract

## Scopo

Contratto minimo per ogni sessione Codex su Me.Mo.Ri.A.

## Principio guida

```text
fonti -> documenti -> evidenze -> riconciliazione -> schede -> revisione umana -> feedback -> pubblicazione approvata
```

Nessun fatto storico diventa pubblicabile senza fonte tracciabile e revisione
umana.

## Architettura da assumere

Workspace multi-repo:

```text
memoria-bootstrap
memoria-engine
memoria-workspace
memoria-knowledge
memoria-rules
memoria-sources
```

Cuore implementativo installabile:

```text
memoria-engine/code/caduti_fonti_report/
```

Flusso concettuale:

```text
PersonResearchProfile JSON-LD
  -> PersonQuery
  -> SourceDefinition / SearchStrategy
  -> SourceResult
  -> SourceDocument / EvidenceClaim
  -> review decision
  -> verified fact preview / profile patch preview
  -> feedback action / new search run
```

## Direzione CLI

La CLI Python installabile `memoria` e' la superficie canonica futura e gia'
fornisce orientamento read-only.

`scripts/memoria.ps1` resta la superficie compatibile per workflow Windows che
scrivono artefatti preview gia' validati. Non introdurre nuova logica di dominio
nei wrapper e non bloccare T29-T33 per completare la migrazione CLI.

## Priorita' corrente

La corsia prioritaria e':

```text
T29 -> T30 -> T31 -> T32 -> T33
```

Obiettivo: una sola golden run che dimostri merge multi-fonte, decisione umana,
patch preview e feedback loop chiuso.

Cloud T26-T28 e Q2 non sono passi ordinari prima di T33.

## Workspace e dati

Il workspace operativo reale e':

```text
P:\Comune\Me.Mo.Ri.a
```

I repository Git non contengono documenti, run o profili reali destinati
all'operativita'. Usare il data root o input espliciti. Non scrivere run reali
nei repository.

Sorgenti canoniche:

- profili operativi: indice nel data root;
- registry fonti: `memoria-sources/registry/camalanca_fonti.yaml`;
- knowledge: `memoria-knowledge`;
- rules e prompt: `memoria-rules`;
- evidence/review store: workspace `database`, quando disponibile;
- Obsidian: spazio redazionale, non database canonico.

## Guardrail storici

- Una pagina risultati non produce fatti.
- Solo un documento o record identificabile produce claim candidati.
- Seed e search hints sono indizi.
- EvidenceClaim e' un'affermazione documentata, non verita' definitiva.
- Verified facts richiedono decisione approvata e restano preview finche' non
  esiste approvazione editoriale/canonica.
- Il merge multi-fonte mantiene fonti e valori alternativi.
- `no_results` documenta l'esito di una ricerca, non l'inesistenza del fatto.
- ProfilePatch non viene applicata automaticamente.

## Golden run invariants

- un solo `run_id` o una derivazione esplicita e auditabile;
- almeno due fonti eterogenee sullo stesso caso;
- claim, documenti e decisioni collegati;
- almeno una decisione accettata e una incertezza/richiesta di fonti;
- almeno una patch preview;
- almeno un feedback action eseguito a un esito;
- nessun output presentato come pubblicabile senza approvazione.

## Regole operative

- Lavorare per piccoli incrementi testabili.
- Leggere `current-next-increment.md` prima di scegliere il lavoro.
- Aggiornare solo i documenti direttamente impattati.
- Usare fixture offline.
- Non fare scraping aggressivo.
- Non salvare credenziali.
- Non aggiungere fonti salvo scope T29-T31.
- Non fare refactor ampi.
- Riportare file, test, rischi e impatto sulla golden run.

## Checklist di applicazione canonica

Quando un incremento autorizzato deve trasformare un artefatto preview in una
modifica canonica, completare tutti i gate seguenti e conservarne gli artefatti
collegati allo stesso `run_id` o identificativo equivalente:

1. **Revisione umana esplicita**: ogni operazione è stata esaminata e ha una
   decisione tracciabile, con reviewer e stato finale.
2. **Piano, provenance e hash**: il piano dichiara target, operazioni, fonti,
   decisioni, hash degli input e hash attesi dei target prima dell'applicazione.
3. **Dry-run**: il dry-run deterministico conferma conteggi, operazioni,
   collisioni, precondizioni e assenza di scritture canoniche.
4. **Autorizzazione separata**: l'autorizzazione all'applicazione è esplicita,
   riferita al piano e distinta dalla revisione o dalla produzione del dry-run.
5. **Backup**: prima della scrittura esiste un backup verificabile dei target e
   del relativo indice o manifest, con percorso, timestamp e hash.
6. **Applicazione controllata**: si scrive soltanto il set autorizzato e si
   registrano operazioni riuscite, saltate o fallite senza ampliare lo scope.
7. **Audit post-run**: dopo la scrittura si verificano hash, conteggi,
   provenance, stato dei target, backup e assenza di claim promossi
   implicitamente; l'esito viene registrato.
8. **Rollback condizionato agli hash**: si ripristina solo se gli hash correnti
   corrispondono alle condizioni attese e il backup è quello del piano; in caso
   contrario si interrompe e si richiede revisione manuale.

Se un gate manca, l'operazione resta preview/dry-run e non modifica il canonico.
La checklist è un contratto riutilizzabile: non sostituisce la revisione
storica, l'autorizzazione dell'incremento o i contratti specifici del dominio.

## Stop condition

Fermarsi o richiedere revisione umana se il task richiede:

```text
approvazione claim
verified_facts canonici
merge profili reali
risoluzione conflitti storici
pubblicazione schede
credenziali o sessioni private
scraping massivo
```
