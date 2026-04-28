import os
import abc
from enum import Enum
import logging

from . import utils

# TODO no static data
_scaffolds: list['Scaffold'] = []
logger = logging.getLogger("masterthesis.scaffoldmgr")

class ScaffoldStatus(Enum):
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"

class Scaffold(abc.ABC):
    name: str

    def __init__(self, name: str):
        self.name = name
    
    def start(self):
        ...
    
    def stop(self):
        ...
        # TODO look into connection to Docker (py docker lib, sock exposed, etc)
    
    def status(self) -> ScaffoldStatus:
        ...

def load_scaffolds() -> list['Scaffold']:
    scaffolds = []
    
    modules = utils.load_modules(os.path.join(os.path.dirname(__file__), "scaffolds"))
    for module in modules: # TODO safe loading
        try:
            scaffold: 'Scaffold' = module.load()
            scaffolds.append(scaffold)
            logger.info(f"Loaded module {scaffold.name}")
        except Exception as exc:
            logger.error(f"Exception while loading scaffold {module.__name__}", exc_info=exc)

    return scaffolds

def get_scaffolds() -> list['Scaffold']:
    return _scaffolds

def load():
    global _scaffolds
    _scaffolds = load_scaffolds()
