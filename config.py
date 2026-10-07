from dataclasses import dataclass, field
from pathlib import Path
import tomllib


@dataclass(frozen=True)
class LiteLLMConfig:
    host: str = "http://localhost:4000"
    key: str = ""
    embedder_model: str = "openai-text-embedding-3-small"


@dataclass(frozen=True)
class RunnerConfig:
    max_simultaneous_runs: int = 1
    docker_sysbox_runtime: str = "sysbox-runc"
    docker_container_litellm_name: str = "llmptb_litellm"
    docker_container_envoy_name: str = "llmptb_envoy"
    container_initialization_timeout: int = 60 # seconds
    litellm_data_fetch_delay: int = 10 # seconds


@dataclass(frozen=True)
class PluginConfig:
    litellm: LiteLLMConfig = field(default_factory=LiteLLMConfig)
    runner: RunnerConfig = field(default_factory=RunnerConfig)


CONFIG_PATH = Path(__file__).with_name("config.toml")


def load_config(config_path: Path = CONFIG_PATH) -> PluginConfig:
    if not config_path.exists():
        return PluginConfig()

    with config_path.open("rb") as config_file:
        raw_config = tomllib.load(config_file)

    litellm_config = raw_config.get("litellm", {})
    runner_config = raw_config.get("runner", {})

    return PluginConfig(
        litellm=LiteLLMConfig(
            host=litellm_config.get("host", LiteLLMConfig.host),
            key=litellm_config.get("key", LiteLLMConfig.key),
            embedder_model=litellm_config.get("embedder_model", LiteLLMConfig.embedder_model),
        ),
        runner=RunnerConfig(
            max_simultaneous_runs=int(
                runner_config.get("max_simultaneous_runs", RunnerConfig.max_simultaneous_runs)
            ),
            docker_sysbox_runtime=runner_config.get("docker_sysbox_runtime", RunnerConfig.docker_sysbox_runtime),
            docker_container_litellm_name=runner_config.get("docker_container_litellm_name", RunnerConfig.docker_container_litellm_name),
            docker_container_envoy_name=runner_config.get("docker_container_envoy_name", RunnerConfig.docker_container_envoy_name),
            container_initialization_timeout=int(
                runner_config.get("container_initialization_timeout", RunnerConfig.container_initialization_timeout)
            ),
            litellm_data_fetch_delay=int(
                runner_config.get("litellm_data_fetch_delay", RunnerConfig.litellm_data_fetch_delay)
            ),
        ),
    )


CONFIG = load_config()