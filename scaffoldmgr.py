import os
import abc
import logging

from CTFd.models import Challenges

from . import utils
from .utils import docker_client

_scaffolds: dict[str, 'Scaffold']
logger = logging.getLogger("llmpentestbench.scaffoldmgr")

class Scaffold(abc.ABC):
    id: str
    name: str

    def __init__(self, id: str, name: str):
        self.id = id
        self.name = name

    def get_image_name(self):
        """
        Returns the name of the Docker image for this scaffold.
        """
        ...
    
    def get_internal_model_name(self) -> str:
        """
        The internal model name that is used for LLM queries.
        This name will be mapped to the correct model at runtime.
        """
        ...

    def set_llm_key_command(self, llm_key: str) -> str:
        """
        Returns the command to set the LiteLLM key in the scaffold container.
        """
        ...

    def get_command(self, challenge: Challenges) -> str | list[str]:
        """
        Returns the command to run the scaffold container for a given challenge.
        """
        ...

    def is_available(self) -> bool:
        return docker_client.images.list(name=self.get_image_name()) != []
    
    def use_output_flag_scanning(self) -> bool:
        """
        Override this method to return False if the scaffold image does it's own flag submission 
        by writing the flag to `/llmptb/output/flag.txt`.
        """
        return True

def get_scaffolds() -> list['Scaffold']:
    return list(_scaffolds.values())

def get_scaffold(scaffold_id: str) -> 'Scaffold | None':
    return _scaffolds.get(scaffold_id)

def _load_scaffolds() -> dict[str, 'Scaffold']:
    scaffolds = {}

    modules = utils.load_modules(os.path.join(os.path.dirname(__file__), "scaffolds"))
    for module in modules:
        try:
            scaffold: 'Scaffold' = module.load()
            scaffolds[scaffold.id] = scaffold
            logger.info(f"Loaded module {scaffold.name}")
        except Exception as exc:
            logger.error(f"Exception while loading scaffold {module.__name__}", exc_info=exc)

    return scaffolds

def load():
    global _scaffolds
    _scaffolds = _load_scaffolds()
