import json
import os
import logging
import threading
import asyncio

from CTFd.models import db
from CTFd.utils.uploads import get_uploader

from . import utils
from .models import AGENT_RUN_HEARTBEAT_INTERVAL, AgentRun, AgentRunStatus
from .scaffoldmgr import Scaffold
from .utils import docker_client

DOCKER_RUNTIME = "sysbox-runc"
DOCKER_NETWORK = "llmptb_proxynet"

CONTAINER_RUN_TIMEOUT = 180 # seconds
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
        # Populate run folder with challenge details
        run_folder = agent_run.get_folder()
        run_work_folder = agent_run.get_work_folder()
        os.mkdir(run_folder)
        os.mkdir(run_work_folder)
        _write_challenge_details(run_work_folder, agent_run.challenge)

        container_name = "llmptb_" + scaffold.id + "_run_" + str(run_id)
        container = docker_client.containers.run(
            scaffold.get_image_name(),
            detach=True,
            tty=True,
            stdin_open=True,
            runtime=DOCKER_RUNTIME,
            network=DOCKER_NETWORK,
            name=container_name,
            volumes={
                run_work_folder: { # TODO mount subfolder instead
                    "bind": "/llmptb",
                    "mode": "rw",
                }
            },
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
        raise Exception(f"Failed to start run {run_id} for scaffold {scaffold.id} and challenge {challenge_id}") from exc

def stop_run(agent_run: AgentRun):
    ... # TODO

async def _send_heartbeats(agent_run_id, interval=AGENT_RUN_HEARTBEAT_INTERVAL):
    while True:
        agent_run = AgentRun.query.get(agent_run_id)
        if agent_run is None or agent_run.is_finished():
            break

        agent_run.heartbeat()
        agent_run.logger.debug(f"Sent heartbeat")

        await asyncio.sleep(interval)

@utils.wrap_app_context
async def _monitor_run_container(container, sock, run_id):
    agent_run = AgentRun.query.get(run_id)
    agent_run.mark_running()

    run_folder = agent_run.get_folder()
    log_file_path = f"{run_folder}/output.log"

    try:
        timeout_task = asyncio.create_task(asyncio.sleep(CONTAINER_RUN_TIMEOUT))
        stream_task = asyncio.create_task(
            asyncio.to_thread(utils.stream_socket_to_file, sock._sock, log_file_path)
        )
        # Send heartbeats for zombie run detection
        heartbeat_task = asyncio.create_task(_send_heartbeats(run_id))

        try:
            # Wait for container to finish or timeout to expire
            await asyncio.wait(
                [timeout_task, stream_task],
                return_when=asyncio.FIRST_COMPLETED,
            )
        finally:
            # Cancel all tasks and wait for them to finish
            timeout_task.cancel()
            stream_task.cancel()
            heartbeat_task.cancel()

            await asyncio.gather(
                heartbeat_task, timeout_task, stream_task,
                return_exceptions=True,
            )

        agent_run.logger.info(f"Finished monitoring container")

        submitted_flag = _extract_submitted_flag(agent_run.get_work_folder() + "/flag.txt")
        if submitted_flag is not None:
            flag_correct = utils.check_flag(agent_run.challenge, submitted_flag)
            agent_run.logger.info(f"Submitted flag `{submitted_flag}` is {'correct' if flag_correct else 'incorrect'}")
        else:
            agent_run.logger.warning("No flag submitted")

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

def _write_challenge_details(folder, challenge) -> str:
    """
    Write the (limited) details of the CTFd challenge to a JSON file for the scaffold.
    """
    name = challenge.name
    description = challenge.description
    category = challenge.category
    connection_info = challenge.connection_info

    # Get files from file storage (local / S3), and write to challenge files folder
    files_folder = f"{folder}/files"
    if challenge.files:
        os.mkdir(files_folder)
    
    uploader = get_uploader()
    file_names = []
    for file in challenge.files:
        file_name = file.location.split("/")[-1]

        # Open file stream and write to the location in chunks
        with uploader.open(file.location, "rb") as f: 
            file_path = f"{files_folder}/{file_name}"
            with open(file_path, "wb") as dst:
                while chunk := f.read(1024*1024): # 1MB chunks
                    dst.write(chunk)
        
        file_names.append(file_name)
    
    with open(f"{folder}/challenge.json", "w") as f:
        json.dump({
            "name": name,
            "description": description,
            "category": category,
            "connection_info": connection_info,
            "files": file_names,
        }, f, indent=4)

def _extract_submitted_flag(file_path) -> str | None:
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            submitted_flag = f.read().strip()
    else:
        submitted_flag = None

    return submitted_flag

def load():
    # TODO cleanup
    pass
