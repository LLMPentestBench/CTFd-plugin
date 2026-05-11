import os
import importlib

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
