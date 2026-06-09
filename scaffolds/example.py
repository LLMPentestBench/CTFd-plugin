import logging

from ..scaffoldmgr import Scaffold

logger = logging.getLogger("llmpentestbench.scaffolds.example")

class ExampleScaffold(Scaffold):
    def __init__(self):
        super().__init__("example", "Example Scaffold")

    def get_image_name(self):
        return f"llmptb-baseimage:latest"

    def get_command(self) -> str:
        return "echo Hello World! && sleep 5 && echo Goodbye World!"

def load():
    return ExampleScaffold()