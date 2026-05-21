import sounddevice as sd
import numpy as np
import queue
import sys
from faster_whisper import WhisperModel

# --- CONFIGURAZIONE ---
CAMPIONAMENTO = 16000  # Frequenza standard per Whisper
DURATA_BLOCCO = 1.0    # Controlla il microfono ogni 1 secondo
MODELLO = "base"       # 'tiny' o 'base' sono consigliati per il tempo reale perché velocissimi

print("🤖 Caricamento del modello Whisper in corso...")
# Usiamo il modello 'base' (o 'tiny') per garantire che la CPU sia abbastanza veloce da starti dietro
model = WhisperModel(MODELLO, device="cpu", compute_type="int8")

# Coda (Queue) per scambiare i dati audio tra il microfono e Whisper
coda_audio = queue.Queue()

def callback_microfono(indata, frames, time, status):
    """Questa funzione viene chiamata automaticamente dal microfono ogni secondo"""
    if status:
        print(status, file=sys.stderr)
    # Inserisce i dati audio della coda convertendoli in float32 (formato voluto da Whisper)
    coda_audio.put(indata.copy().flatten())

# Configurazione del flusso di ingresso audio
stream = sd.InputStream(
    samplerate=CAMPIONAMENTO,
    channels=1,
    callback=callback_microfono,
    blocksize=int(CAMPIONAMENTO * DURATA_BLOCCO),
    dtype="float32"
)

print("\n🎙️ Microfono ATTIVO! Parla pure continuamente...")
print("(Per fermare il programma premi CTRL+C nel terminale)\n")

audio_accumulato = np.zeros(0, dtype=np.float32)

with stream:
    try:
        while True:
            # Prende il nuovo pezzo di audio dalla coda
            nuovo_chunk = coda_audio.get()
            
            # Accumula l'audio per mantenere il contesto della frase
            audio_accumulato = np.concatenate((audio_accumulato, nuovo_chunk))
            
            # Limitiamo la memoria agli ultimi 15 secondi per non rallentare la CPU
            if len(audio_accumulato) > CAMPIONAMENTO * 15:
                audio_accumulato = audio_accumulato[-CAMPIONAMENTO * 15:]
            
            # Esegui la trascrizione sul blocco accumulato
            # beam_size=1 accelera drasticamente l'elaborazione per il real-time
            segments, info = model.transcribe(
                audio_accumulato, 
                language="it", 
                beam_size=1, 
                vad_filter=True # Filtra i silenzi per non generare testo fantasma
            )
            
            # Unisce i segmenti di testo trovati
            testo_parziale = ""
            for segment in segments:
                testo_parziale += segment.text
            
            # Stampa il testo aggiornando la stessa linea nel terminale
            if testo_parziale.strip():
                # \r sovrascrive la riga corrente, dando l'effetto "live"
                sys.stdout.write(f"\r📝 Trascrizione: {testo_parziale.strip()}")
                sys.stdout.flush()
                
                # Se l'utente smette di parlare (il testo finisce con un punto o spazio lungo),
                # puoi decidere di liberare la memoria dell'audio accumulato.
                if len(audio_accumulato) >= CAMPIONAMENTO * 12:
                    print("") # Va a capo per la nuova frase
                    audio_accumulato = np.zeros(0, dtype=np.float32)

    except KeyboardInterrupt:
        print("\n\n🛑 Flusso continuo interrotto dall'utente.")

'''
import urllib.request
import os
from faster_whisper import WhisperModel

# 1. Definiamo l'URL del tuo audiolibro e il nome del file temporaneo
URL_AUDIO = "https://www.liberliber.eu/mediateca/audiolibri/d/de_angelis/l_amante_di_cesare/mp3/014_de_angelis_l_amante_rm_l_asp.mp3"
FILE_TEMPORANEO = "capitolo_audiolibri.mp3"

print("📥 Scaricamento del file MP3 da Liber Liber in corso...")
try:
    # Scarica il file direttamente dall'URL remoto
    urllib.request.urlretrieve(URL_AUDIO, FILE_TEMPORANEO)
    print("✅ Download completato con successo!")
except Exception as e:
    print(f"❌ Errore durante il download: {e}")
    exit()

print("\n🤖 Caricamento del modello Whisper (modello 'base' per massima velocità)...")
# Nota: Essendo un audiolibro (voce chiara), il modello 'base' sarà velocissimo e molto preciso
model = WhisperModel("base", device="cpu", compute_type="int8")

print("📝 Trascrizione dell'audiolibri in corso... Attendi qualche istante...")
print("-" * 50)

# Eseguiamo la trascrizione specificando la lingua italiana
segments, info = model.transcribe(FILE_TEMPORANEO, language="it")

# Stampiamo il testo riga per riga con i relativi minuti/secondi
for segment in segments:
    # Formattiamo il tempo in minuti:secondi (es. 01:23)
    minuti_inizio, secondi_inizio = divmod(int(segment.start), 60)
    minuti_fine, secondi_fine = divmod(int(segment.end), 60)
    
    timestamp = f"[{minuti_inizio:02d}:{secondi_inizio:02d} -> {minuti_fine:02d}:{secondi_fine:02d}]"
    print(f"{timestamp} {segment.text}")

# 3. Pulizia opzionale: rimuoviamo il file scaricato per non occupare spazio sul server cloud
if os.path.exists(FILE_TEMPORANEO):
    os.remove(FILE_TEMPORANEO)
    print("-" * 50)
    print("🗑️ File temporaneo rimosso per pulizia.")'''