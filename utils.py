import functools
import os
import importlib
import inspect

import docker
import flask

from CTFd.plugins.challenges.logic import challenge_attempt_any

docker_client: docker.DockerClient = docker.from_env()

def load_modules(folder: str) -> list:
    """
    Loads the modules from the given folder, returning a list of all imported modules.
    """
    modules = []
    
    # Extract relative to root, e.g. `CTFd.plugins.llmpentestbench.scaffolds`
    package = os.path.relpath(folder).replace("/", ".")
    
    for filename in os.listdir(folder):
        if not os.path.isfile(os.path.join(folder, filename)) or not filename.endswith(".py"):
            continue
        module_name = os.path.basename(filename)[:-3] # cut off .py
        
        module = importlib.import_module("." + module_name, package=f"{package}")
        modules.append(module)
    
    return modules

def stream_socket_to_file(sock, file_path, buffer_size=4096):
    """
    Streams the binary content received on the given socket to the given file path
    """
    with open(file_path, "wb") as f:
        while True:
            data = sock.recv(buffer_size)
            if not data:
                break
            f.write(data)
            f.flush()

def wrap_app_context(func):
    """
    Decorator to wrap a function in the Flask app context, allowing it to use the DB session and other Flask features.
    Works for both sync and async functions.
    """
    current_app = flask.current_app._get_current_object()

    if inspect.iscoroutinefunction(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            with current_app.app_context():
                return await func(*args, **kwargs)
        return wrapper
    else:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with current_app.app_context():
                return func(*args, **kwargs)
        return wrapper

def check_flag(challenge, flag) -> bool:
    """
    Checks if the given flag is correct for the given challenge by using the same logic as the challenge attempt endpoints.
    """
    return challenge_attempt_any(flag, challenge, challenge.flags).status == "correct"