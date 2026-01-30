from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from github import Github
from github.Issue import Issue
from github.PullRequest import PullRequest
from github.Repository import Repository


@dataclass
class RepoHandle:
    gh: Github
    repo: Repository


def get_repo(token: str, full_name: str) -> RepoHandle:
    gh = Github(token)
    repo = gh.get_repo(full_name)
    return RepoHandle(gh=gh, repo=repo)


def find_issue_by_number(repo: Repository, number: int) -> Issue:
    return repo.get_issue(number=number)


def find_open_issues_with_label(repo: Repository, label: str) -> Iterable[Issue]:
    return repo.get_issues(state="open", labels=[label])


def find_pr_for_issue(repo: Repository, issue_number: int) -> PullRequest | None:
    # Heuristic: look for PR with branch name or title containing issue number.
    for pr in repo.get_pulls(state="open", sort="created", direction="desc"):
        if f"issue-{issue_number}" in pr.head.ref or f"#{issue_number}" in pr.title:
            return pr
    return None


def create_or_update_pr(
    repo: Repository,
    base_branch: str,
    head_branch: str,
    title: str,
    body: str,
) -> PullRequest:
    existing = None
    for pr in repo.get_pulls(state="open", head=f"{repo.owner.login}:{head_branch}"):
        existing = pr
        break
    if existing:
        existing.edit(title=title, body=body)
        return existing
    return repo.create_pull(title=title, body=body, base=base_branch, head=head_branch)


def get_latest_reviewer_comment(pr: PullRequest, bot_login: str | None) -> str | None:
    comments = list(pr.get_issue_comments())
    comments.reverse()
    for comment in comments:
        if bot_login:
            if comment.user and comment.user.login == bot_login:
                return comment.body
        else:
            if "STATUS:" in (comment.body or ""):
                return comment.body
    return None
