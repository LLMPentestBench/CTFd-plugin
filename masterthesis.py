import abc
from enum import Enum
import glob
import importlib
import os

from flask import Blueprint, render_template, current_app

from CTFd import CTFdFlask
from CTFd.utils.decorators import admins_only, authed_only
from CTFd.plugins import register_user_page_menu_bar

blueprint = Blueprint(
    "masterthesis",
    __name__,
    template_folder="templates",
    static_folder="assets",
    static_url_path="/plugins/masterthesis/assets",
)

# TODO separate html views and api logic into separate files
class ScaffoldStatus(Enum):
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"

class Scaffold(abc.ABC):
    name: str

    def __init__(self, name: str):
        self.name = name
    
    def start(self):
        ...
    
    def stop(self):
        ...
        # TODO look into connection to Docker (py docker lib, sock exposed, etc)
    
    def status(self) -> ScaffoldStatus:
        ...

# TODO: check how we should deal with in-memory data (redis / global variables). also e.g. state of scaffold
scaffolds = []
def load_scaffolds():
    scaffolds = []
    
    modules = sorted(glob.glob(current_app.plugins_dir + "/masterthesis/scaffolds/*"))
    blacklist = {"__pycache__"}
    
    for module in modules:
        module_name = os.path.basename(module)
        if os.path.isfile(module) and module_name not in blacklist:
            module = importlib.import_module("." + module_name[:-3], package="CTFd.plugins.masterthesis.scaffolds")
            scaffold = module.load()
            scaffolds.append(scaffold)
    return scaffolds

@blueprint.route('/admin/masterthesis')
@admins_only
def view_config():
    # scaffolds = [
    #     {
    #         "name": "PentestGPT",
    #         "status": ScaffoldStatus.STOPPED,
    #     }
    # ]
    # scaffolds2 = map(lambda s: {"name": s.name, "status": s.status().value}, scaffolds)
    # TODO scaffold status in globals of template?
    return render_template('masterthesis/admin/config.html', scaffolds=scaffolds, ScaffoldStatus=ScaffoldStatus)

@authed_only
@blueprint.route('/masterthesis')
def view_masterthesis():
    return render_template('masterthesis/user/view.html')



# TODO set up logging
def load(app: CTFdFlask):
    app.register_blueprint(blueprint)
    register_user_page_menu_bar("Master Thesis", "/masterthesis")
    
    global scaffolds
    scaffolds = load_scaffolds()
