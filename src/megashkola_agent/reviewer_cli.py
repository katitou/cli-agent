from __future__ import annotations

import os

import typer

from .config import load_settings
from .llm import LlmClient
from .reviewer import ReviewerAgent, pr_number_from_event

app = typer.Typer(no_args_is_help=True)


@app.command()
def review(pr: int | None = typer.Option(None, "--pr", "-p")) -> None:
    settings = load_settings()
    if not settings.github_token or not settings.github_repo:
        raise typer.BadParameter("USER_ACCESS_TOKEN and TARGET_REPO are required")

    pr_number = pr or pr_number_from_event() or int(os.getenv("PR_NUMBER", "0"))
    if not pr_number:
        raise typer.BadParameter("Provide --pr or set PR_NUMBER")

    ci_status = os.getenv("CI_STATUS", "success")
    llm = LlmClient(settings.llm_provider, settings.llm_api_key, settings.llm_model)
    reviewer = ReviewerAgent(settings.github_token, settings.github_repo, llm)
    reviewer.review_pr(pr_number, ci_status)


if __name__ == "__main__":
    app()
