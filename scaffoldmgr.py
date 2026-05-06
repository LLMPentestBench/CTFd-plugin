import os
import abc
import logging
import docker

from . import utils

_scaffolds: dict[str, 'Scaffold'] = {}
logger = logging.getLogger("masterthesis.scaffoldmgr")

docker_client = docker.from_env()

class Scaffold(abc.ABC):
    id: str
    name: str
    docker_container_name: str

    def __init__(self, id: str, name: str):
        self.id = id
        self.name = name
        self.docker_container_name = f"scaffold-{self.id}" 

    def _get_image_name(self):
        return f"mt-baseimage:latest" 
    
    def is_available(self) -> bool:
        return docker_client.images.list(name=self._get_image_name()) != []
    
    def run_challenge(self):
        try:
            container = docker_client.containers.run(
                self._get_image_name(),
                detach=True,
                tty=True,
                stdin_open=True,
                runtime="sysbox-runc",
            )
            logger.info(f"Container started: {container.id[:12]}")

            code, sock = container.exec_run(
                "bash -c 'echo hello && bash'",
                stdin=True,
                tty=True,
                socket=True,
            )
            try:
                while True:
                    chunk = sock._sock.recv(4096)
                    if not chunk:
                        break
                    print(chunk.decode("utf-8", errors="replace"), end="", flush=True)
                    # print(repr(chunk)[2:-1].replace('\\n', '\n'), end="", flush=True)
            finally:
                sock.close()
        finally:
            container.stop()
            container.remove()

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
