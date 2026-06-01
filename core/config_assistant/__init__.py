"""Config Assistant — meta-agent that parses arbitrary user input and produces a structured config plan.

Use case: user pastes a JSON dump (e.g. OpenClaw config), an .env, free
text with credentials, etc. The assistant figures out what's there and
proposes a list of actions Rugol should take. The user reviews and
applies. Tokens never get echoed back in the response.
"""
from core.config_assistant.parser import (
    ConfigAction,
    ConfigPlan,
    apply_plan,
    parse_user_input,
)

__all__ = ["ConfigPlan", "ConfigAction", "parse_user_input", "apply_plan"]
