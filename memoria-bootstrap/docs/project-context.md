# Project Context — Me.Mo.Ri.A

Me.Mo.Ri.A e' un meta-motore di ricerca, memoria e curatela per documentazione
sulla Resistenza e sui caduti/partigiani.

L'obiettivo dell'MVP non e' produrre schede pubblicabili automaticamente, ma
dare evidenza ai finanziatori del percorso che porta da documenti grezzi, OCR e
fonti eterogenee a una scheda JSON-LD revisionabile dallo storico, con
provenance, decision trail e feedback loop per nuove ricerche.

## Valore principale

- Ricerca su fonti disomogenee offline e online.
- Aggregazione tracciabile per persona, evento, luogo, unita' e documento.
- Riconciliazione multi-fonte senza cancellare divergenze e incertezze.
- Vista unica per lo storico.
- Decision trail e patch preview, senza merge automatico.
- Feedback loop che rilancia una ricerca mirata e ne registra l'esito.

## Prova MVP richiesta

La demo finanziatori deve usare una sola golden run e mostrare:

1. almeno due fonti eterogenee collegate allo stesso caso;
2. contributi complementari o conflittuali con provenance visibile;
3. una decisione umana sostanziale;
4. un fatto verificato e una patch esclusivamente preview;
5. una richiesta di nuova ricerca realmente eseguita;
6. un nuovo documento/claim oppure un `no_results` tracciato che rientra nella
   memoria di ricerca del profilo.

## Vincolo metodologico

L'AI propone estrazioni, collegamenti e strategie. Lo storico valida, rigetta,
fonde, lascia incerto o rilancia ricerche. Fonte, trasformazione e decisione
restano sempre visibili. Nessun output preview e' automaticamente pubblicabile.
