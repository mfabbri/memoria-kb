# Agent Session Prompt

Usa questo prompt all'inizio di una nuova sessione agent.

```text
Siamo nella nuova architettura multi-repo di Me.Mo.Ri.A.

Root:
D:\CaDiMalanca\me.mo.ri.a-kb

Data root esterno:
P:\Comune\Me.Mo.Ri.a

Leggi prima:
- memoria-bootstrap/docs/roadmap/00-roadmap-master.md
- memoria-bootstrap/docs/roadmap/01-mvp-roadmap.md
- memoria-bootstrap/docs/roadmap/02-technical-roadmap.md
- memoria-bootstrap/docs/funding-demo-golden-path.md
- memoria-bootstrap/docs/current-next-increment.md
- memoria-bootstrap/docs/decision-log.md
- memoria-bootstrap/docs/developer-playbook.md
- memoria-bootstrap/docs/daily-agent-procedure.md
- memoria-bootstrap/docs/cli-discovery-report.md se presente
- checklists/post-migration-validation.md se presente

Determina se il current increment e' ancora aperto.

Se e' aperto:
- lavora solo su quello;
- usa vincoli, comandi di validazione e criteri di accettazione;
- non allargare lo scope.

Se e' chiuso:
- scegli il prossimo incremento dalla roadmap tecnica;
- fino alla chiusura di T33 scegli T29-T33 in ordine;
- T26-T28 cloud e Q2 non sono candidati ordinari, salvo blocco diretto della
  golden run o richiesta esplicita;
- aggiorna current-next-increment.md prima di iniziare.

Obiettivo corrente del progetto:
- creare una golden run finanziatori unica;
- mostrare merge multi-fonte con provenance e conflitti visibili;
- mostrare decisione dello storico e patch preview;
- chiudere almeno un feedback loop dalla review alla nuova ricerca e al suo
  esito;
- non produrre schede pubblicabili definitive.

Esegui un solo incremento piccolo e verificabile.

Regole:
- non chiedere all'utente il prossimo passo salvo ambiguita' bloccante;
- per operazioni sui dati reali, scrivere solo dentro
  P:\Comune\Me.Mo.Ri.a e sue sotto-cartelle, e solo quando serve
  all'incremento corrente documentato;
- non scrivere fuori da P:\Comune\Me.Mo.Ri.a per workflow operativi;
- non cancellare o sovrascrivere massivamente, modificare profili canonici,
  applicare patch o promuovere fatti canonici senza incremento dedicato,
  backup e audit trail;
- non copiare dati reali nei repository Git;
- non lanciare OCR o pipeline fuori dal perimetro dell'incremento;
- non applicare patch ai profili canonici;
- non aggiungere fonti salvo necessita' dimostrata dal caso golden path;
- non fare refactor ampio;
- mantenere separati evidenza, proposta, decisione e pubblicazione;
- aggiornare documentazione e stato a fine incremento;
- aggiornare decision-log.md solo per decisioni architetturali o metodologiche.

Output finale richiesto:
- incremento completato e criteri soddisfatti;
- file creati/modificati;
- validazioni eseguite o non eseguite;
- impatto sulla golden run;
- prossimo incremento determinato dalla roadmap.
```
