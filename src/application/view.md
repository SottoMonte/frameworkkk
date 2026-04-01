# Documentazione Schema XML Custom

Questo documento descrive i tag validi e i relativi attributi per la configurazione dei widget tramite XML.

## Indice dei Tag

  * [Card](https://www.google.com/search?q=%23card)
  * [Media](https://www.google.com/search?q=%23media)
  * [Icon](https://www.google.com/search?q=%23messenger)
  * [Divider](https://www.google.com/search?q=%23messenger)
  * [Navigation](https://www.google.com/search?q=%23navigation)
  * [View](https://www.google.com/search?q=%23view)
  * [Messenger](https://www.google.com/search?q=%23messenger)
  * [Message](https://www.google.com/search?q=%23message)
  * [Defender](https://www.google.com/search?q=%23defender)
  * [Column](https://www.google.com/search?q=%23column)
  * [Row](https://www.google.com/search?q=%23row)
  * [Container](https://www.google.com/search?q=%23container)
  * [Stack](https://www.google.com/search?q=%23stack)
  * [Storekeeper](https://www.google.com/search?q=%23storekeeper)
  * [Input](https://www.google.com/search?q=%23input)
  * [Action](https://www.google.com/search?q=%23action)
  * [Window](https://www.google.com/search?q=%23window)
  * [Text](https://www.google.com/search?q=%23text)
  * [Group](https://www.google.com/search?q=%23group)

## Indice degli Attributi

| Attributo | Valori Ammessi | Descrizione |
| :--- | :--- | :--- |
| **id** | Stringa univoca | Identificatore univoco dell'elemento nel documento. |
| **title** | Testo | Titolo principale o etichetta dell'elemento. |
| **subtitle** | Testo | Sottotitolo o testo descrittivo secondario. |
| **image** | URL, Path | Percorso o link all'immagine da visualizzare. |
| **content** | Testo, HTML | Contenuto principale o corpo del componente. |
| **class** | Stringa | Nomi delle classi CSS per lo styling. |
| **width** | px, %, em, auto | Larghezza dell'elemento. |
| **height** | px, %, em, auto | Altezza dell'elemento. |
| **padding** | Valore numerico o CSS | Spazio interno tra il bordo e il contenuto. |
| **margin** | Valore numerico o CSS | Spazio esterno attorno all'elemento. |
| **expand** | boolean | Se `true`, l'elemento occupa tutto lo spazio disponibile. |
| **alignment-content** | start, center, end, stretch | Allineamento degli elementi figli all'interno. |
| **alignment-vertical** | top, center, bottom | Posizionamento verticale nel contenitore. |
| **alignment-horizontal**| left, center, right | Posizionamento orizzontale nel contenitore. |
| **spacing** | Valore numerico | Distanza (gap) tra gli elementi interni. |
| **orientation** | vertical, horizontal | Direzione dello sviluppo del layout. |
| **type** | text, email, submit, etc. | Definisce il tipo di input o di componente. |
| **value** | Stringa, Numero | Valore memorizzato o inserito nel campo. |
| **required** | boolean | Definisce se il campo è obbligatorio. |
| **disabled** | boolean | Disattiva l'interazione con l'elemento. |
| **readonly** | boolean | Impedisce la modifica ma permette la visualizzazione. |
| **autofocus** | boolean | Forza il focus sull'elemento al caricamento. |
| **selected** | boolean | Indica se l'elemento è attualmente selezionato. |
| **event-click** | Nome funzione | Azione eseguita al click del mouse. |
| **event-change** | Nome funzione | Azione eseguita alla variazione del valore. |
| **name** | Stringa | Nome identificativo per invio dati o form. |
| **placeholder** | Testo | Suggerimento testuale mostrato in campi vuoti. |
| **allow** | Stringa (policy) | Permessi specifici (es. per iframe o API). |
| **controls** | boolean | Mostra o nasconde i tasti di controllo multimediali. |
| **autoplay** | boolean | Avvia automaticamente audio o video. |
| **src** | URL, Path | Sorgente della risorsa esterna. |
| **route** | Percorso / Stringa | Indirizzo di navigazione interna al sistema. |
| **view** | Nome vista | Identifica la vista o il componente da caricare. |
| **index** | Numero intero | Posizione dell'elemento in un elenco. |
| **domain** | URL / Stringa | Dominio o contesto dati di riferimento. |
| **mode** | dark, light, edit, view | Stato o tema di visualizzazione del componente. |
| **repository** | Stringa | Riferimento alla sorgente dati (DB o API). |
| **filter** | Stringa / Query | Criterio di filtraggio per le liste. |
| **sort** | asc, desc, Stringa | Criterio di ordinamento dei risultati. |
| **limit** | Numero | Quantità massima di elementi da restituire. |
| **offset** | Numero | Numero di elementi da saltare (paginazione). |
| **method** | GET, POST, PUT, DELETE | Metodo di richiesta HTTP. |
| **action** | URL / Nome funzione | Operazione da eseguire all'invio del form. |
| **active** | boolean | Indica se lo stato dell'elemento è attivo. |
| **size** | small, medium, large | Scala dimensionale del componente. |
| **layout** | grid, flex, block | Modello di impaginazione utilizzato. |

-----

## Card

Utilizzato per rappresentare un componente scheda.

  * **Attributi:**
      * `id`, 
      * `title`, 
      * `subtitle`, 
      * `image`, 
      * `content`, 
      * `class`, 
      * `width`, 
      * `height`, 
      * `padding`, 
      * `margin`, 
      * `expand`: Stringa.
      * `alignment-content`: `horizontal`, `center`, `end`, `between`, `around`.

## Data

Utilizzato per la visualizzazione di dati strutturati.

  * **Attributi:**
      * `id`, 
      * `class`, 
      * `width`, 
      * `height`, 
      * `value`: Stringa.
      * `type`: `text` (default), `table`, `table.row`, `table.cell`, `table.header`, `table.body`, `progress`, `placeholder`.

## Media

Gestisce contenuti multimediali.

  * **Attributi:**
      * `allow`, 
      * `class`, 
      * `controls`, 
      * `autoplay`, 
      * `width`, 
      * `height`, 
      * `expand`, 
      * `src`: Stringa.
      * `type`: `image`, `video`, `audio`, `embed`, `carousel`, `map`, `icon`.

## Navigation

Definisce barre di navigazione, breadcrumb o impaginazione.

  * **Attributi:**
      * `id`, 
      * `class`, 
      * `width`, 
      * `height`, 
      * `expand`, 
      * `padding`, 
      * `margin`: Stringa.
      * `alignment-content`: `horizontal`, `vertical`, `center`, `end`, `between`, `around`.
      * `orientation`: `horizontal` (default), `vertical`.
      * `type`: `bar` (default), `breadcrumb`, `pagination`, `accordion`, `tab`, `accordion-item`.

## View

Monta una vista specifica basata su una rotta.

  * **Attributi:**
      * `route`, 
      * `view`, 
      * `index`: Stringa.

## Messenger

Configura un widget di messaggistica/chat.

  * **Attributi:**
      * `view`, 
      * `domain`: Stringa.

## Message

Visualizza messaggi di stato, avvisi o notifiche.

  * **Attributi:**
      * `title`, 
      * `subtitle`: Stringa.
      * `type`: `info` (default), `success`, `warning`, `error`.
      * `mode`: `alert` (default), `toast`, `inline`, `banner`.

## Defender

Tag di sicurezza.

  * **Attributi:** Nessuno definito nello schema.

## Column

Contenitore a sviluppo verticale.

  * **Attributi:**
      * `id`, 
      * `padding`, 
      * `margin`, 
      * `width`, 
      * `height`, 
      * `class`, 
      * `expand`: Stringa.

## Row

Contenitore a sviluppo orizzontale.

  * **Attributi:**
      * `id`, 
      * `expand`, 
      * `class`, 
      * `width`, 
      * `height`, 
      * `padding`, 
      * `margin`, 
      * `spacing`, 
      * `alignment-vertical`, 
      * `alignment-horizontal`, 
      * `alignment-content`: Stringa.

## Container

Contenitore principale con vincoli di layout.

  * **Attributi:**
      * `id`, 
      * `class`, 
      * `width`, 
      * `height`, 
      * `padding`, 
      * `spacing`, 
      * `margin`, 
      * `expand`: Stringa.
      * `type`: `fluid` (default), `fixed`.
      * `alignment-content`: `horizontal`, `center`, `end`, `between`, `around`.

## Storekeeper

Gestisce le chiamate ai dati (Repository/API).

  * **Attributi:**
      * `repository`, 
      * `id`, 
      * `filter`, 
      * `sort`, 
      * `limit`, 
      * `offset`: Stringa.
      * `method`: `get` (default), `post`, `put`, `delete`.

## Input

Campi di input per form.

  * **Attributi:**
      * `id`, 
      * `class`, 
      * `width`, 
      * `height`, 
      * `required`, 
      * `disabled`, 
      * `readonly`, 
      * `autofocus`, 
      * `selected`, 
      * `event-click`, 
      * `event-change`, 
      * `name`, 
      * `placeholder`, 
      * `value`: Stringa.
      * `type`: `text` (default), `email`, `select`, `checkbox`, `textarea`, `radio`, `switch`, `color`, `range`, `password`, `listbox`, `search`, `number`, `file`, `hidden`, `date`, `time`, `month`, `week`, `url`, `tel`, `number`.
      * `alignment-content`: `horizontal`, `center`, `end`, `between`, `around`.

## Action

Elementi interattivi (pulsanti, link, form).

  * **Attributi:**
      * `id`, 
      * `tooltip`, 
      * `spacing`, 
      * `expand`, 
      * `width`, 
      * `height`, 
      * `class`, 
      * `action`, 
      * `active`, 
      * `route`, 
      * `event-change`, 
      * `event-click`: Stringa.
      * `type`: `button` (default), `submit`, `form`, `reset`, `link`.
      * `alignment-content`: `horizontal`, `center`, `end`, `between`, `around`.

## Window

Definisce finestre di dialogo, modali o aree radice.

  * **Attributi:**
      * `allow`, 
      * `title`, 
      * `layout`, 
      * `class`, 
      * `id`, 
      * `width`, 
      * `height`, 
      * `expand`, 
      * `action`, 
      * `size`, 
      * `src`: Stringa.
      * `type`: `embed` (default), `still`, `dialog`, `page`.

## Text

Visualizzazione di testo semplice o blocchi di codice.

  * **Attributi:**
      * `class`, 
      * `width`, 
      * `height`, 
      * `value`, 
      * `disabled`: Stringa.
      * `type`: `text` (default), `input`, `h1`, `h2`, `h3`, `h4`, `h5`, `h6`, `p`, `span`, `mark`, `blockquote`, `pre`, `code`, `abbr`, `cite`, `time`.

## Group

Raggruppa logicamente altri componenti.

  * **Attributi:**
      * `width`, 
      * `height`, 
      * `expand`, 
      * `class`, 
      * `padding`, 
      * `spacing`, 
      * `margin`: Stringa.
      * `type`: `input` (default), `list`, `card`, `tab`, `action`, `dropdown`.
      * `alignment-content`
      * `alignment-vertical`