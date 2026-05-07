import logging

from ..scaffoldmgr import Scaffold

logger = logging.getLogger("llmpentestbench.scaffolds.example")

class ExampleScaffold(Scaffold):
    def __init__(self):
        super().__init__("example", "Example Scaffold")

    def get_image_name(self):
        return f"mt-baseimage:latest"

    def get_command(self) -> str:
        return "echo $NODE_EXTRA_CA_CERTS && echo abc"

def load():
    return ExampleScaffold()