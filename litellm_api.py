import requests
import logging
from datetime import datetime, timedelta

from .config import CONFIG
from .models import AgentRun, AgentRunLLMStatistics

LITELLM_HOST = CONFIG.litellm.host
LITELLM_KEY = CONFIG.litellm.key
EMBEDDER_MODEL_NAME = CONFIG.litellm.embedder_model

LITELLM_SPEND_LOGS_FETCH_PAGE_SIZE = 100 # max 100

logger = logging.getLogger("llmpentestbench.litellm_api")

def get_key_alias_for_run(run: AgentRun) -> str:
    """
    Returns the LiteLLM key alias for a given run.
    """
    return f"llmptb-{run.id}"

def get_run_llm_statistics(run: "AgentRun") -> "AgentRunLLMStatistics":
    """
    Fetches the LLM statistics for a given AgentRun from LiteLLM,
    filtering based on the LiteLLM key, the container's IP address and the run's time range.

    In case the container is still running, set current_time_instead_of_end_time to True.
    """
    key_alias = get_key_alias_for_run(run)
    start_date = run.start_time
    end_date = run.start_time + timedelta(days=999) # must provide a start and end date, this should cover the end date
    
    start_date_f = start_date.strftime("%Y-%m-%d %H:%M:%S").replace(" ", "%20")
    end_date_f = end_date.strftime("%Y-%m-%d %H:%M:%S").replace(" ", "%20")
    logger.info(f"Fetching spend logs for run {run.id} from LiteLLM between {start_date} and {end_date}")

    page = 1
    
    # Accumulated statistics
    calls_total = 0
    calls_failed = 0
    total_spend = 0
    total_prompt_tokens = 0
    total_completion_tokens = 0
    
    total_llm_time_seconds = 0

    while True:
        url = f"{LITELLM_HOST}/spend/logs/v2?key_alias={key_alias}&start_date={start_date_f}&end_date={end_date_f}&page={page}&page_size={LITELLM_SPEND_LOGS_FETCH_PAGE_SIZE}"
        req = requests.get(url, headers={"Authorization": f"Bearer {LITELLM_KEY}"})
        if req.status_code != 200:
            raise Exception(f"Failed to fetch spend logs: {req.status_code} - {req.text}")
        data = req.json()
        entries = data.get("data", [])
        logger.info(f"Fetched {len(entries)} spend log entries from LiteLLM for run {run.id} (page {page})")

        for entry in entries:
            calls_total += 1
            total_spend += entry.get("spend", 0)
            total_prompt_tokens += entry.get("prompt_tokens", 0)
            total_completion_tokens += entry.get("completion_tokens", 0)

            if entry.get("status") == "failure":
                calls_failed += 1

            end_time = datetime.fromisoformat(entry.get("endTime"))
            start_time = datetime.fromisoformat(entry.get("startTime"))
            total_llm_time_seconds += (end_time - start_time).total_seconds()
        
        if len(entries) < LITELLM_SPEND_LOGS_FETCH_PAGE_SIZE:
            break
        page += 1
    
    average_tps = total_completion_tokens / total_llm_time_seconds if total_llm_time_seconds > 0 else 0

    logger.info(f"Fetched {calls_total} spend log entries from LiteLLM for run {run.id}. Total spend: {total_spend}, Total prompt tokens: {total_prompt_tokens}, Total completion tokens: {total_completion_tokens}, Failed requests: {calls_failed}, Average tokens per second: {average_tps:.2f}")

    return AgentRunLLMStatistics(
        calls_total=calls_total,
        calls_failed=calls_failed,
        total_spend=total_spend,
        total_prompt_tokens=total_prompt_tokens,
        total_completion_tokens=total_completion_tokens,
        total_time=total_llm_time_seconds
    )

def key_exists(key_alias: str) -> bool:
    """
    Checks if a LiteLLM key exists for the given key_alias.
    """
    req = requests.get(f"{LITELLM_HOST}/key/aliases", headers={"Authorization": f"Bearer {LITELLM_KEY}"})

    if req.status_code != 200:
        raise Exception(f"Failed to fetch LiteLLM key aliases: {req.status_code} - {req.text}")
    
    data = req.json()
    
    return key_alias in data['aliases']

def create_key_for_run(run: AgentRun) -> str:
    """
    Returns the LiteLLM key for a given run.
    """
    litellm_key_alias = get_key_alias_for_run(run)
    internal_alias = run.scaffold.get_internal_model_name()

    if key_exists(litellm_key_alias):
        delete_key_alias(litellm_key_alias)

    req = requests.post(f"{LITELLM_HOST}/key/generate", headers={"Authorization": f"Bearer {LITELLM_KEY}", "Content-Type": "application/json"}, json={
        "models": [internal_alias, "embedding-model"],
        "aliases": {
            internal_alias: run.model,
            "embedding-model": EMBEDDER_MODEL_NAME
        },
        "key_alias": litellm_key_alias,
    })

    if req.status_code != 200:
        raise Exception(f"Failed to generate LiteLLM key for run {run.id}: {req.status_code} - {req.text}")
    
    data = req.json()
    key = data.get("key")

    return key

def delete_key_for_run(run: AgentRun):
    """
    Deletes the LiteLLM key for a given run.
    """
    litellm_key_alias = f"llmptb-{run.id}"

    delete_key_alias(litellm_key_alias)

def delete_key_alias(key_alias: str):
    req = requests.post(f"{LITELLM_HOST}/key/delete", headers={"Authorization": f"Bearer {LITELLM_KEY}"}, json={"key_aliases": [key_alias]})

    if req.status_code != 200:
        raise Exception(f"Failed to delete LiteLLM key for alias {key_alias}: {req.status_code} - {req.text}")

def list_models() -> list[str]:
    """
    Returns a list of all available models in LiteLLM.
    """
    req = requests.get(f"{LITELLM_HOST}/models", headers={"Authorization": f"Bearer {LITELLM_KEY}"})

    if req.status_code != 200:
        raise Exception(f"Failed to fetch LiteLLM models: {req.status_code} - {req.text}")
    
    data = req.json()

    return [model['id'] for model in data['data'] if model['object'] == 'model']
