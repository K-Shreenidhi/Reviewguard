"""
github_utils.py — Real GitHub API integration for ReviewGuard.
Fetches PR diffs, extracts added lines, and posts review comments.
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_API = "https://api.github.com"

SKIP_EXT = {".lock", ".min.js", ".svg", ".png", ".jpg", ".jpeg", ".ico",
            ".woff", ".woff2", ".ttf", ".eot", ".gif", ".bmp", ".map"}

CODE_EXT = {".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rb", ".php",
            ".cpp", ".c", ".h", ".rs", ".swift", ".kt", ".cs", ".sh", ".yml",
            ".yaml", ".json", ".env", ".tf", ".sql", ".toml", ".cfg", ".ini",
            ".html", ".css", ".scss", ".md", ".dockerfile", ".xml"}


def _headers():
    h = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        h["Authorization"] = f"token {GITHUB_TOKEN}"
    return h


def get_pr_files(owner: str, repo: str, pr_number: int) -> list[dict]:
    """
    Fetch the list of changed files for a PR via GitHub REST API.
    Returns a list of dicts with keys: filename, patch, status, additions, etc.
    Handles pagination (GitHub returns max 30 files per page by default).
    """
    all_files = []
    page = 1

    while True:
        url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}/files"
        resp = requests.get(url, headers=_headers(), params={"per_page": 100, "page": page})

        if resp.status_code == 403 and "rate limit" in resp.text.lower():
            print("[WARN] GitHub API rate limit hit. Add a GITHUB_TOKEN to .env for higher limits.")
            break

        if resp.status_code != 200:
            print(f"[Error] GitHub API error {resp.status_code}: {resp.text[:200]}")
            break

        files = resp.json()
        if not files:
            break

        all_files.extend(files)
        page += 1

        # If we got fewer than per_page, we're done
        if len(files) < 100:
            break

    return all_files


def extract_added_lines(patch: str) -> str:
    """Extract only the added lines (lines starting with +, excluding +++ header) from a unified diff patch."""
    if not patch:
        return ""
    
    lines = []
    for line in patch.split("\n"):
        if line.startswith("+") and not line.startswith("+++"):
            lines.append(line[1:])  # strip the leading +
    
    return "\n".join(lines)


def filter_and_extract(files: list[dict]) -> list[dict]:
    """
    Given raw GitHub API file objects, filter to code files and extract added lines.
    Returns list of { filename, code } ready for analysis.
    """
    results = []

    for f in files:
        filename = f.get("filename", "")
        status = f.get("status", "")
        patch = f.get("patch", "")

        # Skip removed files
        if status == "removed":
            continue

        # Skip binary / non-code files
        ext = ""
        if "." in filename:
            ext = "." + filename.rsplit(".", 1)[-1].lower()

        if ext in SKIP_EXT:
            continue

        # Accept known code extensions, or files without extensions (scripts)
        if ext and ext not in CODE_EXT:
            continue

        # Extract added lines from the patch
        added = extract_added_lines(patch)
        if not added.strip():
            continue

        results.append({"filename": filename, "code": added})

    return results


# ── Legacy functions (used by webhook endpoint) ──────────────────────────────

def get_pr_diff(repo_full_name: str, pr_number: int) -> list[dict]:
    """Legacy wrapper: fetch PR files using owner/repo format."""
    parts = repo_full_name.split("/")
    if len(parts) != 2:
        print(f"[Error] Invalid repo name: {repo_full_name}")
        return []
    owner, repo = parts
    return get_pr_files(owner, repo, pr_number)


def post_pr_comment(repo_full_name: str, pr_number: int, comment_body: str):
    """Post a comment on a GitHub PR."""
    if not GITHUB_TOKEN:
        print("[WARN] No GITHUB_TOKEN set — skipping comment post")
        print(f"\n--- COMMENT FOR PR #{pr_number} ---")
        print(comment_body[:500])
        print("--------------------------------------------------\n")
        return

    url = f"{GITHUB_API}/repos/{repo_full_name}/issues/{pr_number}/comments"
    resp = requests.post(url, headers=_headers(), json={"body": comment_body})

    if resp.status_code == 201:
        print(f"[Success] Comment posted on PR #{pr_number}")
    else:
        print(f"[Error] Failed to post comment: {resp.status_code} — {resp.text[:200]}")
