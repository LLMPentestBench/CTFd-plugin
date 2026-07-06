import requests
import logging
from datetime import datetime

from .models import AgentRun, AgentRunLLMStatistics

LITELLM_HOST = "http://localhost:4000"
LITELLM_KEY = "sk-M7lSa-wbdMaT6VtYLZYldQ" # TODO not hardcoded

LITELLM_FETCH_PAGE_SIZE = 100 # max 100

logger = logging.getLogger("llmpentestbench.scoremgr")

def get_run_llm_statistics(run: "AgentRun", ip_address: str, current_time_instead_of_end_time: bool = False) -> "AgentRunLLMStatistics":
    """
    Fetches the LLM statistics for a given AgentRun from LiteLLM,
    filtering based on the LiteLLM key, the container's IP address and the run's time range.

    In case the container is still running, set current_time_instead_of_end_time to True.
    """
    key_alias = run.scaffold.get_litellm_key_alias()
    run_ip = ip_address
    start_date = run.start_time

    if current_time_instead_of_end_time:
        end_date = datetime.utcnow()
    else:
        end_date = run.end_time
        if end_date is None:
            raise ValueError(f"Run {run.id} has no end_time set, and current_time_instead_of_end_time is False. Cannot fetch LLM statistics.")

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
        url = f"{LITELLM_HOST}/spend/logs/v2?key_alias={key_alias}&start_date={start_date_f}&end_date={end_date_f}&page={page}&page_size={LITELLM_FETCH_PAGE_SIZE}"
        req = requests.get(url, headers={"Authorization": f"Bearer {LITELLM_KEY}"})
        if req.status_code != 200:
            raise Exception(f"Failed to fetch spend logs: {req.status_code} - {req.text}")
        data = req.json()
        entries = data.get("data", [])
        logger.info(f"Fetched {len(entries)} spend log entries from LiteLLM for run {run.id} (page {page})")

        for entry in entries:
            ip = entry.get('requester_ip_address')
            if ip != run_ip:
                logger.warning(f"Skipping entry with IP {ip} for run {run.id} (expected {run_ip})")
                continue

            calls_total += 1
            total_spend += entry.get("spend", 0)
            total_prompt_tokens += entry.get("prompt_tokens", 0)
            total_completion_tokens += entry.get("completion_tokens", 0)
            
            if entry.get("status") == "failed":
                calls_failed += 1

            end_time = datetime.fromisoformat(entry.get("endTime"))
            start_time = datetime.fromisoformat(entry.get("startTime"))
            total_llm_time_seconds += (end_time - start_time).total_seconds()
        
        if len(entries) < LITELLM_FETCH_PAGE_SIZE:
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
