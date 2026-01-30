from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass

from git import Repo

from megashkola_agent.config import Settings
from megashkola_agent.github_client import (
    create_or_update_pr,
    find_issue_by_number,
    find_pr_for_issue,
    get_latest_reviewer_comment,
    get_repo,
)
from megashkola_agent.llm import LlmClient
from megashkola_agent.utils import get_logger


@dataclass
class AgentContext:
    issue_number: int
    issue_title: str
    issue_body: str
    reviewer_feedback: str


class CodeAgent:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.log = get_logger("code-agent")
        self.llm = LlmClient(
            provider=settings.llm_provider,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
        )

    def run_once(self, issue_number: int) -> None:
        if not self.settings.github_token or not self.settings.github_repo:
            raise RuntimeError("GITHUB_TOKEN and GITHUB_REPO are required")

        handle = get_repo(self.settings.github_token, self.settings.github_repo)
        issue = find_issue_by_number(handle.repo, issue_number)

        pr = find_pr_for_issue(handle.repo, issue_number)
        reviewer_feedback = ""
        if pr:
            reviewer_login = self.settings.reviewer_bot_login or None
            latest = get_latest_reviewer_comment(pr, bot_login=reviewer_login)
            if latest:
                reviewer_feedback = latest
                if "STATUS: APPROVED" in latest:
                    self.log.info("PR already approved; nothing to do.")
                    return

        iteration = self._current_iteration(issue, handle.gh.get_user().login)
        if iteration >= self.settings.max_iterations:
            self.log.info("Max iterations reached; exiting.")
            return

        ctx = AgentContext(
            issue_number=issue_number,
            issue_title=issue.title,
            issue_body=issue.body or "",
            reviewer_feedback=reviewer_feedback,
        )

        repo = self._ensure_repo()
        branch = f"agent/issue-{issue_number}"
        self._checkout_branch(repo, branch)

        applied = self._apply_llm_patch(repo, ctx)
        if not applied:
            self._apply_fallback_change(ctx, str(repo.working_tree_dir) or os.getcwd())

        if not repo.is_dirty(untracked_files=True):
            self.log.info("No changes detected; skipping commit.")
        else:
            repo.git.add(A=True)
            repo.index.commit(f"Agent update for issue #{issue_number}")
            repo.git.push("-u", "origin", branch)

        pr_title = f"Agent: {issue.title} (#{issue_number})"
        pr_body = self._build_pr_body(ctx, iteration + 1)
        pr = create_or_update_pr(handle.repo, self.settings.base_branch, branch, pr_title, pr_body)

        self.log.info("PR ready: %s", pr.html_url)
        issue.create_comment(
            f"Code Agent created/updated PR: {pr.html_url}\n\nIteration: {iteration + 1}"
        )

    def _checkout_branch(self, repo: Repo, branch: str) -> None:
        repo.git.fetch("origin")
        if branch in repo.branches:
            repo.git.checkout(branch)
            try:
                repo.git.reset("--hard", f"origin/{branch}")
            except Exception:
                # Remote branch may not exist yet; keep local branch as-is.
                pass
            return
        repo.git.checkout(self.settings.base_branch)
        repo.git.checkout("-b", branch)

    def _apply_llm_patch(self, repo: Repo, ctx: AgentContext) -> bool:
        if not self.llm.enabled():
            return False
        system = (
            "You are a senior software engineer. Output ONLY a unified diff patch that applies cleanly. "
            "If unsure, output an empty response."
        )
        user = (
            f"Issue title: {ctx.issue_title}\n\nIssue body:\n{ctx.issue_body}\n\n"
            f"Reviewer feedback (if any):\n{ctx.reviewer_feedback}\n\n"
            "Return a git-style unified diff for the minimal fix."
        )
        response = self.llm.chat(system=system, user=user)
        if not response:
            return False
        patch = response.text.strip()
        if not patch:
            return False
        if "diff --git" not in patch:
            return False
        with tempfile.NamedTemporaryFile("w", delete=False) as tmp:
            tmp.write(patch)
            tmp_path = tmp.name
        try:
            repo.git.apply(tmp_path, whitespace="nowarn")
            return True
        except Exception:
            return False

    def _apply_fallback_change(self, ctx: AgentContext, repo_dir: str) -> None:
        output_dir = os.path.join(repo_dir, "agent_output")
        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, f"issue-{ctx.issue_number}.md")
        self._apply_simple_rules(ctx, repo_dir)
        content = (
            f"# Issue {ctx.issue_number}\n\n"
            f"## Title\n{ctx.issue_title}\n\n"
            f"## Body\n{ctx.issue_body}\n\n"
            "## Agent Note\nLLM failed or patch not produced; fallback rules applied.\n"
        )
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def _build_pr_body(self, ctx: AgentContext, iteration: int) -> str:
        return (
            f"Implements issue #{ctx.issue_number}.\n\n"
            f"Iteration: {iteration}\n\n"
            "Agent-generated PR. Reviewer feedback will trigger another iteration if needed."
        )

    def _current_iteration(self, issue, bot_login: str) -> int:
        comments = list(issue.get_comments())
        comments.reverse()
        for comment in comments:
            if comment.user and comment.user.login == bot_login:
                match = re.search(r"Iteration:\s*(\d+)", comment.body or "")
                if match:
                    return int(match.group(1))
        return 0

    def _apply_simple_rules(self, ctx: AgentContext, repo_dir: str) -> None:
        text = f"{ctx.issue_title}\n{ctx.issue_body}".lower()
        if "hello" in text and "python" in text:
            path = os.path.join(repo_dir, "hello.py")
            with open(path, "w", encoding="utf-8") as f:
                f.write('print("Hello, world!")\n')

    def _ensure_repo(self) -> Repo:
        if os.path.isdir(os.path.join(os.getcwd(), ".git")):
            return Repo(os.getcwd())

        repo_slug = self.settings.github_repo.replace("/", "-")
        base_dir = os.path.join(tempfile.gettempdir(), "megashkola_agent", repo_slug)
        os.makedirs(base_dir, exist_ok=True)
        repo_path = os.path.join(base_dir, "workspace")
        if os.path.isdir(os.path.join(repo_path, ".git")):
            repo = Repo(repo_path)
            repo.git.fetch("origin")
            return repo

        token = self.settings.github_token
        repo_url = f"https://x-access-token:{token}@github.com/{self.settings.github_repo}.git"
        return Repo.clone_from(repo_url, repo_path)
