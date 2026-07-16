# Roadmap Task Selector

## Scopo

Scegliere il prossimo micro-incremento dalla roadmap corrente senza usare una
backlog statica e senza ricadere in documenti pre-migrazione.

## Fonti autorevoli

Direzione e milestone:

```text
memoria-bootstrap/docs/roadmap/00-roadmap-master.md
memoria-bootstrap/docs/roadmap/01-mvp-roadmap.md
memoria-bootstrap/docs/roadmap/02-technical-roadmap.md
memoria-bootstrap/docs/funding-demo-golden-path.md
```

Stato operativo della sessione:

```text
memoria-bootstrap/docs/current-next-increment.md
```

Decisioni:

```text
memoria-bootstrap/docs/decision-log.md
```

`current-next-increment.md` non sostituisce le roadmap, ma e' il puntatore
operativo autorevole: se dichiara un incremento aperto, Codex continua quello e
non ne seleziona un altro.

## Regola di priorita' corrente

Fino alla chiusura di T33:

1. continuare T29-T33 in ordine;
2. non scegliere T26-T28 cloud come incremento ordinario;
3. non scegliere Q2 salvo blocco diretto della golden run;
4. non aggiungere fonti salvo necessita' del caso selezionato;
5. preferire il minimo cambiamento che rende piu' evidente merge multi-fonte,
   decisione umana, patch preview o feedback loop.

## Procedura token-saving

1. Leggere il titolo, stato e criteri del current increment.
2. Aprire solo la relativa sezione della roadmap tecnica.
3. Aprire `funding-demo-golden-path.md` per i criteri di prova.
4. Identificare i file minimi e un test/verifica mirata.
5. Aggiornare il current increment solo quando quello precedente e' chiuso.

## Forma dell'incremento scelto

Prima di implementare, dichiarare:

```text
incremento roadmap
criteri di ingresso verificati
scope minimo
file candidati
test o verifica read-only
documentation touchpoint
impatto sulla golden run
stop condition
```

## Criteri di scelta dopo T33

Solo dopo T33 tornano candidati ordinari:

- cloud workspace T26-T28;
- nuovi Q2;
- espansione fonti;
- ampliamento dei profili pilota.

## Quando fermarsi

Fermarsi e richiedere revisione umana se il task richiede:

```text
scelta storica sostanziale
approvazione claim
merge sul profilo canonico
risoluzione definitiva di conflitti
pubblicazione
credenziali o accesso privato
scraping massivo
```
