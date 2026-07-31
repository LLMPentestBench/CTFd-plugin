import re

from CTFd.plugins.challenges.logic import challenge_attempt_any
from CTFd.plugins.flags import CTFdStaticFlag, get_flag_class
from CTFd.models import Challenges

def check_flag(challenge, flag) -> bool:
    """
    Checks if the given flag is correct for the given challenge by using the same logic as the challenge attempt endpoints.
    """
    return challenge_attempt_any(flag, challenge, challenge.flags).status == "correct"

def extract_flag_format(challenge: Challenges) -> str:
    """
    Extracts the flag format as a regex pattern from a given challenge.

    Flag requiresments are:
    - Must be in format `PREFIX{SECRET}`
    - The secret part of the flag must have at least 6 characters

    For example, a challenge with flag `CTF{My_s3cr3t_Fl@g}` returns `CTF{[^}]{6,}}`.
    """
    if len(challenge.flags) != 1 or challenge.flags[0].type != CTFdStaticFlag.name:
        raise ValueError(f"Challenge {challenge.id} must have exactly one static flag")

    flag = challenge.flags[0].content
    
    m = re.fullmatch(r"(\w+)\{(.+)\}", flag)
    if m is None:
        raise ValueError("Flag does not match expected format of <PREFIX>{<SECRET>}")
    
    prefix = m.group(1)
    secret = m.group(2)

    if len(secret) < 6:
        raise ValueError("Flag secret is too short, should be at least 6 characters")

    # return regex pattern with prefix and a >6 character secret
    return f"{prefix}\\{{[^}}]{{6,}}\\}}"

def validate_challenge(challenge):
    """
    Validates that the challenge has exactly one static flag with a valid format.
    
    See `extract_flag_format` for the expected flag format.
    """
    extract_flag_format(challenge)
