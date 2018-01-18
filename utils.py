import logging
import constants

class VSphereLogger(logging.Logger):
    def __init__(self, name, level=logging.INFO):
        logging.Logger.__init__(self, name, level)
        destination = constants.LOG_FILE
        handler = logging.FileHandler(destination, mode='a')
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        self.propagate = False
        self.addHandler(handler)


logging.setLoggerClass(VSphereLogger)
