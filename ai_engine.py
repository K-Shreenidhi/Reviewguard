import os
import re
import json
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai import errors as genai_errors

load_dotenv()

# Initialize the GenAI client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Models to try in order — if one is rate-limited, try the next
MODEL_CHAIN = [
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
]

MAX_RETRIES = 3          # retries per model
BASE_RETRY_DELAY = 5     # seconds, used if API doesn't tell us how long to wait


def _extract_retry_delay(error_msg: str) -> float:
    """Parse 'retryDelay' or 'Please retry in Xs' from the API error message."""
    m = re.search(r"retry in ([\d.]+)s", str(error_msg))
    if m:
        return min(float(m.group(1)), 60.0)   # cap at 60s
    return BASE_RETRY_DELAY


def _call_gemini(prompt: str, model: str) -> tuple:
    """Single Gemini API call — returns (parsed JSON dict or None, raw text)."""
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.2,
            response_mime_type="application/json",
        ),
    )

    try:
        result = json.loads(response.text)
        return result, response.text
    except json.JSONDecodeError:
        return None, response.text


def analyze_code_block(code: str, filename: str) -> dict:
    prompt = f"""You are ReviewGuard, an expert AI code review assistant.
Analyze the following code from file: {filename}

{code}

You must respond in this exact JSON format only:
{{
  "is_ai_generated": true or false,
  "ai_confidence": "high" or "medium" or "low",
  "explanation": "Plain English explanation of what this code does (2-3 sentences max)",
  "risk_score": <integer from 1 to 10, where 10 is extremely risky>,
  "risk_reasons": [
    "Specific risk reason 1",
    "Specific risk reason 2"
  ],
  "suggestion": "One concrete, actionable improvement suggestion"
}}

Scoring guide for risk_score:
- 1-3: Clean, safe, well-written code
- 4-6: Minor issues, worth noting
- 7-9: Significant issues, needs attention
- 10: Critical issue, do not merge"""

    last_error = None

    for model in MODEL_CHAIN:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                print(f"   -> Trying {model} (attempt {attempt}/{MAX_RETRIES})...")
                result, raw_text = _call_gemini(prompt, model)
                
                if result is not None:
                    print(f"   [OK] Success with {model}")
                    return result
                
                # Model returned text but it wasn't clean JSON — try to salvage
                try:
                    raw = raw_text.strip()
                    if "```" in raw:
                        raw = raw.split("```")[1]
                        if raw.startswith("json"):
                            raw = raw[4:]
                    salvaged_result = json.loads(raw.strip())
                    print(f"   [OK] Success with {model} (salvaged JSON)")
                    return salvaged_result
                except Exception:
                    last_error = "Gemini returned malformed JSON"
                    break  # move to next model

            except genai_errors.ClientError as e:
                last_error = e
                error_str = str(e)

                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    delay = _extract_retry_delay(error_str)
                    if delay > 10:
                        print(f"   [WARN] Rate-limit on {model} requires {delay:.0f}s wait. Skipping to next model instead.")
                        break  # skip to next model immediately to avoid hanging the server
                    print(f"   [WAIT] Rate-limited on {model}. Waiting {delay:.0f}s before retry...")
                    time.sleep(delay)
                    continue   # retry same model
                else:
                    print(f"   [ERR] Client error on {model}: {e}")
                    break  # non-rate-limit error → skip to next model

            except Exception as e:
                last_error = e
                print(f"   [ERR] Unexpected error on {model}: {e}")
                break  # skip to next model

        # If we exhausted retries for this model, move to next
        print(f"   [WARN] Exhausted retries for {model}, trying next model...")

    # All models failed
    error_msg = str(last_error) if last_error else "Unknown error"

    if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
        reason = "API rate limit exceeded — too many requests. Please wait a minute and try again."
        suggestion = "Wait 1-2 minutes, then re-analyze. Or upgrade to a paid Gemini API plan for higher limits."
    elif "API_KEY" in error_msg or "401" in error_msg or "403" in error_msg:
        reason = "Invalid or expired GEMINI_API_KEY. Check your .env file."
        suggestion = "Get a new API key at https://aistudio.google.com/apikey"
    else:
        reason = f"API error: {error_msg[:120]}"
        suggestion = "Check server logs and try again."

    print(f"   [FAIL] All models failed: {reason}")
    return {
        "is_ai_generated": False,
        "ai_confidence": "low",
        "explanation": "Analysis failed for this file.",
        "risk_score": 0,
        "risk_reasons": [reason],
        "suggestion": suggestion,
    }

def format_comment(analysis: dict, filename: str) -> str:
    score = analysis["risk_score"]

    if score == 0: risk_emoji, risk_label = "⚪", "Unanalyzed"
    elif score <= 3: risk_emoji, risk_label = "🟢", "Low Risk"
    elif score <= 6: risk_emoji, risk_label = "🟡", "Medium Risk"
    else: risk_emoji, risk_label = "🔴", "High Risk"

    ai_badge = f"🤖 AI-Generated ({analysis['ai_confidence']} confidence)" if analysis["is_ai_generated"] else "👤 Human-written"
    reasons_text = "\n".join(f"- {r}" for r in analysis["risk_reasons"])

    return f"""## 🔍 ReviewGuard — `{filename}`

| | |
|---|---|
| **Origin** | {ai_badge} |
| **Risk Score** | {risk_emoji} {score}/10 — {risk_label} |

### 📖 What this code does
{analysis['explanation']}

### ⚠️ Risk Factors
{reasons_text}

### 💡 Suggestion
{analysis['suggestion']}

---
*Powered by ReviewGuard*"""

# ── Quick test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    test_code = """
def login(username, password):
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    result = db.execute(query)
    if result:
        return {"token": "hardcoded_secret_token_123", "user": result[0]}
    return None
"""
    print("Testing new Gemini 2.5 connection...\n")
    result = analyze_code_block(test_code, "auth.py")
    print("Raw analysis:", json.dumps(result, indent=2))
    print("\n--- FORMATTED COMMENT ---\n")
    print(format_comment(result, "auth.py"))
