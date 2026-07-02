import datetime
import fnmatch
import logging
import os
import sys
from typing import Any, Dict, List

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

import framework.port.message as message
import framework.manager.storekeeper as storekeeper

class Adapter(message.Port):
    """
    Enterprise-grade AI/ML & Console Adapter progettato per l'orchestrazione dinamica 
    di modelli linguistici (LLM/Transformers) e logging strutturato.
    """

    class AuditFormatter(logging.Formatter):
        """Formatter enterprise per audit log conformi allo standard ISO 8601."""
        def format(self, record: logging.LogRecord) -> str:
            record.asctime = datetime.datetime.fromtimestamp(
                record.created, datetime.timezone.utc
            ).isoformat(timespec='milliseconds')

            record.transaction_id = getattr(record, 'transaction_id', 'SYSTEM')
            record.domain = getattr(record, 'domain', 'UNKNOWN')
            record.user_id = getattr(record, 'user_id', 'ANONYMOUS')
            record.action = getattr(record, 'action', 'NOT_SPECIFIED')

            return super().format(record)

    def __init__(self, storekeeper: storekeeper.Manager, **constants) -> None:
        """
        Inizializza il sistema verificando i parametri di runtime e istanziando 
        dinamicamente il modello di intelligenza artificiale richiesto.
        """
        if constants.get('name'):
            self.name = __name__ + "." + constants['name'].lower()
        else:
            self.name = __name__
            
        self.adapter = __name__.split('.')[-1]
        self.config = constants
        self.storekeeper = storekeeper
        self.persistence = constants.get('persistence')
        self.project_meta: Dict[str, Any] = self.config.get('project', {})
        
        self.project_id: str = self.project_meta.get('identifier', 'enterprise-ai-service')
        self.environment: str = self.project_meta.get('mode', 'production').lower()
        
        self._history: Dict[str, List[Any]] = {}
        # Estendiamo le capacità per includere l'inferenza AI
        self.processable: List[str] = ['log', 'audit', 'generate', 'inference']

        # Configurazione Logger
        self._logger = logging.getLogger(f"audit.{self.project_id}")
        self._logger.propagate = False
        self._logger.setLevel(logging.INFO if self.environment == 'production' else logging.DEBUG)
        self._initialize_handler(constants.get('format'))

        # --- INITIALIZATION FACTORY DEL MODELLO ---
        self.model = None
        self.tokenizer = None
        
        # Recupera il path o il nome del modello dai parametri (es: 'google/gemma-2b-it', 'meta-llama/Meta-Llama-3-8B')
        self.model_target: str = constants.get('model_name_or_path')
        
        if self.model_target:
            self._load_dynamic_model(self.model_target, **constants)

    def _load_dynamic_model(self, model_name: str, **constants) -> None:
        """Inietta dinamicamente i pesi nell'architettura caricando i moduli Transformers richiesti."""
        self._logger.info(f"Avvio del caricamento dinamico del modello: {model_name}", extra={'action': 'MODEL_LOAD'})
        try:
            # Configurazione della precisione basata sull'hardware/ambiente
            use_quantization = constants.get('quantize_4bit', False)
            
            # Caricamento Tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            
            # Strategia di caricamento condizionale (4-bit per risparmio VRAM o Float16 standard)
            if use_quantization and torch.cuda.is_available():
                quant_config = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16
                )
                self.model = AutoModelForCausalLM.from_pretrained(
                    model_name,
                    quantization_config=quant_config,
                    device_map="auto"
                )
            else:
                dtype = torch.float16 if torch.cuda.is_available() else torch.float32
                self.model = AutoModelForCausalLM.from_pretrained(
                    model_name,
                    torch_dtype=dtype,
                    device_map="auto" if torch.cuda.is_available() else "cpu"
                )
                
            self._logger.info(f"Modello {model_name} caricato con successo sulla risorsa: {self.model.device}", extra={'action': 'MODEL_LOAD_SUCCESS'})
        except Exception as e:
            self._logger.critical(f"Fallimento critico durante l'istanza del modello {model_name}: {str(e)}", extra={'action': 'MODEL_LOAD_FAILURE'})
            raise RuntimeError(f"Impossibile inizializzare l'adapter AI: {e}")

    def _initialize_handler(self, custom_format: str = None) -> None:
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setLevel(self._logger.level)

        default_audit_format = (
            "%(asctime)s | "
            f"[{self.environment.upper()}] | "
            f"[{self.project_id}] | "
            "[TX:%(transaction_id)s] | "
            "[DOM:%(domain)s] | "
            "[USER:%(user_id)s] | "
            "%(levelname)-8s | "
            "%(filename)s:%(lineno)d | "
            "%(message)s"
        )

        log_format = custom_format if custom_format else default_audit_format
        formatter = self.AuditFormatter(log_format)
        stdout_handler.setFormatter(formatter)
        
        self._logger.handlers.clear()
        self._logger.addHandler(stdout_handler)

    async def can(self, *services: Any, **constants: Any) -> bool:
        """Verifica se l'operazione richiesta rientra nelle capacità del sistema AI/Log."""
        return constants.get('name') in self.processable

    async def post(self, *services: Any, **constants: Any) -> None:
        """Esegue azioni di Auditing standard o triggera l'inferenza se richiesto."""
        action_type = constants.get('name', 'log')

        # Se l'azione è un'interrogazione al modello AI
        if action_type in ['generate', 'inference']:
            if not self.model or not self.tokenizer:
                raise ValueError("Nessun modello IA inizializzato in questo adapter.")
                
            prompt = constants.get('prompt', '')
            max_tokens = constants.get('max_new_tokens', 128)
            temperature = constants.get('temperature', 0.7)
            
            # Loggare l'inizio dell'operazione di NLP per auditing
            self._logger.info(f"Esecuzione inferenza AI su prompt di lunghezza {len(prompt)}", extra=constants)
            
            # Tokenizzazione ed esecuzione a risorse isolate (no_grad)
            inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=max_tokens,
                    temperature=temperature,
                    do_sample=True if temperature > 0 else False
                )
            
            generated_text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            
            # Salvataggio del risultato nei costanti per ritornarlo o persistenza
            constants['response'] = generated_text

        # --- Persistenza e Tracciamento standard dei Log ---
        message_text: str = constants.get('message', constants.get('response', str(constants)))
        level: str = constants.get('level', 'INFO').upper()
        domain: str = constants.get('domain', 'ai_engine')

        audit_context = {
            'transaction_id': constants.get('transaction_id', 'SYSTEM'),
            'domain': domain,
            'user_id': constants.get('user_id', 'ANONYMOUS'),
            'action': constants.get('action', 'AI_INFERENCE_EXEC') if action_type in ['generate', 'inference'] else constants.get('action', 'NOT_SPECIFIED')
        }

        log_level_map = {
            'DEBUG': logging.DEBUG, 'INFO': logging.INFO, 'WARNING': logging.WARNING,
            'ERROR': logging.ERROR, 'CRITICAL': logging.CRITICAL
        }
        
        self._logger.log(log_level_map.get(level, logging.INFO), message_text, extra=audit_context)
        
        if self.persistence:
            from datetime import datetime
            adesso = datetime.now().strftime("%Y-%m-%d")
            await self.storekeeper.store("id", repository="logging", payload=constants, filter={'eq': {'filename': f'{adesso}.log'}})

    async def read(self, *services: Any, **constants: Any) -> List[Dict[str, Any]]:
        """Lettura degli asset immagazzinati o della history di esecuzione."""
        domain_pattern: str = constants.get('domain', '*')
        results: List[Dict[str, Any]] = []

        for registered_domain in self._history.keys():
            if fnmatch.fnmatch(registered_domain, domain_pattern):
                pointer, messages = self._history[registered_domain]
                if pointer < len(messages):
                    self._history[registered_domain][0] = len(messages)
                    results.append({
                        'domain': registered_domain,
                        'events': messages[pointer:]
                    })
        return results