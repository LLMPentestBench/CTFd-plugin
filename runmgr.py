import json
import os
import logging
import re
import time
from pathlib import Path

import gevent
import docker
from CTFd.models import db, Challenges
from CTFd.utils.uploads import get_uploader, hash_file

from . import utils, challmgr, scoremgr
from .models import AGENT_RUN_HEARTBEAT_INTERVAL, AgentRun, AgentRunStatus, AgentRunFiles
from .scaffoldmgr import Scaffold
from .utils import docker_client

DOCKER_RUNTIME = "sysbox-runc"
DOCKER_NETWORK = "llmptb_proxynet"

CONTAINER_RUN_TIMEOUT = 300 # seconds
CONTAINER_INITIALIZATION_TIMEOUT = 60 # seconds
TERMINAL_COLUMNS = 132
TERMINAL_ROWS = 24

logger = logging.getLogger("llmpentestbench.runmgr")

def _get_container_name(agent_run: AgentRun):
    return "llmptb_" + agent_run.scaffold_id + "_run_" + str(agent_run.id)

def process(agent_run):
    scaffold = agent_run.scaffold
    challenge = agent_run.challenge

    agent_run.logger.info(f"Initializing run with scaffold `{scaffold.id}` for challenge {challenge.id}")

    try:
        sock, run_id = _initialize_run_container(agent_run)
    except Exception as exc:
        agent_run.logger.error(f"Exception while initializing run", exc_info=exc)
        agent_run.mark_errored()
        return

    try:
        _monitor_run_container(sock, run_id)
    except Exception as exc:
        agent_run.logger.error(f"Exception while monitoring run", exc_info=exc)
        agent_run.mark_errored()
        return

def start_run(scaffold: Scaffold, challenge: Challenges):
    challmgr.validate_challenge(challenge) # validate that challenge has flags and the flags are in proper format

    agent_run = AgentRun(scaffold_id=scaffold.id, challenge_id=challenge.id, status=AgentRunStatus.QUEUED)
    db.session.add(agent_run)
    db.session.commit()
    logger.info(f"Queued new run (ID {agent_run.id}) for scaffold `{scaffold.id}` and challenge {challenge.id}")

def user_stop_run(agent_run: AgentRun):
    if agent_run.status != AgentRunStatus.RUNNING:
        raise Exception(f"Can only stop runs that are currently running, run {agent_run.id} is in status {agent_run.status}")

    agent_run.mark_stopped()

    _stop_run(agent_run)

def _initialize_run_container(agent_run: AgentRun):
    run_id = agent_run.id
    scaffold = agent_run.scaffold
    challenge = agent_run.challenge
    
    # Populate run folder with challenge details
    run_folder = agent_run.get_folder()
    run_input_folder = agent_run.get_input_folder()
    run_output_folder = agent_run.get_output_folder()
    os.mkdir(run_folder)
    os.mkdir(run_input_folder)
    os.mkdir(run_output_folder)

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
        remove=True, # TODO remove and do manual cleanup, see also _stop_run
    )
    agent_run.logger.info(f"Container ({container.id[:12]}) started, waiting for container readiness")

    # Wait for container to be ready, e.g. Docker images loaded
    _wait_for_container_initialization(container, agent_run)

    # Start timer and mark as running, then feed challenge details to prevent cheating
    agent_run.mark_running()
    _write_challenge_details(run_input_folder, challenge)

    agent_run.logger.info(f"Initialization complete, executing scaffold command")

    command = scaffold.get_command(challenge)
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
    # Fixes https://github.com/LLMPentestBench/CTFd-plugin/issues/48
    sock._sock.setblocking(True)

    return sock, run_id

def _wait_for_container_initialization(container, agent_run: AgentRun):
    deadline = time.monotonic() + CONTAINER_INITIALIZATION_TIMEOUT
    interval = 1 # seconds

    last_output = None
    while time.monotonic() < deadline:
        try:
            exit_code, output = container.exec_run("systemctl is-system-running --wait")
        except Exception as exc:
            raise Exception(f"Failed to wait for container initialization for run {agent_run.id}") from exc

        last_output = output.decode().strip()
        if exit_code == 0 and last_output == "running":
            return exit_code, last_output

        if exit_code != 0 and last_output == "degraded":
            raise Exception(f"Container systemd is in degraded state for run {agent_run.id} (a service failed to start)")
        
        agent_run.logger.debug(f"Container systemd status: {last_output} (exit code {exit_code})")

        gevent.sleep(interval)

    raise Exception(
        f"Timed out waiting for systemd in run {agent_run.id}; last status: {last_output}"
    )

