from __future__ import annotations

import os
import time

import typer

from megashkola_agent.code_agent import CodeAgent
from megashkola_agent.config import load_settings
from megashkola_agent.github_client import find_open_issues_with_label, get_repo
from megashkola_agent.utils import get_logger

app = typer.Typer(no_args_is_help=True)
log = get_logger("code-agent-cli")


@app.command()
def run_once(issue: int | None = typer.Option(None, "--issue", "-i")) -> None:
    """Process a single issue by number."""
    print("Finish")
    settings = load_settings()
    if issue is None:
        issue_env = os.getenv("ISSUE_NUMBER", "")
        issue = int(issue_env) if issue_env else None
    if issue is None:
        raise typer.BadParameter("Provide --issue or ISSUE_NUMBER env var")
    agent = CodeAgent(settings)
    agent.run_once(issue)
    print("Finish")


@app.command()
def poll() -> None:
    """Poll for open issues with the agent label and process them."""
    settings = load_settings()
    if not settings.github_token or not settings.github_repo:
        raise typer.BadParameter("GITHUB_TOKEN and GITHUB_REPO are required")

    handle = get_repo(settings.github_token, settings.github_repo)
    agent = CodeAgent(settings)

    while True:
        issues = list(find_open_issues_with_label(handle.repo, settings.agent_label))
        if not issues:
            log.info("No issues with label '%s'.", settings.agent_label)
        for issue in issues:
            try:
                agent.run_once(issue.number)
            except Exception as exc:
                log.exception("Failed on issue %s: %s", issue.number, exc)


if __name__ == "__main__":
    app()
