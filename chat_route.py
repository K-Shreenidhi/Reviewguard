# ── ADD THIS TO YOUR main.py ─────────────────────────────────────────────────
# Drop this block right after your existing /analyze endpoint

from pydantic import BaseModel
from typing import Optional, List, Any

class ChatContext(BaseModel):
    files: Optional[List[Any]] = []
    risks: Optional[List[Any]] = []
    pr_url: Optional[str] = ""

class ChatRequest(BaseModel):
    question: str
    context: Optional[ChatContext] = None


@app.post("/chat")
async def chat_with_pr(request: ChatRequest):
    """
    AI chatbot endpoint — answers questions about the current PR
    using the cached analysis context from the extension.
    """

    # Build a rich context string from the analysis data
    ctx_parts = []

    if request.context and request.context.files:
        ctx_parts.append("=== PR ANALYSIS CONTEXT ===\n")

        for f in request.context.files:
            # Handle both dict and object
            fname    = f.get("filename", "unknown") if isinstance(f, dict) else getattr(f, "filename", "unknown")
            score    = f.get("risk_score", "?")     if isinstance(f, dict) else getattr(f, "risk_score", "?")
            expl     = f.get("explanation", "")     if isinstance(f, dict) else getattr(f, "explanation", "")
            is_ai    = f.get("is_ai_generated", False) if isinstance(f, dict) else getattr(f, "is_ai_generated", False)
            suggest  = f.get("suggestion", "")      if isinstance(f, dict) else getattr(f, "suggestion", "")
            risks_l  = f.get("risk_reasons", [])    if isinstance(f, dict) else getattr(f, "risk_reasons", [])
            line_risks = f.get("risks", [])          if isinstance(f, dict) else getattr(f, "risks", [])

            ctx_parts.append(f"File: {fname}")
            ctx_parts.append(f"  Risk score: {score}/10")
            ctx_parts.append(f"  AI-generated: {is_ai}")
            ctx_parts.append(f"  Summary: {expl}")
            if risks_l:
                ctx_parts.append(f"  Risk reasons: {'; '.join(risks_l)}")
            if line_risks:
                for lr in line_risks:
                    lnum   = lr.get("line", "?")    if isinstance(lr, dict) else getattr(lr, "line", "?")
                    lsev   = lr.get("severity", "") if isinstance(lr, dict) else getattr(lr, "severity", "")
                    lrsn   = lr.get("reason", "")   if isinstance(lr, dict) else getattr(lr, "reason", "")
                    lsugg  = lr.get("suggestion","") if isinstance(lr, dict) else getattr(lr, "suggestion","")
                    ctx_parts.append(f"  Line {lnum} [{lsev}]: {lrsn} → {lsugg}")
            ctx_parts.append(f"  Suggestion: {suggest}\n")

    if request.context and request.context.pr_url:
        ctx_parts.append(f"PR URL: {request.context.pr_url}")

    context_text = "\n".join(ctx_parts) if ctx_parts else "No prior analysis available."

    prompt = f"""You are ReviewGuard AI, an expert code security and quality assistant embedded in a GitHub PR review tool.

{context_text}

The developer is asking:
"{request.question}"

Instructions:
- Answer concisely and specifically (3-6 sentences max unless a fix is requested)
- Reference specific files and line numbers from the context when relevant
- If asked for a fix, provide actual code
- If asked "safe to merge", give a clear YES/NO/CONDITIONAL with brief reasoning
- Use plain text (no markdown headers, keep formatting minimal)
- Be direct and developer-friendly, not corporate

Answer:"""

    try:
        response = model.generate_content(prompt)
        answer = response.text.strip()
        # Clean up any markdown artifacts
        answer = answer.replace("**", "").replace("##", "").replace("# ", "")
        return {"answer": answer}

    except Exception as e:
        print(f"Chat error: {e}")
        return {"answer": f"Sorry, I encountered an error: {str(e)}. Please try again."}