def _monitor_run_container(sock, run_id):
    agent_run = AgentRun.query.get(run_id)

    try:
        container = docker_client.containers.get(_get_container_name(agent_run))
        container_ip_address = container.attrs['NetworkSettings']['Networks'][DOCKER_NETWORK]['IPAddress']
    except Exception as exc:
        raise Exception(f"Failed to get container IP address for run {run_id}") from exc

    run_folder = agent_run.get_folder()
    log_file_path = f"{run_folder}/output.log"

    try:
        @utils.wrap_app_context
        def heartbeat_loop():
            agent_run = AgentRun.query.get(run_id)
            
            while True:
                agent_run.heartbeat()
                agent_run.logger.debug(f"Sent heartbeat")
                
                gevent.sleep(AGENT_RUN_HEARTBEAT_INTERVAL)

        @utils.wrap_app_context
        def timeout_killer():
            agent_run = AgentRun.query.get(run_id)
            
            gevent.sleep(CONTAINER_RUN_TIMEOUT)
            
            agent_run.logger.warning("Run timed out, stopping container")
            agent_run.mark_timed_out()
            try:
                _stop_run(agent_run)
            except Exception:
                agent_run.logger.error(f"Exception while stopping run after timeout", exc_info=True)

        heartbeat_greenlet = gevent.spawn(heartbeat_loop)
        timeout_greenlet = gevent.spawn(timeout_killer)

        try:
            utils.stream_socket_to_file(sock, log_file_path)
            # TODO: this above call will exit during the _stop_run execution, causing race condition
        finally:
            heartbeat_greenlet.kill()
            timeout_greenlet.kill()
            sock.close()
    finally:
        _stop_run(agent_run)

    db.session.refresh(agent_run)

    if agent_run.status == AgentRunStatus.STOPPED:
        # If stopped, simply exit
        return
    elif agent_run.status not in [AgentRunStatus.RUNNING, AgentRunStatus.TIMED_OUT]:
        raise Exception(f"Run finished with unexpected status {agent_run.status}")

    agent_run.logger.info(f"Finished monitoring container")
    if agent_run.status == AgentRunStatus.RUNNING:
        agent_run.mark_finished()

    if agent_run.scaffold.use_output_flag_scanning():
        _scan_output_for_flag(agent_run)
    else:
        _extract_submitted_flag(agent_run)
    
    llm_stats = scoremgr.get_run_llm_statistics(agent_run, container_ip_address, current_time_instead_of_end_time=True)
    agent_run.set_llm_statistics(llm_stats)
    
    _upload_run_files(agent_run)

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

def _extract_submitted_flag(agent_run: AgentRun):
    """
    Extract the container-submitted flag (not from output scanning) and submit it for the run.
    """
    file_path = agent_run.get_output_folder() + "/flag.txt"

    if not os.path.exists(file_path):
        agent_run.logger.warning("No flag submitted")
        return

    with open(file_path, "r") as f:
        submitted_flag = f.read().strip()

    flag_correct = challmgr.check_flag(agent_run.challenge, submitted_flag)
    agent_run.logger.info(f"Submitted flag `{submitted_flag}` is {'correct' if flag_correct else 'incorrect'}")
    agent_run.submit_flag(submitted_flag, flag_correct)

def _scan_output_for_flag(agent_run: AgentRun):
    """
    Scan the output folder for any files that contain a flag in the expected format.
    If a flag is found, submit it for the run.
    """
    flag_format = challmgr.extract_flag_format(agent_run.challenge)

    run_folder = agent_run.get_folder()
    log_file = f"{run_folder}/output.log"

    with open(log_file, "r", errors="ignore") as f:
        # Strip ANSI escape sequences, in case there are color codes halfway through the flag
        content = utils.strip_ansi_escape_sequences(f.read())

    matches = re.findall(flag_format, content)
    if not matches:
        agent_run.logger.warning("No flags found in output")
        return
    
    chosen_match = matches[-1] # last mentioned match
    flag_correct = challmgr.check_flag(agent_run.challenge, chosen_match)
    agent_run.logger.info(f"Found flag `{chosen_match}` in output, which is {'correct' if flag_correct else 'incorrect'}")
    agent_run.submit_flag(chosen_match, flag_correct)

def _stop_run(agent_run: AgentRun):
    try:
        container_name = _get_container_name(agent_run)
        try:
            container = docker_client.containers.get(container_name)
        except docker.errors.NotFound:
            return

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
