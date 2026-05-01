import os
import abc
from enum import Enum
import logging
import docker

from CTFd.forms import self

from . import utils

_scaffolds: list['Scaffold'] = []
logger = logging.getLogger("masterthesis.scaffoldmgr")

docker_client = docker.from_env()

class ScaffoldStatus(Enum):
    UNAVAILABLE = "unavailable"
    STOPPED = "stopped"
    RUNNING = "running"

class Scaffold(abc.ABC):
    id: str
    name: str
    docker_container_name: str

    def __init__(self, id: str, name: str):
        self.id = id
        self.name = name
        self.docker_container_name = f"scaffold-{self.id}"  
    
    def _get_container(self):
        try:
            return docker_client.containers.get(self.docker_container_name)
        except docker.errors.NotFound:
            return None

    def start(self):
        container = self._get_container()
        if not container:
            raise Exception(f"Container {self.docker_container_name} not found for scaffold {self.name}")

        logger.info(f"Starting scaffold {self.name} using container {self.docker_container_name}")
        container.start()
    
    def stop(self):
        container = self._get_container()
        if not container:
            raise Exception(f"Container {self.docker_container_name} not found for scaffold {self.name}")

        logger.info(f"Stopping scaffold {self.name} using container {self.docker_container_name}")
        container.stop()
    
    def status(self) -> ScaffoldStatus:
        container = self._get_container()
        if not container:
            return ScaffoldStatus.UNAVAILABLE
        
        # container.status is restarting, running, paused or exited
        # possibly more, see https://www.baeldung.com/ops/docker-container-states
        if container.status == "running":
            return ScaffoldStatus.RUNNING
        else:
            return ScaffoldStatus.STOPPED

def _load_scaffolds() -> list['Scaffold']:
    scaffolds = []

    modules = utils.load_modules(os.path.join(os.path.dirname(__file__), "scaffolds"))
    for module in modules:
        try:
            scaffold: 'Scaffold' = module.load()
            scaffolds.append(scaffold)
            logger.info(f"Loaded module {scaffold.name}")
        except Exception as exc:
            logger.error(f"Exception while loading scaffold {module.__name__}", exc_info=exc)

    return scaffolds

def get_scaffolds() -> list['Scaffold']:
    return _scaffolds

def _get_scaffold(scaffold_id: str) -> 'Scaffold | None':
    return next((s for s in _scaffolds if s.id == scaffold_id), None)

def start_scaffold(scaffold_id: str) -> bool:
    scaffold = _get_scaffold(scaffold_id)
    if not scaffold:
        logger.error(f"Scaffold with id {scaffold_id} not found")
        return False
    
    try:
        scaffold.start()
        return True
    except Exception as exc:
        logger.error(f"Exception while starting scaffold {scaffold.name}", exc_info=exc)
        return False

def stop_scaffold(scaffold_id: str) -> bool:
    scaffold = _get_scaffold(scaffold_id)
    if not scaffold:
        logger.error(f"Scaffold with id {scaffold_id} not found")
        return False

    try:
        scaffold.stop()
        return True
    except Exception as exc:
        logger.error(f"Exception while stopping scaffold {scaffold.name}", exc_info=exc)
        return False

def load():
    global _scaffolds
    _scaffolds = _load_scaffolds()
