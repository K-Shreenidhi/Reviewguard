import hmac
import hashlib
import json
import os
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from ai_engine import analyze_code_block, format_comment
from github_utils import get_pr_files, get_pr_diff, extract_added_lines, filter_and_extract, post_pr_comment

load_dotenv()

app = FastAPI(
    title="ReviewGuard",
    description="AI-powered code review using Google Gemini",
    version="1.0.0"
)

# Allow Chrome extension/Frontend to call this server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        
    allow_methods=["*"],
    allow_headers=["*"],
)

WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "")

# ── Models ───────────────────────────────────────────────────────────────────
class FileInput(BaseModel):
    filename: str
    code: str

class AnalyzeRequest(BaseModel):
    files: list[FileInput]

class AnalyzePRRequest(BaseModel):
    owner: str
    repo: str
    pr_number: int

# ── Webhook signature verification ───────────────────────────────────────────
def verify_github_signature(payload_body: bytes, signature_header: str) -> bool:
    if not WEBHOOK_SECRET or not signature_header:
        return True  # Skip verification in dev mode

    hash_object = hmac.new(
        WEBHOOK_SECRET.encode("utf-8"),
        msg=payload_body,
        digestmod=hashlib.sha256
    )
    expected = "sha256=" + hash_object.hexdigest()
    return hmac.compare_digest(expected, signature_header)

# ── Health check ─────────────────────────────────────────────────────────────
@app.get("/")
async def health_check():
    return {
        "status": "ReviewGuard is running",
        "llm": "Google Gemini 2.5 Flash Lite",
        "version": "1.0.0"
    }

# ── Direct analysis endpoint (used by Frontend for raw code) ──────────────────
@app.post("/analyze")
def analyze_direct(request: AnalyzeRequest):
    if not request.files:
        return {"summary": {"total_files": 0, "high_risk_count": 0, "ai_detected_count": 0}, "files": []}

    print(f"\n[Analyze] Direct analysis request: {len(request.files)} file(s)")

    results      = []
    high_risk    = 0
    ai_detected  = 0

    for file in request.files:
        if not file.code.strip():
            continue

        print(f"   Analyzing {file.filename}...")
        analysis              = analyze_code_block(file.code, file.filename)
        analysis["filename"]  = file.filename

        if analysis["risk_score"] >= 7:
            high_risk += 1
        if analysis["is_ai_generated"]:
            ai_detected += 1

        results.append(analysis)

    print(f"   Done. {high_risk} high-risk, {ai_detected} AI-detected.")

    return {
        "summary": {
            "total_files":       len(results),
            "high_risk_count":   high_risk,
            "ai_detected_count": ai_detected
        },
        "files": results
    }

# ── NEW: PR analysis via GitHub API ──────────────────────────────────────────
@app.post("/analyze-pr")
def analyze_pr(request: AnalyzePRRequest):
    """
    Fetch diff from GitHub API, extract added lines, and analyze each file.
    This is the primary endpoint used by the Chrome extension.
    """
    print(f"\n[Analyze PR] request: {request.owner}/{request.repo} PR #{request.pr_number}")

    # 1. Fetch files from GitHub API
    raw_files = get_pr_files(request.owner, request.repo, request.pr_number)

    if not raw_files:
        return {
            "summary": {"total_files": 0, "high_risk_count": 0, "ai_detected_count": 0},
            "files": [],
            "error": "Could not fetch PR files from GitHub. Check the PR URL and ensure GITHUB_TOKEN is set for private repos."
        }

    print(f"   Fetched {len(raw_files)} file(s) from GitHub API")

    # 2. Filter to code files and extract added lines
    code_files = filter_and_extract(raw_files)
    print(f"   {len(code_files)} code file(s) with additions to analyze")

    if not code_files:
        return {
            "summary": {"total_files": 0, "high_risk_count": 0, "ai_detected_count": 0},
            "files": []
        }

    # 3. Analyze each file with Gemini
    results      = []
    high_risk    = 0
    ai_detected  = 0

    for file in code_files:
        print(f"   Analyzing {file['filename']}...")
        analysis              = analyze_code_block(file["code"], file["filename"])
        analysis["filename"]  = file["filename"]

        if analysis["risk_score"] >= 7:
            high_risk += 1
        if analysis["is_ai_generated"]:
            ai_detected += 1

        results.append(analysis)

    print(f"   [Done] {high_risk} high-risk, {ai_detected} AI-detected out of {len(results)} files.")

    return {
        "summary": {
            "total_files":       len(results),
            "high_risk_count":   high_risk,
            "ai_detected_count": ai_detected
        },
        "files": results
    }

