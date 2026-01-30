# MegaSchool Coding Agents (MVP)

This repository contains a minimal but working SDLC automation pipeline:

- **Code Agent** CLI reads GitHub Issues, creates/updates code changes, and opens/updates a PR.
- **Reviewer Agent** runs in GitHub Actions, analyzes the PR + CI results, and posts a review/comment.
- **CI/CD** runs checks and the reviewer on each PR update.
- **Iteration loop**: if reviewer requests changes, Code Agent can re-run and update the PR.

## Quick start (local, uv)

Requirements: Python 3.11+, `uv`, and a GitHub token with repo permissions.

```bash
uv venv .venv
source .venv/bin/activate
uv pip install -e .

export GITHUB_TOKEN=...            # required
export GITHUB_REPO=owner/repo      # required
export GITHUB_BASE_BRANCH=main     # optional

code-agent run-once --issue 1
```

## Docker

```bash
docker-compose up -d
```

The container runs the **poller** which periodically checks for new issues with the label `agent`. If the
container is not started inside a git repo, the agent will clone `GITHUB_REPO` into a temp workspace.

## GitHub Actions

Two workflows are included:

- `.github/workflows/code-agent.yml`: runs on Issue events **when label `agent` is present**, executes the Code Agent.
- `.github/workflows/reviewer.yml`: runs on PR events, executes CI + Reviewer Agent.

## Environment variables

- `GITHUB_TOKEN` (required)
- `GITHUB_REPO` (required, `owner/repo`)
- `GITHUB_BASE_BRANCH` (default: `main`)
- `AGENT_LABEL` (default: `agent`)
- `REVIEWER_BOT_LOGIN` (optional; if unset, agent scans latest `STATUS:` comment)
- `LLM_PROVIDER` (`openai` or `yandex`, optional)
- `LLM_API_KEY` (optional)
- `LLM_MODEL` (optional)
- `MAX_ITERATIONS` (default: `3`)
- `POLL_INTERVAL_SECONDS` (default: `300`)

If no LLM is configured, the agent falls back to a simple rule-based change that still produces a PR.

## Notes

This is an MVP intended for demonstration and extension. See `docs/REPORT.md` for the required report template.
