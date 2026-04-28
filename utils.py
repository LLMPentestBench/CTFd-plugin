import os
import importlib

def load_modules(folder: str):
    """
    Loads the modules from the given folder, returning a list of all imported modules.
    """
    modules = []
    
    # Extract relative to root, e.g. `CTFd.plugins.masterthesis.scaffolds`
    package = os.path.relpath(folder).replace("/", ".")
    
    for filename in os.listdir(folder):
        if not os.path.isfile(os.path.join(folder, filename)) or not filename.endswith(".py"):
            continue
        module_name = os.path.basename(filename)[:-3] # cut off .py
        
        module = importlib.import_module("." + module_name, package=f"{package}")
        modules.append(module)
    
    return modules