# ── GitHub Webhook ────────────────────────────────────────────────────────────
@app.post("/webhook")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    payload_body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    if not verify_github_signature(payload_body, signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    event_type = request.headers.get("X-GitHub-Event", "")
    payload = json.loads(payload_body)

    if event_type != "pull_request":
        return {"status": "ignored", "reason": f"Event type '{event_type}' not handled"}

    action = payload.get("action", "")
    if action not in ["opened", "synchronize"]:
        return {"status": "ignored", "reason": f"Action '{action}' not handled"}

    pr_number  = payload["pull_request"]["number"]
    repo_name  = payload["repository"]["full_name"]
    pr_title   = payload["pull_request"]["title"]
    pr_author  = payload["pull_request"]["user"]["login"]

    print(f"\n[Webhook] PR #{pr_number} {action} by @{pr_author}: '{pr_title}'")
    background_tasks.add_task(run_pr_analysis, repo_name, pr_number)
    return {"status": "analysis started", "pr": pr_number}

# ── Core PR analysis pipeline ─────────────────────────────────────────────────
def run_pr_analysis(repo_full_name: str, pr_number: int):
    print(f"\n[Start] analysis: {repo_full_name} PR #{pr_number}")
    try:
        changed_files = get_pr_diff(repo_full_name, pr_number)
        if not changed_files: return
        
        all_comments, high_risk_count, ai_count = [], 0, 0

        for file in changed_files:
            added_code = extract_added_lines(file.get("patch", ""))
            if not added_code.strip(): continue

            analysis     = analyze_code_block(added_code, file["filename"])
            comment_body = format_comment(analysis, file["filename"])
            all_comments.append(comment_body)

            if analysis["risk_score"] >= 7: high_risk_count += 1
            if analysis["is_ai_generated"]: ai_count += 1

        if not all_comments: return

        summary = build_summary_comment(len(all_comments), ai_count, high_risk_count)
        full_comment = summary + "\n\n---\n\n" + "\n\n---\n\n".join(all_comments)
        post_pr_comment(repo_full_name, pr_number, full_comment)
        print(f"[Success] Analysis complete for PR #{pr_number}")

    except Exception as e:
        print(f"[Failed] Analysis failed for PR #{pr_number}: {e}")
        post_pr_comment(repo_full_name, pr_number, f"⚠️ **ReviewGuard**: Analysis failed — `{str(e)}`\nPlease review this PR manually.")

# ── Summary card builder ──────────────────────────────────────────────────────
def build_summary_comment(total: int, ai: int, risky: int) -> str:
    ai_pct = int((ai / total) * 100) if total > 0 else 0
    overall_status = f"⚠️ {risky} high-risk file(s) detected — review carefully" if risky > 0 else "✅ No high-risk files found"
    return f"""# 🛡️ ReviewGuard Report
> *Powered by Google Gemini*

| Metric | Value |
|--------|-------|
| 📁 Files analyzed | {total} |
| 🤖 AI-generated | {ai} ({ai_pct}%) |
| 🔴 High risk | {risky} |
| 📊 Overall | {overall_status} |

*Detailed breakdown per file below ↓*"""