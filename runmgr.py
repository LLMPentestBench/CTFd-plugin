import json
import os
import logging
import threading
import asyncio
from pathlib import Path

from CTFd.models import db, Challenges
from CTFd.utils.uploads import get_uploader, hash_file

from . import utils, challmgr
from .models import AGENT_RUN_HEARTBEAT_INTERVAL, AgentRun, AgentRunStatus, AgentRunFiles
from .scaffoldmgr import Scaffold
from .utils import docker_client

DOCKER_RUNTIME = "sysbox-runc"
DOCKER_NETWORK = "llmptb_proxynet"

CONTAINER_RUN_TIMEOUT = 180 # seconds
TERMINAL_COLUMNS = 132
TERMINAL_ROWS = 24

logger = logging.getLogger("llmpentestbench.runmgr")

def _get_container_name(agent_run: AgentRun):
    return "llmptb_" + agent_run.scaffold_id + "_run_" + str(agent_run.id)

def start_run(scaffold: Scaffold, challenge_id):
    challenge = Challenges.query.filter_by(id=challenge_id).first()
    if not challenge:
        raise ValueError(f"Challenge with id {challenge_id} does not exist")
    challmgr.validate_challenge(challenge) # validate that challenge has flags and the flags are in proper format

    agent_run = AgentRun(scaffold_id=scaffold.id, challenge_id=challenge_id, status=AgentRunStatus.INITIATING)
    db.session.add(agent_run)
    db.session.commit()

    run_id = agent_run.id

    agent_run.logger.info(f"Starting run with scaffold `{scaffold.id}` for challenge {challenge_id}")
    
    try:
        # Populate run folder with challenge details
        run_folder = agent_run.get_folder()
        run_input_folder = agent_run.get_input_folder()
        run_output_folder = agent_run.get_output_folder()
        os.mkdir(run_folder)
        os.mkdir(run_input_folder)
        os.mkdir(run_output_folder)
        _write_challenge_details(run_input_folder, agent_run.challenge)

        container_name = _get_container_name(agent_run)
        container = docker_client.containers.run(
            scaffold.get_image_name(),
            detach=True,
            tty=True,
            stdin_open=True,
            runtime=DOCKER_RUNTIME,
            network=DOCKER_NETWORK,
            name=container_name,
            labels={
                "llmptb_run": str(run_id),
            },
            volumes={
                run_input_folder: {
                    "bind": "/llmptb/input",
                    "mode": "ro",
                },
                run_output_folder: {
                    "bind": "/llmptb/output",
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

def user_stop_run(agent_run: AgentRun):
    if agent_run.status != AgentRunStatus.RUNNING:
        raise Exception(f"Can only stop runs that are currently running, run {agent_run.id} is in status {agent_run.status}")

    agent_run.mark_stopped()

    _stop_run(agent_run)

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
    db.session.refresh(agent_run)
    agent_run.mark_running()

    run_folder = agent_run.get_folder()
    log_file_path = f"{run_folder}/output.log"

    try:
        timeout_task = asyncio.create_task(asyncio.sleep(CONTAINER_RUN_TIMEOUT))
        stream_task = asyncio.create_task(
            asyncio.to_thread(utils.stream_socket_to_file, sock, log_file_path)
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

        sock.close()
        _stop_run(agent_run)
    except Exception as exc:
        agent_run.logger.error(f"Exception while monitoring container", exc_info=exc)
    finally:
        submitted_flag = _extract_submitted_flag(agent_run.get_output_folder() + "/flag.txt")
        if submitted_flag is not None:
            flag_correct = challmgr.check_flag(agent_run.challenge, submitted_flag)
            agent_run.logger.info(f"Submitted flag `{submitted_flag}` is {'correct' if flag_correct else 'incorrect'}")
            agent_run.submit_flag(submitted_flag, flag_correct)
        else:
            agent_run.logger.warning("No flag submitted")

        _upload_run_files(agent_run)

        # Only mark finished when not stopped
        db.session.refresh(agent_run)
        if agent_run.status == AgentRunStatus.RUNNING:
            agent_run.mark_finished()

        time_taken = agent_run.end_time.timestamp() - agent_run.start_time.timestamp()

        agent_run.logger.info(f"Container finished in {time_taken:.2f} seconds")

def _write_challenge_details(folder, challenge) -> str:
    """
    Write the (limited) details of the CTFd challenge to a JSON file for the scaffold.
    """
    name = challenge.name
    description = challenge.description
    category = challenge.category
    connection_info = challenge.connection_info
    flag_format = challmgr.extract_flag_format(challenge)

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
            "flag_format": flag_format,
            "files": file_names,
        }, f, indent=4)

def _extract_submitted_flag(file_path) -> str | None:
    """
    Extract the flag from the given file path (a text file). Returns the flag, or None if the file does not exist.
    """
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            submitted_flag = f.read().strip()
    else:
        submitted_flag = None

    return submitted_flag

def _stop_run(agent_run: AgentRun):
    try:
        container_name = _get_container_name(agent_run)
        container = docker_client.containers.get(container_name)

        # TODO softer stopping for timeout?
        container.stop(timeout=0)
        # container.remove(force=True) # TODO add back when remove=True is gone
        agent_run.logger.info(f"Container stopped")
    except Exception as exc:
        agent_run.logger.error(f"Exception while stopping run", exc_info=exc)
        raise Exception(f"Failed to stop run {agent_run.id}") from exc

def _upload_run_files(agent_run: AgentRun):
    folder = agent_run.get_output_folder()
    uploader = get_uploader()

    for path in Path(folder).rglob("*"):
        try:
            if not path.is_file():
                continue

            filename = path.name
            relpath = str(path.relative_to(folder))
        
            with open(path, "rb") as f:
                sha1sum = hash_file(fp=f)

                location = uploader.upload(file_obj=f, filename=filename)

            run_file = AgentRunFiles(
                run_id=agent_run.id,
                path=relpath,
                location=location,
                sha1sum=sha1sum,
            )
            db.session.add(run_file)

            agent_run.logger.info(f"Uploaded run file `{relpath}` with sha1sum {sha1sum}")
        except Exception as exc:
            raise Exception(f"Failed to upload run file {path}") from exc

    # TODO merge this into remainder of the function, possibly split off into _upload_run_file for singular file
    log_file_path = f"{agent_run.get_folder()}/output.log"
    with open(log_file_path, "rb") as f:
        sha1sum = hash_file(fp=f)

        location = uploader.upload(file_obj=f, filename="output.log")
    run_file = AgentRunFiles(
        run_id=agent_run.id,
        path="output.log",
        location=location,
        sha1sum=sha1sum,
    )
    db.session.add(run_file)

    db.session.commit()

def cleanup_containers():
    """
    Cleanup any leftover containers from runs that were not properly stopped (e.g. due to CTFd crash). Should be called on plugin load.
    """
    for container in docker_client.containers.list(all=True, filters={"label": "llmptb_run"}):
        try:
            run_id = int(container.labels.get("llmptb_run"))
            agent_run = AgentRun.query.get(run_id)
            if not agent_run:
                logger.warning(f"Found leftover container named {container.name} with run_id {run_id} but no corresponding database entry, not cleaning up container")
                continue
            # Only clean up zombie runs, to avoid possible concurrency issues with multiple workers
            if agent_run.status == AgentRunStatus.RUNNING:
                logger.warning(f"Found running leftover container named {container.name} for run {run_id} in status {agent_run.status}, not cleaning up container")
                continue

            container.remove(force=True)
            logger.info(f"Cleaned up leftover container named {container.name} for run {run_id} ({container.id[:12]})")
        except Exception as exc:
            logger.error(f"Exception while cleaning up leftover container named {container.name} for run {run_id} ({container.id[:12]})", exc_info=exc)

def load():
    cleanup_containers()
