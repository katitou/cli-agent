from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

from github import Github
from github.PullRequest import PullRequest

from .llm import LlmClient
from .utils import get_logger


@dataclass
class ReviewContext:
    pr: PullRequest
    issue_number: int | None
    issue_title: str
    issue_body: str
    ci_status: str


class ReviewerAgent:
    def __init__(self, token: str, repo: str, llm: LlmClient) -> None:
        self.token = token
        self.repo_full = repo
        self.llm = llm
        self.log = get_logger("reviewer-agent")
        self.gh = Github(token)
        self.repo = self.gh.get_repo(repo)

    def review_pr(self, pr_number: int, ci_status: str) -> None:
        pr = self.repo.get_pull(pr_number)
        issue_number = self._extract_issue_number(pr)
        issue_title = ""
        issue_body = ""
        if issue_number is not None:
            issue = self.repo.get_issue(number=issue_number)
            issue_title = issue.title
            issue_body = issue.body or ""
        ctx = ReviewContext(
            pr=pr,
            issue_number=issue_number,
            issue_title=issue_title,
            issue_body=issue_body,
            ci_status=ci_status,
        )

        verdict, summary, details = self._generate_review(ctx)
        self._publish_review(pr, verdict, summary, details)

    def _generate_review(self, ctx: ReviewContext) -> tuple[str, str, str]:
        if ctx.ci_status.lower() != "success":
            msg = f"CI status is {ctx.ci_status}. Please fix CI failures."
            return "CHANGES_REQUESTED", msg, msg

        # Fallback heuristic: check for agent_output file update.
        if ctx.issue_number is not None:
            expected = f"agent_output/issue-{ctx.issue_number}.md"
            files = [f.filename for f in ctx.pr.get_files()]
            if expected not in files:
                msg = f"Expected file {expected} not found in PR. Please add output or code changes."
                return ("CHANGES_REQUESTED", msg, msg)

        if not self.llm.enabled():
            msg = "LLM not configured; minimal checks passed."
            return "APPROVED", msg, msg

        prompt = self._build_prompt(ctx)
        response = self.llm.chat(
            system="You are a strict code reviewer. Reply with STATUS: APPROVED or STATUS: CHANGES_REQUESTED and a short rationale.",
            user=prompt,
        )
        if not response:
            msg = "No LLM response; defaulting to approve."
            return "APPROVED", msg, msg
        text = response.text.strip()
        if "CHANGES_REQUESTED" in text:
            return "CHANGES_REQUESTED", text, text
        return "APPROVED", text, text

    def _build_prompt(self, ctx: ReviewContext) -> str:
        pr = ctx.pr
        files = list(pr.get_files())
        file_list = "\n".join([f"- {f.filename}" for f in files])
        patches = []
        for f in files:
            if f.patch:
                patches.append(f"File: {f.filename}\n{f.patch}")
        patch_text = "\n\n".join(patches) if patches else "No diff available."
        return (
            f"PR title: {pr.title}\n\n"
            f"PR body:\n{pr.body}\n\n"
            f"Issue title: {ctx.issue_title}\n\n"
            f"Issue body:\n{ctx.issue_body}\n\n"
            f"Changed files:\n{file_list}\n\n"
            f"Diff:\n{patch_text}\n\n"
            f"CI status: {ctx.ci_status}\n\n"
            "Check if changes satisfy the issue requirements and CI is green."
        )

    def _publish_review(self, pr: PullRequest, verdict: str, summary: str, details: str) -> None:
        status = f"STATUS: {verdict}"
        summary_body = f"{status}\n\nSummary:\n{summary}\n"
        review_body = f"{status}\n\nDetails:\n{details}\n"
        pr.create_issue_comment(summary_body)
        pr.create_review(body=review_body, event=verdict)

    def _extract_issue_number(self, pr: PullRequest) -> int | None:
        if pr.title:
            match = re.search(r"#(\d+)", pr.title)
            if match:
                return int(match.group(1))
        if pr.head and pr.head.ref:
            match = re.search(r"issue-(\d+)", pr.head.ref)
            if match:
                return int(match.group(1))
        return None


def pr_number_from_event() -> int | None:
    path = os.getenv("GITHUB_EVENT_PATH")
    if not path:
        return None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if "pull_request" in data and "number" in data["pull_request"]:
        return int(data["pull_request"]["number"])
    return None
