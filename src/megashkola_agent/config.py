import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    github_token: str
    github_repo: str
    base_branch: str = "main"
    agent_label: str = "agent"
    reviewer_bot_login: str = ""
    llm_provider: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    max_iterations: int = 3


def load_settings() -> Settings:
    return Settings(
        github_token=os.getenv("TOKEN", ""),
        github_repo=os.getenv("REPO", ""),
        base_branch=os.getenv("BASE_BRANCH", "main"),
        agent_label=os.getenv("AGENT_LABEL", "agent"),
        reviewer_bot_login=os.getenv("REVIEWER_BOT_LOGIN", ""),
        llm_provider=os.getenv("LLM_PROVIDER", ""),
        llm_api_key=os.getenv("LLM_API_KEY", ""),
        llm_model=os.getenv("LLM_MODEL", ""),
        max_iterations=int(os.getenv("MAX_ITERATIONS", "3")),
    )
