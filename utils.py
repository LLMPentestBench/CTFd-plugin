import functools
import os
import importlib
import inspect
import re
import sys
import threading

import docker
import flask
from flask.helpers import get_debug_flag

_docker_client = threading.local()

def get_docker_client() -> docker.DockerClient:
    """
    Returns a Docker client instance.
    Do not reuse the instance across threads, call this function from the other thread instead.
    """
    if not hasattr(_docker_client, "client"):
        _docker_client.client = docker.from_env()
    return _docker_client.client

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
    buffer = bytearray(buffer_size)
    with open(file_path, "wb") as f:
        while True:
            bytes_read = sock.readinto(buffer)
            if not bytes_read:
                break
            f.write(buffer[:bytes_read])
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

# From https://stackoverflow.com/a/14693789
ANSI_STRIP_REGEX = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

def strip_ansi_escape_sequences(text: str) -> str:
    """
    Strips ANSI escape sequences from the given text.
    """
    return ANSI_STRIP_REGEX.sub('', text)

def detect_early_debug_mode() -> bool:
    """
    Detects if the app is running in debug mode, aims to be accurate even early in the app lifecycle.

    Due to CTFd's serve.py, at create_app() time the debug flag is not yet set,
    therefore this contains an exception checking if the app is started with serve.py (indicating debug mode).
    """
    return get_debug_flag() or sys.argv[0].endswith("serve.py")
