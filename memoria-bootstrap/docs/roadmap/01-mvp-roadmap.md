# MVP Roadmap

Data: 2026-07-18

## Definizione MVP

L'MVP di Me.Mo.Ri.A e' una dimostrazione controllata del percorso:

```text
documenti grezzi e fonti eterogenee
  -> evidenze estratte e tracciabili
  -> riconciliazione multi-fonte
  -> proposta di scheda/profilo
  -> revisione storica
  -> patch preview
  -> nuova ricerca guidata dal feedback
```

La finalita' e' mostrare a storici e finanziatori il valore operativo del
metodo. L'MVP non produce automaticamente schede pubblicabili.

## Tesi da dimostrare

La demo deve rendere evidente che Me.Mo.Ri.A:

- cerca e registra fonti offline e online disomogenee;
- riconduce documenti differenti alla stessa persona, evento o luogo;
- mantiene separati i contributi di ogni fonte;
- espone contraddizioni, lacune e livelli di confidenza;
- consente allo storico di confermare, rigettare o lasciare incerto un claim;
- trasforma solo decisioni approvate in fatti verificati preview;
- propone una patch revisionabile al profilo senza merge automatico;
- usa la review per generare una nuova ricerca e registrarne l'esito.

## Definition of Done dell'MVP finanziatori

L'MVP e' pronto per una presentazione esterna quando esiste una sola golden run
che soddisfa tutti i criteri seguenti.

### Casi storici

- 3 profili intenzionalmente selezionati: 1 caso principale e 2 casi
  complementari;
- 5 documenti sorgente complessivi, senza scansione massiva;
- almeno due fonti o famiglie documentali differenti;
- almeno un campo complementare, divergente o incerto utile alla review.

### Riconciliazione multi-fonte

- i documenti sono collegati allo stesso soggetto con provenance visibile;
- la vista consolidata mostra quale fonte sostiene ogni claim;
- eventuali valori discordanti restano entrambi visibili;
- nessun risultato generico o pagina lista e' promosso a evidenza;
- almeno un fatto e' supportato da piu' fonti oppure la scheda unifica contributi
  complementari provenienti da fonti differenti.

### Decisione e patch

- almeno una decisione storica sostanziale e' registrata;
- ogni profilo selezionato ha almeno una decisione sostanziale oppure un esito
  esplicito di incertezza o richiesta fonti;
- almeno un fatto verificato resta marcato preview/non pubblicabile;
- almeno una patch del profilo e' collegata a source document, claim, decisione,
  reviewer e run;
- nessuna patch e' applicata automaticamente al profilo canonico.

### Feedback loop chiuso

- una lacuna, incertezza o contraddizione e' selezionata dallo storico;
- viene registrata una richiesta di nuova ricerca;
- il planner produce una query e una strategia fonte-specifica;
- la ricerca e' eseguita in modo controllato;
- l'esito e' un nuovo documento/evidenza oppure un `no_results` tracciato;
- il profilo conserva l'esito come memoria della ricerca successiva.

### Presentazione

- tutti i report puntano allo stesso `run_id` canonico;
- il walkthrough e' ripetibile senza scansioni massive o rete non controllata;
- ogni schermata distingue automatico, revisionato e pubblicabile;
- il dossier dichiara cosa funziona oggi e cosa richiede finanziamento.

## Perimetro dati

I dati reali restano fuori dai repository Git. Il backend locale compatibile e':

```text
P:\Comune\Me.Mo.Ri.a
```

La golden run referenzia i materiali nel workspace operativo. Nei repository
restano codice, regole, documentazione e fixture sintetiche.

## Incrementi MVP

### Incremento 0 - Baseline post-migrazione

Stato: **completato**.

Risultati:

- architettura multi-repo;
- package e test;
- data root risolvibile;
- CLI diagnostica e viste read-only;
- separazione fra engine, sources, knowledge, rules e workspace.

