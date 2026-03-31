![License: AGPL v3](https://img.shields.io/badge/license-AGPL--3.0-blue.svg)
# OmniPort Framework

Il **OmniPort Framework** è una piattaforma modulare e flessibile progettata per la creazione rapida di applicazioni web. Sfrutta Python, Jinja2 e Supabase per offrire un'esperienza di sviluppo moderna e scalabile.

"Smetti di scrivere codice per una sola piattaforma. Definisci l'intento, scegli il Port. Benvenuti nell'era di OmniPort."

## 🚀 Caratteristiche Principali

* **Modularità Avanzata**: Supporta il caricamento dinamico dei moduli, facilitando l'estensibilità e la manutenzione del codice.
* **Internazionalizzazione**: Gestione multi-lingua integrata per applicazioni globali.
* **Frontend Dinamico**: Utilizzo di Jinja2 per il rendering dinamico e supporto per TypeScript nella zona applicativa.
* **Persistenza con Supabase**: Integrazione con Supabase per la gestione dei dati e autenticazione.
* **DevOps Integrato**: Strumenti per la gestione e il deployment continuo delle applicazioni.

---

### ⚙️ Configurazione Dichiarativa

SottoMonte adotta un approccio dichiarativo per la configurazione delle applicazioni, riducendo la necessità di codice imperativo e facilitando la gestione centralizzata delle impostazioni. La configurazione avviene tramite file YAML o JSON, che descrivono:

- **Moduli da caricare**: elenco dei moduli e delle dipendenze.
- **Provider di servizi**: configurazione dei servizi (database, autenticazione, storage, ecc.).
- **Routing**: definizione delle rotte e delle azioni associate.
- **Parametri di ambiente**: variabili e segreti gestiti in modo sicuro.
- **Internazionalizzazione**: lingue supportate e fallback.

```toml
[app]
name = "hub"
identifier = "cloud.colosso.app"
key = "{{ SECRET_KEY }}"
version = "0.0.1"
readme = "README.md"
requires-python = ">=3.8"

# Configurazione della presentazione
[presentation.web]
adapter = "wasm"
host = "0.0.0.0"
port = "8000"
view = "page/welcome.xml"
routes = "policy/web.xml"
```

---

### 🧩 Architettura Modulare e Dinamica

SottoMonte adotta un'architettura modulare, con una struttura ben organizzata delle cartelle e dei file. La directory principale `/src/` contiene sottocartelle come `core/`, `models/`, `services/` e `controllers/`, ciascuna con responsabilità specifiche. Questa separazione dei compiti facilita la manutenzione e l'estensibilità del codice.

---

### 🌐 Supporto Multilingua

Il framework prevede il supporto per applicazioni multilingua, come indicato nei commenti del codice. Questo consente di sviluppare applicazioni che possono essere facilmente adattate a diverse lingue e regioni, migliorando l'accessibilità e l'usabilità a livello globale.

---

### ⚙️ Caricamento Dinamico dei Moduli

Una delle caratteristiche distintive di SottoMonte è la capacità di caricare dinamicamente i moduli. Questo approccio consente di aggiungere o modificare funzionalità senza dover riavviare l'intera applicazione, migliorando la flessibilità e la scalabilità del sistema.

---

### 🧠 Gestione Automatica delle Dipendenze

Il framework è progettato per comprendere automaticamente il ciclo delle dipendenze tra i moduli. Questo significa che può determinare l'ordine corretto di caricamento e inizializzazione dei componenti, riducendo gli errori e semplificando lo sviluppo.

---

### 📦 Integrazione con Supabase per la Persistenza

SottoMonte integra Supabase come soluzione per la persistenza dei dati. Supabase è una piattaforma open-source che offre funzionalità simili a Firebase, come database in tempo reale, autenticazione e storage. Questa integrazione consente di gestire facilmente i dati dell'applicazione in modo scalabile e sicuro.

---

### 🎨 Template Engine

SottoMonte supporta **motori di template HTML** e il rendering dinamico attraverso WebAssembly (WASM). Le caratteristiche includono:

- Separazione chiara tra logica e presentazione.
- Supporto a linguaggi come Jinja2 o compatibilità simil-Vue/React.
- **Binding dei dati bidirezionale** nei template client.
- Supporto multilingua con interpolazione dinamica (`i18n`).

---

### 🧪 Utilizzo di WebAssembly (WASM) per la Presentazione

Il framework prevede l'uso di WebAssembly (WASM) per migliorare le prestazioni della presentazione dell'applicazione. WASM consente di eseguire codice ad alte prestazioni nel browser, offrendo un'esperienza utente più fluida e reattiva.

---

### 🛠️ DevOps e Automazione

SottoMonte include strumenti per facilitare le pratiche DevOps, come l'automazione del ciclo di vita dell'applicazione e la gestione delle configurazioni. Questo permette di implementare rapidamente nuove funzionalità e di mantenere l'applicazione aggiornata con maggiore efficienza.

---

## 🧭 Pattern MVA (Model-View-Action)

SottoMonte adotta un'evoluzione del classico MVC, definita **MVA - Model View Action**:

- **Model**: Definisce le entità del dominio e la logica di accesso ai dati.
- **View**: È gestita tramite template HTML o WASM con data-binding.
- **Action**: Le azioni (anziché controller) sono unità indipendenti e modulari, caricate dinamicamente.

Ogni **azione** rappresenta una singola funzionalità o endpoint, rendendo il codice molto più granularizzato rispetto a controller monolitici.

---

### 📊 Binding dei Dati e Logging Avanzato

Il framework offre meccanismi avanzati per il binding dei dati tra il frontend e il backend, migliorando la sincronizzazione delle informazioni. Inoltre, include un sistema di logging e messaggistica potenziato, utile per il monitoraggio e il debug dell'applicazione.

---

### 🧪 Testabilità Nativa

* Ogni componente può essere testato in isolamento.
* Il contenitore DI permette mocking e sostituzioni controllate.
* Le azioni sono testabili come unità singole (senza il framework completo).
* TTD

---

### 🧠 Dependency Injection (DI)

Il framework implementa un **contenitore di iniezione delle dipendenze personalizzato** , con queste funzionalità:

- Registrazione esplicita dei provider
- Recupero delle istanze in modo lazy.
- Supporto a dipendenze complesse e nidificate.
- Controllo del ciclo di vita delle istanze (singleton, factory).
- Estensione possibile tramite annotazioni o decorators.

---

### 🚀 Integrazione con TypeScript

SottoMonte prevede l'uso di TypeScript per lo sviluppo del frontend, sfruttando i vantaggi del tipaggio statico e delle funzionalità avanzate del linguaggio. Questo contribuisce a scrivere codice più robusto e manutenibile.

---

## 🛠️ Installazione

1. **Clona la repository**:

   ```bash
   git clone https://github.com/SottoMonte/framework.git
   cd framework
   ```



2. **Crea e attiva un ambiente virtuale**:

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```



3. **Installa le dipendenze**:

   ```bash
   pip install -r requirements.txt
   ```



4. **Avvia l'applicazione**:

   ```bash
   python3 public/main.py
   ```

## 📁 Struttura del Progetto

### `/src/`

Contiene il codice sorgente principale suddiviso in tre macro-aree secondo l'architettura a port and adapter (Hexagonal Architecture):

#### 📁 `framework/`

* **`manager/`**: logiche di coordinamento e orchestrazione dei componenti.
* **`service/`**: servizi di business logic, astratti dall’infrastruttura.
* **`port/`**: porte (interfacce) per l’inversione di controllo.

#### 📁 `infrastructure/`

* **`encryption/`**: crittografia, hashing e firme digitali.
* **`presentation/`**: interfacce utente o API esterne.
* **`sensor/`**: raccolta dati da hardware o stream.
* **`actuator/`**: componenti che agiscono nel mondo reale o simulato.
* **`authentication/`**: autenticazione, gestione utenti e ruoli.
* **`perception/`**: elaborazione dati e analisi (ML, AI).
* **`message/`**: messaggistica asincrona, pub/sub.
* **`persistence/`**: accesso a DB, file system e cache.
* **`test/`**: mock e implementazioni per test.

#### 📁 `application/`

* **`model/`**: definizione entità e oggetti valore.
* **`policy/`**: regole aziendali e vincoli di dominio.

    * `authentication`, `presentation`, `message`, `persistence`
* **`repository/`**: pattern repository per la persistenza.
* **`view/`**:

  * **`layout/`**: template di layout condivisi.
  * **`component/`**: componenti UI riutilizzabili.
  * **`content/`**: contenuti visuali (form, modal, wizard, tab, card, table).
  * **`page/`**: pagine applicative:
  
    * `auth`, `error`
* **`locales/`**: file di traduzione e internazionalizzazione.
* **`action/`**: comandi e interazioni utente.

### `/public/`

Contiene il punto di ingresso (`app.py`) e asset statici.

### `/doc/`

Risorse aggiuntive e guide.

### Radice del progetto

* `Dockerfile`: containerizzazione.
* `Procfile`: deployment (Heroku).
* `requirements.txt`: dipendenze Python.


## 📌 Roadmap e TODO

* [ ] Rifattorizzare il loader dei moduli per una maggiore efficienza.
* [ ] Implementare il supporto multi-lingua completo.
* [ ] Aggiungere un sistema di caricamento dinamico con attesa tramite Jinja2.
* [ ] Creare un prodotto minimale per il rilascio iniziale.
* [ ] Integrare un sistema di iniezione delle dipendenze.
* [ ] Sviluppare pipeline DevOps per il deployment continuo.
* [ ] Migliorare il sistema di log e messaggistica.
* [ ] Implementare il binding dei dati tra frontend e backend.
* [ ] Creare e gestire progetti tramite una piattaforma dedicata.
* [ ] Utilizzare TypeScript per la zona applicativa.
* [ ] Trasformare il codice JavaScript in moduli utilizzabili in Python per la persistenza con Supabase.
* [ ] Support export per i test.
* [ ] Test obbligatori.

## 📄 Licenza

Questo progetto è distribuito sotto la licenza AGPL v3.

## 🤝 Contribuire

Contributi, segnalazioni di bug e suggerimenti sono benvenuti! Sentiti libero di aprire issue o pull request.

---

Per ulteriori dettagli e aggiornamenti, visita la [repository ufficiale](https://github.com/SottoMonte/framework/tree/main).