import logging

from ..scaffoldmgr import Scaffold

logger = logging.getLogger("llmpentestbench.scaffolds.example")

class ExampleScaffold(Scaffold):
    def __init__(self):
        super().__init__("example", "Example Scaffold")

    def get_image_name(self):
        return f"mt-baseimage:latest"

    def get_command(self) -> str:
        return "while true; do echo \"Hello, World!\"; sleep 5; done"

def load():
    return ExampleScaffold()