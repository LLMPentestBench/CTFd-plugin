import os
import abc
import logging
import threading
import asyncio

import docker

from . import utils

CONTAINER_RUN_TIMEOUT = 60 # seconds
TERMINAL_COLUMNS = 132
TERMINAL_ROWS = 24

_scaffolds: dict[str, 'Scaffold']
logger = logging.getLogger("llmpentestbench.scaffoldmgr")

docker_client = docker.from_env()

class Scaffold(abc.ABC):
    id: str
    name: str
    docker_container_name: str

    def __init__(self, id: str, name: str):
        self.id = id
        self.name = name
        self.docker_container_name = f"scaffold-{self.id}" 

    def get_image_name(self):
        ...

    def get_command(self) -> str:
        ...

    def is_available(self) -> bool:
        return docker_client.images.list(name=self.get_image_name()) != []

    def run_challenge(self):
        # TODO: Move container creation and exec to inside thread?
        container = docker_client.containers.run(
            self.get_image_name(),
            detach=True,
            tty=True,
            stdin_open=True,
            runtime="sysbox-runc",
            network="mt_proxynet",
        )
        logger.info(f"Container started: {container.id[:12]}")

        _, sock = container.exec_run(
            f"bash --login -c '{self.get_command()}'",
            stdin=True,
            tty=True,
            socket=True,
            workdir="/root",
            environment={ # Run in color with the terminal dimensions used by the frontend
                "TERM": "xterm-256color",
                "COLUMNS": str(TERMINAL_COLUMNS),
                "LINES": str(TERMINAL_ROWS),
            }
        )

        async def read_container():
            log_file_path = f"/tmp/{self.id}_container.log" # TODO

            try:
                event_loop = asyncio.get_event_loop()
                start_time = event_loop.time()

                try:
                    async with asyncio.timeout(CONTAINER_RUN_TIMEOUT):
                        await asyncio.to_thread(utils.stream_socket_to_file, sock._sock, log_file_path)
                except asyncio.TimeoutError:
                    pass # ignore timeout

                sock.close()
                container.stop(timeout=0) # TODO lighter way of stopping, e.g. sending non-kill signal first and fully timing out later if needed

                end_time = event_loop.time()
                time_taken = end_time - start_time
                logger.info(f"Container finished in {time_taken:.2f} seconds")
            except Exception as exc:
                logger.error(f"Exception while reading container output for {self.id}", exc_info=exc)
            finally:
                container.remove()
        
        thread = threading.Thread(target=asyncio.run, args=(read_container(),), daemon=True)
        thread.start()

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
