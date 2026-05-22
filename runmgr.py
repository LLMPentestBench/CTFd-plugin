import os
import logging
import threading
import asyncio

from CTFd.models import db

from . import utils
from .models import AgentRun, AgentRunStatus
from .scaffoldmgr import Scaffold
from .utils import docker_client

DOCKER_RUNTIME = "sysbox-runc"
DOCKER_NETWORK = "mt_proxynet"

CONTAINER_RUN_TIMEOUT = 60 # seconds
TERMINAL_COLUMNS = 132
TERMINAL_ROWS = 24

logger = logging.getLogger("llmpentestbench.runmgr")

def start_run(scaffold: Scaffold, challenge_id):
    agent_run = AgentRun(scaffold_id=scaffold.id, challenge_id=challenge_id, status=AgentRunStatus.INITIATING)
    db.session.add(agent_run)
    db.session.commit()

    run_id = agent_run.id

    agent_run.logger.info(f"Starting run with scaffold `{scaffold.id}` for challenge {challenge_id}")
    
    try:
        os.mkdir(agent_run.get_folder())

        container_name = "llmptb_" + scaffold.id + "_run_" + str(run_id)

        container = docker_client.containers.run(
            scaffold.get_image_name(),
            detach=True,
            tty=True,
            stdin_open=True,
            runtime=DOCKER_RUNTIME,
            network=DOCKER_NETWORK,
            name=container_name,
            remove=True, # TODO remove and do manual cleanup, see also _monitor_run_container finally block
        )
        agent_run.logger.info(f"Container ({container.id[:12]}) started")
        
        command = scaffold.get_command()
        _, sock = container.exec_run(
            f"bash --login -c '{command}'",
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
        
        thread = threading.Thread(target=asyncio.run, args=(_monitor_run_container(container, sock, run_id),), daemon=True)
        thread.start()
    except Exception as exc:
        agent_run.logger.error(f"Exception while starting run", exc_info=exc)
        agent_run.mark_errored()
        raise exc

@utils.wrap_app_context
async def _monitor_run_container(container, sock, run_id):
    agent_run = AgentRun.query.get(run_id)
    agent_run.mark_running()

    run_folder = agent_run.get_folder()
    log_file_path = f"{run_folder}/output.log"

    try:
        try:
            # TODO could set socket in timeout mode (e.g. 1s), and keep reading until X seconds passed, to reduce to only 1 thread instead of 2
            async with asyncio.timeout(CONTAINER_RUN_TIMEOUT):
                agent_run.logger.info(f"Start monitoring container")

                await asyncio.to_thread(utils.stream_socket_to_file, sock._sock, log_file_path)
        except asyncio.TimeoutError:
            pass # ignore timeout
        
        agent_run.logger.info(f"Finished monitoring container")

        sock.close()
        container.stop(timeout=0) # TODO lighter way of stopping, e.g. sending non-kill signal first and fully timing out later if needed
    except Exception as exc:
        agent_run.logger.error(f"Exception while monitoring container", exc_info=exc)
    finally:
        # container.remove(force=True)
        agent_run.mark_finished()

        time_taken = agent_run.end_time.timestamp() - agent_run.start_time.timestamp()

        agent_run.logger.info(f"Container finished in {time_taken:.2f} seconds")
        # TODO when CTFd crashes, container remains but it shouldnt

def load():
    # TODO cleanup
    pass
