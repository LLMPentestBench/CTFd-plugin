import logging

from ..scaffoldmgr import Scaffold

logger = logging.getLogger("llmpentestbench.scaffolds.example")

class ExampleScaffold(Scaffold):
    def __init__(self):
        super().__init__("example", "Example Scaffold")

    def get_image_name(self):
        return f"ghcr.io/llmpentestbench/agent-example:latest"

    def get_litellm_key_alias(self):
        return "example"

    def get_command(self, challenge) -> str:
        return "/entrypoint"

def load():
    return ExampleScaffold()