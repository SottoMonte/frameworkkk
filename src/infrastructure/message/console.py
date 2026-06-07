import sys
import logging
import time

import message

class Adapter(message.Port):
    
    ANSI_COLORS = {
        'DEBUG': "\033[96m",    # Ciano chiaro
        'INFO': "\033[92m",     # Verde
        'WARNING': "\033[93m",  # Giallo
        'ERROR': "\033[91m",    # Rosso
        'CRITICAL': "\033[95m"  # Magenta
    }
    RESET_COLOR = "\033[0m"  # Reset colori ANSI

    def __init__(self, **constants):
        
        #self.config = constants['config']
        '''self.history = dict()
        self.start_time = time.time()
        # Creazione del logger
        self.logger = logging.getLogger("self.config['project']['identifier']")
        self.logger.propagate = False 
        self.logger.setLevel(logging.DEBUG)
        self.processable = ['log']
        
        # Handler per la console
        ch = logging.StreamHandler()
        if constants['config']['project'].get('mode') == 'production':
            ch.setLevel(logging.INFO)  # In produzione, solo INFO e superiori (esclude DEBUG)
        else:
            ch.setLevel(logging.DEBUG)

        # 2. Modifica il Formatter per includere il campo 'domain' e transaction_id
        formatter = self.ColoredFormatter(
            constants.get('format', "%(asctime)s.%(msecs)03d | [T+%(delta_ms)s]ms | [ΔT%(delta_inter_ms)s]ms | %(levelname)-16s | %(filename)s:%(lineno)d | %(funcName)-25s | %(process)d | [tx:%(transaction_id)s] | %(message)s"),
            datefmt="%Y-%m-%d %H:%M:%S"
        )

        ch.setFormatter(formatter)
        self.logger.addFilter(self._TimerFilter(self.start_time)) 
        self.logger.addHandler(ch)'''

    '''class _TimerFilter(logging.Filter):
        """Calcola e aggiunge il tempo trascorso (delta) dall'avvio del sistema."""
        def __init__(self, start_time):
            super().__init__()
            self.start_time = start_time

        def filter(self, record):
            # Calcola il delta time in secondi
            delta_seconds = record.created - self.start_time
            # Lo formatta in millisecondi con 3 decimali (es. 000000123.456)
            record.delta_ms = f"{delta_seconds * 1000:012.3f}"
            return True'''
    

    async def can(self, *services, **constants):
        return constants['name'] in self.processable

    async def post(self, *services, **constants):
        print(f"[console] {constants}")

    async def read(self, *services, **constants):
        domain = constants.get('domain', 'info')
        identity = constants.get('identity', '')
        results = []
        matching_domains = [d for d in self.history.keys() if language.wildcard_match(d, domain)]
        for dom in matching_domains:
            last, messages = self.history.get(dom, [0, []])
            if last < len(messages):
                self.history[dom][0] += 1
                results.append({'domain': dom, 'message': messages[last:]})
                #results.extend(messages[last:])
        return results

        '''if domain in self.history:
            last,messages = self.history.get(domain,[0,[]])
            #last = last.get(identity,0)
            if last < len(messages):
                self.history[domain][0] += 1
                #self.history.get(domain,[{},[]])[0].get(identity) = len(messages)
                return messages[last:]'''
        return []