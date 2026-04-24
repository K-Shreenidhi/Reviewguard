// ============================================================
// ReviewGuard -- content.js (GitHub API approach)
// No DOM scraping. Extracts owner/repo/PR from URL,
// sends to backend which fetches diff via GitHub API.
// ============================================================

console.log("[ReviewGuard] loaded");

if (window._rgInjected) { /* already running */ }
else {
window._rgInjected = true;

const BACKEND_URL = "https://foyer-showpiece-magician.ngrok-free.dev";

// -- CSS ---------------------------------------------------
function injectStyles() {
  if (document.getElementById("rg-styles")) return;
  const s = document.createElement("style");
  s.id = "rg-styles";
  s.textContent = `
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=DM+Sans:wght@400;500;600;700&display=swap');
    :root {
      --rg-bg0:#040810;--rg-bg1:#0a0f1a;--rg-bg2:#0d1420;
      --rg-bg3:#111827;--rg-bg4:#1a2235;
      --rg-border:#1e2d45;--rg-border2:#243348;
      --rg-text1:#e8f0fe;--rg-text2:#8da4c4;--rg-text3:#4d6080;
      --rg-red:#ff3b5c;--rg-yellow:#f5c842;
      --rg-green:#00e5a0;--rg-blue:#4f9cf9;--rg-purple:#a78bfa;
    }
    #rg-panel{position:fixed;top:0;right:0;width:380px;height:100vh;background:var(--rg-bg1);border-left:1px solid var(--rg-border);z-index:999999;display:flex;flex-direction:column;font-family:'DM Sans',-apple-system,sans-serif;transform:translateX(100%);transition:transform .4s cubic-bezier(.16,1,.3,1);box-shadow:-8px 0 40px rgba(0,0,0,.6);overflow:hidden}
    #rg-panel.rg-open{transform:translateX(0)}
    #rg-panel::before{content:'';position:absolute;left:0;right:0;height:1px;background:linear-gradient(90deg,transparent,var(--rg-blue),transparent);animation:rg-scan 3s ease-in-out infinite;opacity:.4;z-index:1;top:0}
    @keyframes rg-scan{0%{top:0;opacity:.4}50%{opacity:.7}100%{top:100%;opacity:.4}}
    .rg-header{padding:14px 16px 12px;border-bottom:1px solid var(--rg-border);background:linear-gradient(180deg,var(--rg-bg2),var(--rg-bg1));flex-shrink:0;position:relative}
    .rg-header::after{content:'';position:absolute;bottom:0;left:0;right:0;height:1px;background:linear-gradient(90deg,transparent,var(--rg-blue) 50%,transparent);opacity:.3}
    .rg-toprow{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px}
    .rg-brand{display:flex;align-items:center;gap:8px}
    .rg-icon{width:28px;height:28px;border-radius:6px;background:linear-gradient(135deg,#1a2a4a,#0d1a30);border:1px solid var(--rg-blue);display:flex;align-items:center;justify-content:center;font-size:14px;box-shadow:0 0 10px rgba(79,156,249,.25);color:white;}
    .rg-title{font-size:14px;font-weight:700;color:var(--rg-text1);letter-spacing:-.3px}
    .rg-subtitle{font-size:10px;color:var(--rg-blue);letter-spacing:.5px;text-transform:uppercase;font-family:'IBM Plex Mono',monospace}
    .rg-close-btn{width:26px;height:26px;background:transparent;border:1px solid var(--rg-border2);border-radius:6px;cursor:pointer;color:var(--rg-text3);font-size:14px;display:flex;align-items:center;justify-content:center;transition:all .2s;line-height:1}
    .rg-close-btn:hover{background:var(--rg-bg4);color:var(--rg-text1);border-color:var(--rg-text3)}
    .rg-stats{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px}
    .rg-stat{background:var(--rg-bg3);border:1px solid var(--rg-border);border-radius:8px;padding:8px 6px;text-align:center;position:relative;overflow:hidden;transition:transform .2s}
    .rg-stat:hover{transform:translateY(-1px)}
    .rg-stat::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;border-radius:2px 2px 0 0}
    .rg-stat.s-red::before{background:linear-gradient(90deg,transparent,var(--rg-red),transparent)}
    .rg-stat.s-yellow::before{background:linear-gradient(90deg,transparent,var(--rg-yellow),transparent)}
    .rg-stat.s-blue::before{background:linear-gradient(90deg,transparent,var(--rg-blue),transparent)}
    .rg-stat-n{display:block;font-size:20px;font-weight:700;font-family:'IBM Plex Mono',monospace;line-height:1.2}
    .rg-stat.s-red .rg-stat-n{color:var(--rg-red)}
    .rg-stat.s-yellow .rg-stat-n{color:var(--rg-yellow)}
    .rg-stat.s-blue .rg-stat-n{color:var(--rg-blue)}
    .rg-stat-l{font-size:9px;color:var(--rg-text3);text-transform:uppercase;letter-spacing:.5px;font-family:'IBM Plex Mono',monospace;margin-top:2px}
    .rg-statusbar{padding:7px 16px;background:var(--rg-bg2);border-bottom:1px solid var(--rg-border);display:flex;align-items:center;gap:8px;flex-shrink:0}
    .rg-dot{width:6px;height:6px;border-radius:50%;flex-shrink:0}
    .rg-dot.d-loading{background:var(--rg-blue);box-shadow:0 0 6px var(--rg-blue);animation:rg-blink 1s ease-in-out infinite}
    .rg-dot.d-done{background:var(--rg-green);box-shadow:0 0 6px var(--rg-green);animation:rg-blink 2s ease-in-out infinite}
    .rg-dot.d-err{background:var(--rg-red);box-shadow:0 0 6px var(--rg-red)}
    @keyframes rg-blink{0%,100%{opacity:1}50%{opacity:.35}}
    .rg-status-txt{font-size:11px;color:var(--rg-text2);font-family:'IBM Plex Mono',monospace}
    .rg-status-time{margin-left:auto;font-size:10px;color:var(--rg-text3);font-family:'IBM Plex Mono',monospace}
    .rg-body{flex:1;overflow-y:auto;padding:12px;display:flex;flex-direction:column;gap:10px;scrollbar-width:thin;scrollbar-color:var(--rg-border2) transparent}
    .rg-body::-webkit-scrollbar{width:4px}
    .rg-body::-webkit-scrollbar-thumb{background:var(--rg-border2);border-radius:2px}
    .rg-section-lbl{font-size:9px;font-weight:600;text-transform:uppercase;letter-spacing:1px;color:var(--rg-text3);font-family:'IBM Plex Mono',monospace;padding:0 2px;margin-bottom:-4px}
    .rg-shimmer-card{background:var(--rg-bg2);border:1px solid var(--rg-border);border-radius:10px;padding:12px;display:flex;flex-direction:column;gap:8px}
    .rg-shimmer{border-radius:4px;background:linear-gradient(90deg,var(--rg-bg3) 25%,var(--rg-bg4) 50%,var(--rg-bg3) 75%);background-size:200% 100%;animation:rg-shim 1.5s ease-in-out infinite}
    @keyframes rg-shim{0%{background-position:200% 0}100%{background-position:-200% 0}}
    .rg-card{background:var(--rg-bg2);border:1px solid var(--rg-border);border-radius:10px;overflow:hidden;cursor:pointer;opacity:0;transform:translateX(14px);transition:opacity .35s ease,transform .35s ease,border-color .25s,box-shadow .25s}
    .rg-card.rg-vis{opacity:1;transform:translateX(0)}
    .rg-card:hover{border-color:var(--rg-border2);transform:translateY(-1px)!important;box-shadow:0 4px 20px rgba(0,0,0,.35)}
    .rg-card.c-high{border-color:rgba(255,59,92,.3);box-shadow:0 0 0 1px rgba(255,59,92,.1)}
    .rg-card.c-high:hover{border-color:rgba(255,59,92,.55);box-shadow:0 0 18px rgba(255,59,92,.15),0 4px 20px rgba(0,0,0,.3)}
    .rg-card.c-med{border-color:rgba(245,200,66,.25)}
    .rg-card.c-med:hover{border-color:rgba(245,200,66,.5);box-shadow:0 0 18px rgba(245,200,66,.1),0 4px 20px rgba(0,0,0,.3)}
    .rg-card-hdr{padding:9px 12px;display:flex;align-items:center;gap:8px;border-bottom:1px solid var(--rg-border);background:var(--rg-bg3)}
    .rg-file-ext{font-size:10px;width:22px;height:22px;background:var(--rg-bg4);border-radius:4px;display:flex;align-items:center;justify-content:center;flex-shrink:0;font-family:'IBM Plex Mono',monospace;color:var(--rg-text2)}
    .rg-fname{flex:1;font-family:'IBM Plex Mono',monospace;font-size:12px;color:var(--rg-text1);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    .rg-badge{font-size:11px;font-weight:700;padding:2px 7px;border-radius:6px;font-family:'IBM Plex Mono',monospace;flex-shrink:0}
    .b-high{background:rgba(255,59,92,.15);color:var(--rg-red);border:1px solid rgba(255,59,92,.3)}
    .b-med{background:rgba(245,200,66,.12);color:var(--rg-yellow);border:1px solid rgba(245,200,66,.25)}
    .b-low{background:rgba(0,229,160,.1);color:var(--rg-green);border:1px solid rgba(0,229,160,.2)}
    .rg-card-body{padding:10px 12px;display:flex;flex-direction:column;gap:8px}
    .rg-ai-row{display:flex;align-items:center;gap:6px}
    .rg-ai-pill{font-size:10px;font-family:'IBM Plex Mono',monospace;padding:2px 8px;border-radius:10px;font-weight:500}
    .p-ai{background:rgba(167,139,250,.12);color:var(--rg-purple);border:1px solid rgba(167,139,250,.25)}
    .p-hum{background:rgba(0,229,160,.08);color:var(--rg-green);border:1px solid rgba(0,229,160,.18)}
    .rg-conf{font-size:10px;color:var(--rg-text3);font-family:'IBM Plex Mono',monospace}
    .rg-expl{font-size:12px;color:var(--rg-text2);line-height:1.6;border-left:2px solid var(--rg-border2);padding-left:8px}
    .rg-risks{display:flex;flex-direction:column;gap:4px}
    .rg-risk-row{display:flex;align-items:flex-start;gap:6px;font-size:11px;color:var(--rg-text2);line-height:1.5}
    .rg-risk-dot{width:4px;height:4px;border-radius:50%;background:var(--rg-red);margin-top:6px;flex-shrink:0}
    .rg-risk-dot.med{background:var(--rg-yellow)}
    .rg-suggest{background:rgba(0,229,160,.05);border:1px solid rgba(0,229,160,.15);border-radius:7px;padding:8px 10px;font-size:11px;color:rgba(0,229,160,.9);line-height:1.5;display:flex;gap:6px;align-items:flex-start}
    .rg-footer{padding:9px 16px;border-top:1px solid var(--rg-border);display:flex;align-items:center;justify-content:space-between;flex-shrink:0;background:var(--rg-bg2)}
    .rg-footer-txt{font-size:10px;color:var(--rg-text3);font-family:'IBM Plex Mono',monospace}
    .rg-gemini{font-size:9px;padding:2px 8px;border-radius:8px;background:rgba(79,156,249,.08);border:1px solid rgba(79,156,249,.2);color:var(--rg-blue);font-family:'IBM Plex Mono',monospace}
    #rg-trigger-btn{position:fixed;bottom:28px;right:28px;z-index:999998;background:linear-gradient(135deg,#1a2a4a,#0d1a30);border:1px solid #4f9cf9;color:#4f9cf9;font-family:'IBM Plex Mono',monospace;font-size:12px;font-weight:600;padding:9px 18px;border-radius:20px;cursor:pointer;box-shadow:0 0 20px rgba(79,156,249,.25);transition:all .2s ease;letter-spacing:.3px}
    #rg-trigger-btn:hover{background:rgba(79,156,249,.12);box-shadow:0 0 30px rgba(79,156,249,.4);transform:translateY(-1px)}
    #rg-trigger-btn.active{border-color:var(--rg-red);color:var(--rg-red);box-shadow:0 0 20px rgba(255,59,92,.2)}
  `;
  document.head.appendChild(s);
}

// -- PANEL HTML --------------------------------------------
function buildPanelHTML() {
  return `
    <div class="rg-header">
      <div class="rg-toprow">
        <div class="rg-brand">
          <div class="rg-icon">RG</div>
          <div>
            <div class="rg-title">ReviewGuard</div>
            <div class="rg-subtitle">AI Code Analysis</div>
          </div>
        </div>
        <button class="rg-close-btn" id="rg-close">X</button>
      </div>
      <div class="rg-stats">
        <div class="rg-stat s-red"><span class="rg-stat-n" id="rg-s-risk">--</span><div class="rg-stat-l">High Risk</div></div>
        <div class="rg-stat s-yellow"><span class="rg-stat-n" id="rg-s-ai">--</span><div class="rg-stat-l">AI Code</div></div>
        <div class="rg-stat s-blue"><span class="rg-stat-n" id="rg-s-files">--</span><div class="rg-stat-l">Files</div></div>
      </div>
    </div>
    <div class="rg-statusbar">
      <div class="rg-dot d-loading" id="rg-dot"></div>
      <span class="rg-status-txt" id="rg-status-txt">Scanning diff...</span>
      <span class="rg-status-time" id="rg-status-time"></span>
    </div>
    <div class="rg-body" id="rg-body">${shimmerHTML()}</div>
    <div class="rg-footer">
      <span class="rg-footer-txt">reviewguard v1.0</span>
      <span class="rg-gemini">* Gemini 2.0 Flash</span>
    </div>`;
}

function shimmerHTML() {
  return [80,65,50].map(w => `
    <div class="rg-shimmer-card">
      <div class="rg-shimmer" style="width:${w}%;height:14px"></div>
      <div class="rg-shimmer" style="width:90%;height:10px"></div>
      <div class="rg-shimmer" style="width:55%;height:8px"></div>
    </div>`).join("");
}

// -- PANEL LIFECYCLE ---------------------------------------
function ensurePanel() {
  let panel = document.getElementById("rg-panel");
  if (!panel) {
    panel = document.createElement("div");
    panel.id = "rg-panel";
    panel.innerHTML = buildPanelHTML();
    document.body.appendChild(panel);
    document.getElementById("rg-close").onclick = () => {
      panel.classList.remove("rg-open");
      const btn = document.getElementById("rg-trigger-btn");
      if (btn) { btn.textContent = "Analyze PR"; btn.classList.remove("active"); }
    };
  }
  return panel;
}

function openPanel() {
  const panel = ensurePanel();
  document.getElementById("rg-body").innerHTML = shimmerHTML();
  document.getElementById("rg-s-risk").textContent  = "--";
  document.getElementById("rg-s-ai").textContent    = "--";
  document.getElementById("rg-s-files").textContent = "--";
  document.getElementById("rg-dot").className       = "rg-dot d-loading";
  document.getElementById("rg-status-txt").textContent  = "Fetching PR diff via GitHub API...";
  document.getElementById("rg-status-time").textContent = "";
  requestAnimationFrame(() => panel.classList.add("rg-open"));
}

// -- ANIMATED COUNTER --------------------------------------
function animCount(el, to, suffix = "", ms = 700) {
  let start = null;
  const tick = (t) => {
    if (!start) start = t;
    const p = Math.min((t - start) / ms, 1);
    const ease = 1 - Math.pow(1 - p, 3);
    el.textContent = Math.round(to * ease) + suffix;
    if (p < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

// -- EXTRACT PR INFO FROM URL ------------------------------
function extractPRInfo() {
  const m = window.location.pathname.match(/^\/([^/]+)\/([^/]+)\/pull\/(\d+)/);
  if (!m) return null;
  return { owner: m[1], repo: m[2], pr_number: parseInt(m[3], 10) };
}

// -- RENDER RESULTS ----------------------------------------
async function renderResults(data, elapsedSec) {
  const { summary, files } = data;
  document.getElementById("rg-dot").className = "rg-dot d-done";
  document.getElementById("rg-status-txt").textContent = "Analysis complete";
  document.getElementById("rg-status-time").textContent = `${elapsedSec}s`;

  await sleep(150);
  animCount(document.getElementById("rg-s-risk"), summary.high_risk_count, "");
  await sleep(80);
  const aiPct = files.length ? Math.round((summary.ai_detected_count / summary.total_files) * 100) : 0;
  animCount(document.getElementById("rg-s-ai"), aiPct, "%");
  await sleep(80);
  animCount(document.getElementById("rg-s-files"), summary.total_files, "");

  await sleep(350);
  const body = document.getElementById("rg-body");
  if (!body) return;
  body.innerHTML = "";

  if (files.length === 0) {
    body.innerHTML = `<div style="padding:20px;text-align:center;color:var(--rg-text3);font-size:12px">
      No analyzable code additions found in this PR.</div>`;
    return;
  }

  const lbl = document.createElement("div");
  lbl.className = "rg-section-lbl";
  lbl.textContent = "File Analysis";
  body.appendChild(lbl);

  for (const file of files) {
    const card = buildCard(file);
    body.appendChild(card);
    await sleep(50);
    card.classList.add("rg-vis");
    await sleep(110);
  }
}

function buildCard(f) {
  const scoreClass = f.risk_score >= 7 ? "b-high" : f.risk_score >= 4 ? "b-med" : "b-low";
  const cardClass  = f.risk_score >= 7 ? "c-high" : f.risk_score >= 4 ? "c-med" : "c-low";
  const ext        = f.filename.split(".").pop() || "?";
  const aiClass    = f.is_ai_generated ? "p-ai" : "p-hum";
  const aiLabel    = f.is_ai_generated ? "AI-Generated" : "Human-written";
  const dotClass   = f.risk_score >= 7 ? "" : "med";

  const risksHTML  = (f.risk_reasons || []).map(r => `
    <div class="rg-risk-row">
      <div class="rg-risk-dot ${dotClass}"></div>
      <span>${r}</span>
    </div>`).join("");

  const card = document.createElement("div");
  card.className = `rg-card ${cardClass}`;
  card.innerHTML = `
    <div class="rg-card-hdr">
      <div class="rg-file-ext">${ext}</div>
      <span class="rg-fname">${f.filename}</span>
      <span class="rg-badge ${scoreClass}">${f.risk_score}/10</span>
    </div>
    <div class="rg-card-body">
      <div class="rg-ai-row">
        <span class="rg-ai-pill ${aiClass}">${aiLabel}</span>
        <span class="rg-conf">conf: ${f.ai_confidence}</span>
      </div>
      <div class="rg-expl">${f.explanation}</div>
      ${risksHTML ? `<div class="rg-risks">${risksHTML}</div>` : ""}
      <div class="rg-suggest"><span style="flex-shrink:0">[!]</span><span>${f.suggestion}</span></div>
    </div>`;
  return card;
}

function renderError(msg) {
  const body = document.getElementById("rg-body");
  if (!body) return;
  body.innerHTML = `
    <div style="padding:16px;text-align:center">
      <div style="color:var(--rg-red);font-size:13px;margin-bottom:6px">Analysis failed</div>
      <div style="color:var(--rg-text3);font-size:11px;font-family:'IBM Plex Mono',monospace;line-height:1.6">${msg}</div>
      <div style="color:var(--rg-text3);font-size:11px;margin-top:8px">
        Make sure your ReviewGuard server is running:<br>
        <code style="color:var(--rg-blue)">uvicorn main:app --reload</code>
      </div>
    </div>`;
  const dot = document.getElementById("rg-dot");
  if (dot) dot.className = "rg-dot d-err";
  const st = document.getElementById("rg-status-txt");
  if (st) st.textContent = "Error";
}

// -- MAIN ANALYSIS FLOW (GitHub API) -----------------------
async function runAnalysis() {
  console.log("[ReviewGuard] Starting analysis via GitHub API...");
  openPanel();

  const t0 = performance.now();

  try {
    const prInfo = extractPRInfo();
    if (!prInfo) {
      throw new Error("Not on a GitHub PR page. Navigate to a pull request.");
    }

    console.log(`[ReviewGuard] PR detected: ${prInfo.owner}/${prInfo.repo}#${prInfo.pr_number}`);
    document.getElementById("rg-status-txt").textContent = `Analyzing ${prInfo.owner}/${prInfo.repo}#${prInfo.pr_number}...`;

    const res = await fetch(`${BACKEND_URL}/analyze-pr`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(prInfo)
    });

    if (!res.ok) throw new Error(`Server returned HTTP ${res.status}`);

    const data = await res.json();
    const elapsed = ((performance.now() - t0) / 1000).toFixed(1);

    if (data.error) {
      console.warn("[ReviewGuard] Backend warning:", data.error);
    }

    console.log("[ReviewGuard] Response:", data);
    await renderResults(data, elapsed);

  } catch (err) {
    console.error("[ReviewGuard] Error:", err);
    renderError(err.message);
  }
}

// -- HELPERS -----------------------------------------------
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

// -- TRIGGER BUTTON ----------------------------------------
function injectTriggerBtn() {
  if (document.getElementById("rg-trigger-btn")) return;
  const btn = document.createElement("button");
  btn.id = "rg-trigger-btn";
  btn.textContent = "Analyze PR";
  btn.onclick = () => {
    const panel = document.getElementById("rg-panel");
    if (panel && panel.classList.contains("rg-open")) {
      panel.classList.remove("rg-open");
      btn.textContent = "Analyze PR";
      btn.classList.remove("active");
    } else {
      btn.textContent = "X Close";
      btn.classList.add("active");
      runAnalysis();
    }
  };
  document.body.appendChild(btn);
}

// -- INIT --------------------------------------------------
injectStyles();

function init() {
  if (window.location.href.includes("/pull/")) {
    injectTriggerBtn();
  }
}

init();

// Watch GitHub SPA navigation
let _lastURL = location.href;
const _navObs = new MutationObserver(() => {
  if (location.href === _lastURL) return;
  _lastURL = location.href;
  setTimeout(() => {
    if (location.href.includes("/pull/")) {
      injectTriggerBtn();
    }
  }, 1000);
});
_navObs.observe(document.body, { childList: true, subtree: true });

} // end guard
