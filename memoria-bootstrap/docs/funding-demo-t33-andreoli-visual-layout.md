# T33 Andreoli Visual Layout

Data: 2026-08-26

Stato: scaletta interna per la schermata 4 della presentazione T33. Non e' una
slide finale e non autorizza pubblicazione, promozione di claim o modifica dei
profili.

## Scopo

Rendere visibile come fonti diverse possano aprire un percorso di ricerca sullo
stesso nome, senza presentare una biografia gia' risolta.

## Composizione

Usare una pagina orizzontale in tre aree, con poco testo e materiali reali
aperti dal data root esterno al momento dell'impaginazione.

1. A sinistra: una piccola traccia dalla fonte locale tabellare. Mostrare solo
   il nome e l'intestazione necessaria a riconoscere il documento.
2. Al centro: una breve traccia dal documento locale di contesto. Evidenziare
   il nome nella lista, senza estrarre dati biografici o conclusioni.
3. A destra, piu' grande: la scansione archivistica istituzionale nella quale
   il nome e' leggibile. Aggiungere una didascalia con tipo di fonte e
   provenienza, non un'interpretazione storica.

Collegare le tre aree con una sola frase:

```text
Lo stesso nome ricompare in documenti diversi.
```

Sotto alla scansione aggiungere un richiamo visibile ma discreto:

```text
Una seconda scheda richiede ancora verifica storica.
```

## Materiali selezionati

| Ruolo nella slide | Materiale da aprire durante il layout | Uso ammesso |
|---|---|---|
| Traccia locale | `caduti_purocielo.csv` | Mostrare il nome e il contesto minimo del record. |
| Contesto locale | `rielaborazione_schede_caduti_camalanca-prima_parte.docx` | Mostrare il nome nell'elenco, non una biografia. |
| Evidenza visuale principale | Prima immagine della prima scheda istituzionale selezionata | Mostrare la scansione con provenienza leggibile. |
| Domanda aperta | Seconda scheda istituzionale selezionata | Citarla soltanto come materiale da verificare. |

I percorsi, gli identificativi e gli artefatti di review restano nei materiali
operativi T33. Non inserirli nella slide.

## Testo per chi presenta

```text
Qui non stiamo mostrando una biografia gia' conclusa. Stiamo mostrando come lo
stesso nome riemerga in fonti diverse: una fonte locale, un documento di
contesto e una scheda archivistica. Quando le informazioni non coincidono,
restano visibili e diventano una domanda per lo storico.
```

## Da non mostrare

- codici di documento, run, claim, stati interni o conteggi;
- date, ruoli, luoghi o altri dati biografici come fatti conclusi;
- una fonte come se risolvesse automaticamente le differenze;
- preview, patch o output tecnici;
- parole come "claim", "riconciliazione" o "pending".

## Vincoli

- Aprire le fonti dal data root esterno senza copiarle nel repository.
- Indicare che la seconda scheda e' ancora da verificare.
- Mantenere la presentazione non pubblicabile.
- Non applicare `ProfilePatch` e non creare verified facts canonici.
