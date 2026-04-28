import os
import abc
from enum import Enum

from . import utils

scaffolds = []

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

def load_scaffolds():
    scaffolds = []
    
    modules = utils.load_modules(os.path.join(os.path.dirname(__file__), "scaffolds"))
    for module in modules:
        scaffold = module.load()
        scaffolds.append(scaffold)

    return scaffolds

def load():
    global scaffolds
    scaffolds = load_scaffolds()