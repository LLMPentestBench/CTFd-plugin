import logging

from ..scaffoldmgr import Scaffold

logger = logging.getLogger("llmpentestbench.scaffolds.deadend-cli")

def _build_prompt(challenge):
    prompt = f"CTF challenge name: `{challenge.name}`. "
    prompt += f"Description: `{challenge.description}`. "
    prompt += f"Category: `{challenge.category}`. "
    return prompt

class DeadendCLI(Scaffold):
    def __init__(self):
        super().__init__("deadend-cli", "Deadend CLI")

    def get_image_name(self):
        return f"ghcr.io/llmpentestbench/agent-deadend:latest"

    def get_internal_model_name(self):
        return "deadend-cli"

    def set_llm_key_command(self, llm_key: str) -> str:
        return f"/root/set_key.sh {llm_key}"

    def get_command(self, challenge) -> list[str]:
        prompt = _build_prompt(challenge)
        target = challenge.connection_info
        return ["deadend", "--target", target, "--prompt", prompt]

def load():
    return DeadendCLI()
