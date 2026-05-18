import os
import logging
import threading
import asyncio

import flask

from CTFd.models import db

from . import utils
from .models import AgentRun
from .scaffoldmgr import Scaffold
from .utils import docker_client

CONTAINER_RUN_TIMEOUT = 60 # seconds
TERMINAL_COLUMNS = 132
TERMINAL_ROWS = 24

logger = logging.getLogger("llmpentestbench.runmgr")

def start_run(scaffold: Scaffold, challenge_id):
    agent_run = AgentRun(scaffold_id=scaffold.id, challenge_id=challenge_id)
    db.session.add(agent_run)
    db.session.commit()
    
    run_id = agent_run.id
    run_folder = agent_run.get_folder()
    
    os.mkdir(run_folder)

    flask_current_app = flask.current_app._get_current_object()

    container_name = "llmptb_" + scaffold.id + "_run_" + str(run_id)

    # TODO: Move container creation and exec to inside thread?
    container = docker_client.containers.run(
        scaffold.get_image_name(),
        detach=True,
        tty=True,
        stdin_open=True,
        runtime="sysbox-runc",
        network="mt_proxynet",
        name=container_name,
    )
    logger.info(f"Container ({container.id[:12]}) started for run {run_id}")
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

    async def read_container():
        log_file_path = f"{run_folder}/output.log"

        try:
            try:
                async with asyncio.timeout(CONTAINER_RUN_TIMEOUT):
                    await asyncio.to_thread(utils.stream_socket_to_file, sock._sock, log_file_path)
            except asyncio.TimeoutError:
                pass # ignore timeout

            sock.close()
            container.stop(timeout=0) # TODO lighter way of stopping, e.g. sending non-kill signal first and fully timing out later if needed
        except Exception as exc:
            logger.error(f"Exception while reading container output for run {run_id}", exc_info=exc)
        finally:
            container.remove(force=True)

            # Wrap in app context to ensure DB session works
            with flask_current_app.app_context():
                agent_run = AgentRun.query.get(run_id)
                agent_run.mark_finished()

                time_taken = agent_run.end_time.timestamp() - agent_run.start_time.timestamp()

                logger.info(f"Container ({container.id[:12]}) of run {run_id} finished in {time_taken:.2f} seconds")
            # TODO when CTFd crashes, container remains but it shouldnt
    
    thread = threading.Thread(target=asyncio.run, args=(read_container(),), daemon=True)
    thread.start()