### Incremento 1 - Capacita' preview di review e consolidamento

Stato: **sostanzialmente disponibile, ma distribuito fra run differenti**.

Sono gia' presenti nel sistema documenti, claim, decisioni, verified facts
preview, patch preview e piani di feedback. Non costituiscono ancora una demo
esterna coerente perche' non sono congelati in una sola golden run.

### Incremento 2 - Contratto golden path

Collegamento tecnico: **T29**.

Scopo:

- scegliere il caso principale;
- definire fonti e documenti minimi;
- definire il contratto della run canonica;
- stabilire criteri misurabili per merge multi-fonte e feedback loop;
- fissare il walkthrough atteso prima di eseguire nuove pipeline.

### Incremento 3 - Golden run multi-fonte

Collegamento tecnico: **T30**.

Scopo:

- produrre o rigenerare una sola run;
- allineare profili, documenti, store, review, decisioni, patch e report;
- dimostrare la convergenza di fonti differenti nella stessa scheda di lavoro;
- ridurre il rumore della review al solo caso demo.

### Incremento 4 - Feedback loop dimostrato

Collegamento tecnico: **T31**.

Scopo:

- selezionare una domanda aperta reale;
- registrare il feedback dello storico;
- rilanciare una ricerca controllata;
- importare o registrare l'esito;
- mostrare l'effetto sulla memoria di ricerca e sulla scheda preview.

### Incremento 5 - Hardening della demo

Collegamento tecnico: **T32**.

Scopo:

- correggere incoerenze CLI e test cross-platform che incidono sulla demo;
- allineare playbook, guide e run selection;
- eliminare ambiguita' fra artefatti pubblicabili e preview;
- verificare ripetibilita' e assenza di dati reali nei repository distribuibili.

### Incremento 6 - Pacchetto finanziatori

Collegamento tecnico: **T33**.

Scopo:

- preparare walkthrough di 7-10 minuti;
- produrre un dossier breve e coerente con la golden run;
- mostrare problema, valore, prova tecnica, ruolo dello storico e uso dei fondi;
- distinguere MVP attuale, sviluppo finanziato e visione di piattaforma.

## Regola di priorita'

Fino alla chiusura di T33:

1. lavorare sull'incremento corrente T29-T33;
2. eseguire fix o micro-refactor solo se bloccano direttamente la demo;
3. non scegliere pCloud, nuove fonti o ampliamenti massivi come prossimo passo;
4. non aumentare il numero di profili prima di rendere convincente il caso
   principale; l'espansione T33 a tre casi e' il solo ampliamento controllato
   autorizzato e deve confluire in una nuova golden run unica.

## Fuori scope MVP iniziale

- produzione massiva di schede;
- pubblicazione automatica;
- merge automatico dei profili canonici;
- risoluzione automatica dei conflitti;
- estensione indiscriminata a nuove fonti;
- migrazione cloud massiva;
- dashboard general-purpose prima della stabilizzazione della golden run.

## Direzione post-MVP OCR dopo la golden run

Aggiornamento 2026-09-20: questa sezione non modifica il contratto della golden
run finanziatori gia' completata. Definisce il percorso del prodotto completo
per trasformare nuove scansioni in materiale revisionabile.

La pipeline OCR non deve produrre direttamente fatti o schede. La sequenza
selezionata e':

```text
scansione
  -> evidenza OCR strutturata
  -> struttura di pagina derivata
  -> Markdown revisionabile
  -> extraction/candidate claim
  -> review storica
```

Il recognizer primario del prossimo pilot e' PP-OCRv5, mantenendo Tesseract come
seconda lettura. Layout e Markdown vengono ricostruiti con regole deterministiche
prima di introdurre un VLM. Ogni elemento derivato mantiene provenance verso le
regioni dell'immagine.

La sequenza tecnica T35-T40 e il contratto dettagliato sono definiti in
`02-technical-roadmap.md` e `../ocr-structured-evidence-strategy.md`.
