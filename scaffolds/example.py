import logging

from ..scaffoldmgr import Scaffold, ScaffoldStatus

logger = logging.getLogger("masterthesis.scaffolds.example")

class ExampleScaffold(Scaffold):
    def __init__(self):
        super().__init__("Example Scaffold")
    
    def start(self):
        logger.info(f"Starting scaffold {self.name}")
    def stop(self):
        logger.info(f"Stopping scaffold {self.name}")
    def status(self) -> ScaffoldStatus:
        return ScaffoldStatus.RUNNING

def load():
    return ExampleScaffold()