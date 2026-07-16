# Daily Agent Procedure

Data: 2026-07-12

## Scopo

Permettere all'agent di determinare autonomamente il prossimo incremento piccolo
e verificabile, mantenendo la priorita' sulla golden run finanziatori.

## Documenti da leggere a inizio sessione

1. `memoria-bootstrap/docs/roadmap/00-roadmap-master.md`
2. `memoria-bootstrap/docs/roadmap/01-mvp-roadmap.md`
3. `memoria-bootstrap/docs/roadmap/02-technical-roadmap.md`
4. `memoria-bootstrap/docs/funding-demo-golden-path.md`
5. `memoria-bootstrap/docs/current-next-increment.md`
6. `memoria-bootstrap/docs/decision-log.md`
7. `memoria-bootstrap/docs/developer-playbook.md`
8. il solo playbook verticale pertinente
9. `checklists/post-migration-validation.md`, se necessario

## Gerarchia delle fonti operative

- Le tre roadmap definiscono direzione e milestone.
- `funding-demo-golden-path.md` definisce i criteri di prova finanziatori.
- `current-next-increment.md` e' il puntatore operativo autorevole della
  sessione corrente.
- `decision-log.md` conserva le decisioni architetturali e metodologiche.

In caso di conflitto, non scegliere autonomamente una vecchia roadmap o un
playbook obsoleto: correggere il riferimento documentale nello stesso
incremento se rientra nello scope.

## Ciclo operativo

1. Leggere il current increment.
2. Se e' aperto, continuare solo quello.
3. Se e' chiuso, scegliere la milestone successiva con dipendenze soddisfatte.
4. Fino alla chiusura di T33, scegliere T29-T33 in ordine.
5. Considerare T26-T28 o Q2 solo se:
   - l'utente lo richiede esplicitamente; oppure
   - il task rimuove un blocco diretto documentato della golden run.
6. Aggiornare `current-next-increment.md` prima di nuovo lavoro.
7. Eseguire un solo incremento.
8. Aggiornare roadmap o decision log solo quando necessario.
9. Chiudere con test, documentazione e impatto sulla golden run.

## Regole per T29-T33

Ogni incremento deve proteggere questi criteri:

- una sola golden run;
- almeno due fonti eterogenee nello stesso caso;
- provenance e conflitti visibili;
- decisione umana esplicita;
- patch solo preview;
- feedback loop realmente eseguito;
- nessuna pubblicazione automatica.

## Divieti operativi

- Per operazioni sui dati reali, scrivere solo dentro
  `P:\Comune\Me.Mo.Ri.a` e sue sotto-cartelle, e solo quando serve
  all'incremento corrente documentato.
- Non scrivere dati reali fuori da `P:\Comune\Me.Mo.Ri.a`.
- Non cancellare o sovrascrivere massivamente, modificare profili canonici,
  applicare patch o promuovere fatti canonici senza incremento dedicato,
  backup e audit trail.
- Non copiare dati reali nei repository Git.
- Non aggiungere nuove fonti per ampliare genericamente la copertura.
- Non lanciare OCR o pipeline fuori dal perimetro del current increment.
- Non applicare patch ai profili canonici.
- Non risolvere conflitti storici automaticamente.
- Non fare refactor ampi.
- Non scegliere pCloud come prossimo passo mentre T29-T33 sono aperti.

## Chiusura sessione

Prima del messaggio finale:

- verificare i criteri di uscita dell'incremento;
- aggiornare `current-next-increment.md`;
- aggiornare `decision-log.md` solo per nuove decisioni;
- dichiarare test eseguiti e non eseguiti;
- dichiarare l'effetto sulla golden run;
- indicare il prossimo incremento derivato dalla roadmap, senza chiedere
  all'utente di sceglierlo salvo ambiguita' bloccante.
