import logging

from ..scaffoldmgr import Scaffold

logger = logging.getLogger("masterthesis.scaffolds.example")

class ExampleScaffold(Scaffold):
    def __init__(self):
        super().__init__("example", "Example Scaffold")

def load():
    return ExampleScaffold()