"""Interactive Prototype HTML Renderer for ProcessFoundry AI (Feature 08).

Converts a validated PrototypeSpec into a self-contained, interactive HTML document
that can be rendered inside Streamlit components.html() or downloaded as a standalone file.

Safety & Constraints:
- Zero dynamic code evaluation or execution primitives.
- Pure client-side JS and vanilla CSS.
- Sandboxed execution; no data is saved or sent over the network.
- All user-supplied text is properly HTML-escaped.
- Full UTF-8 and multilingual support (Devanagari, etc.).
"""
import html
import json
from typing import Any, Dict, Union

from app.schemas.prototypes import PrototypeSpec


_PROTOTYPE_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__ - Interactive Prototype</title>
<style>
* { box-sizing: border-box; }
body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #f8fafc; color: #0f172a; line-height: 1.5; }
.banner { background: #fef3c7; color: #92400e; padding: 10px 18px; font-size: 13px; font-weight: 600; border-bottom: 1px solid #fde68a; display: flex; align-items: center; justify-content: space-between; }
.banner-badge { background: #b45309; color: #ffffff; padding: 2px 8px; border-radius: 4px; font-size: 11px; text-transform: uppercase; margin-right: 8px; }
.top-bar { background: #ffffff; border-bottom: 1px solid #e2e8f0; padding: 12px 20px; display: flex; flex-wrap: wrap; gap: 16px; align-items: center; justify-content: space-between; }
.title-group h1 { margin: 0; font-size: 18px; font-weight: 700; color: #0f172a; }
.title-group .sub { color: #64748b; font-size: 12px; }
.role-control { display: flex; align-items: center; gap: 10px; font-size: 13px; font-weight: 600; color: #334155; }
.role-select { padding: 6px 12px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 13px; background: #ffffff; font-weight: 500; cursor: pointer; color: #0f172a; }
.role-select:focus { outline: 2px solid #2563eb; }
.wrap { display: flex; gap: 20px; padding: 20px; max-width: 1240px; margin: 0 auto; }
.side { width: 320px; flex: none; display: flex; flex-direction: column; gap: 16px; }
.main { flex: 1; min-width: 0; }
.card { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.03); }
.search-input { width: 100%; padding: 8px 12px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 13px; margin-bottom: 12px; }
.step-list { max-height: 520px; overflow-y: auto; display: flex; flex-direction: column; gap: 4px; padding-right: 4px; }
.step-item { display: flex; align-items: flex-start; gap: 10px; padding: 10px 12px; border-radius: 8px; font-size: 13px; cursor: pointer; border: 1px solid transparent; transition: all 0.15s ease; }
.step-item:hover { background: #f1f5f9; }
.step-item.cur { background: #eff6ff; border-color: #bfdbfe; font-weight: 600; }
.step-item.done { color: #166534; }
.step-item.hidden-role { display: none !important; }
.step-dot { width: 22px; height: 22px; border-radius: 50%; background: #e2e8f0; font-size: 11px; display: flex; align-items: center; justify-content: center; flex: none; margin-top: 2px; }
.cur .step-dot { background: #2563eb; color: #ffffff; font-weight: 700; }
.done .step-dot { background: #bbf7d0; color: #166534; font-weight: 700; }
.chip { display: inline-flex; align-items: center; padding: 3px 10px; border-radius: 9999px; font-size: 12px; font-weight: 600; margin-right: 6px; margin-bottom: 6px; }
.chip-actor { background: #e0f2fe; color: #0369a1; }
.chip-auto { background: #ede9fe; color: #6d28d9; }
.chip-approval { background: #fee2e2; color: #b91c1c; }
.warning-box { background: #fefce8; border: 1px solid #fef08a; border-radius: 8px; padding: 12px 14px; margin-bottom: 16px; font-size: 13px; color: #854d0e; }
.notice-title { font-weight: 700; margin-bottom: 4px; display: flex; align-items: center; gap: 6px; }
.field-group { margin-bottom: 16px; }
label { display: block; font-size: 13.5px; font-weight: 600; margin-bottom: 5px; color: #1e293b; }
.field-hint { font-size: 12px; color: #64748b; margin-top: 4px; font-style: italic; }
input[type=text], input[type=number], input[type=date], input[type=file], select, textarea {
  width: 100%; padding: 9px 12px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 14px; background: #ffffff; color: #0f172a; font-family: inherit;
}
input:focus, select:focus, textarea:focus { outline: 2px solid #2563eb; border-color: #2563eb; }
textarea { resize: vertical; min-height: 70px; }
.recv-box { background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 6px; padding: 8px 12px; font-size: 13px; color: #15803d; margin-bottom: 10px; }
.output-box { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; margin-top: 18px; }
.btn-row { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 20px; }
button { border: 0; border-radius: 6px; padding: 9px 18px; font-size: 13.5px; font-weight: 600; cursor: pointer; transition: background 0.15s; }
.btn-primary { background: #2563eb; color: #ffffff; }
.btn-primary:hover { background: #1d4ed8; }
.btn-success { background: #16a34a; color: #ffffff; }
.btn-success:hover { background: #15803d; }
.btn-warning { background: #f59e0b; color: #ffffff; }
.btn-warning:hover { background: #d97706; }
.btn-danger { background: #dc2626; color: #ffffff; }
.btn-danger:hover { background: #b91c1c; }
.btn-secondary { background: #e2e8f0; color: #334155; }
.btn-secondary:hover { background: #cbd5e1; }
.err-msg { color: #dc2626; font-size: 13px; font-weight: 600; margin-top: 12px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 8px; }
th, td { border: 1px solid #e2e8f0; padding: 8px 12px; text-align: left; }
th { background: #f8fafc; font-weight: 600; color: #475569; }
.rules-detail { font-size: 12.5px; margin-top: 6px; color: #475569; border-top: 1px solid #f1f5f9; padding-top: 6px; }
.rule-pill { display: inline-block; background: #e2e8f0; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: 600; margin-right: 4px; color: #1e293b; }
@media(max-width: 860px) { .wrap { flex-direction: column; } .side { width: 100%; } }
</style>
</head>
<body>

<div class="banner">
  <div><span class="banner-badge">PROTOTYPE</span> Illustrative only. Nothing typed is saved or sent anywhere. This is a design specification prototype.</div>
  <div style="font-size:12px; opacity:0.85;">ProcessFoundry AI</div>
</div>

<div class="top-bar">
  <div class="title-group">
    <h1 id="procTitle"></h1>
    <div class="sub">Interactive Step-by-Step Simulation & Persona Flow</div>
  </div>
  <div class="role-control">
    <label for="roleFilter" style="margin:0; font-size:13px;">View Persona:</label>
    <select id="roleFilter" class="role-select">
      <option value="__ALL__">All Roles (Complete Process)</option>
    </select>
  </div>
</div>

<div class="wrap">
  <div class="side">
    <div class="card">
      <div style="font-weight:700; font-size:14px; margin-bottom:8px;">Workflow Steps</div>
      <input type="text" id="stepSearch" class="search-input" placeholder="Filter steps...">
      <div id="stepTracker" class="step-list"></div>
    </div>

    <div class="card" id="rulesCard">
      <div style="font-weight:700; font-size:14px; margin-bottom:8px;">Business Rules in Force</div>
      <div id="rulesList" style="max-height:240px; overflow-y:auto; display:flex; flex-direction:column; gap:8px;"></div>
    </div>
  </div>

  <div class="main">
    <div id="screenContainer"></div>
  </div>
</div>

<script>
const DATA = __DATA__;
let curIndex = 0;
let historyLog = [];
let enteredValues = {};
let activeRole = "__ALL__";
let validationError = "";
let processFinished = false;
let terminationReason = null;

const $ = id => document.getElementById(id);

function el(tag, attrs, children) {
  const elem = document.createElement(tag);
  for (const k in (attrs || {})) {
    if (k === "class") elem.className = attrs[k];
    else if (k === "style") elem.setAttribute("style", attrs[k]);
    else elem.setAttribute(k, attrs[k]);
  }
  (children || []).forEach(child => {
    elem.appendChild(typeof child === "string" ? document.createTextNode(child) : child);
  });
  return elem;
}

function initRoleDropdown() {
  const sel = $("roleFilter");
  (DATA.actors || []).forEach(actor => {
    const opt = el("option", { value: actor }, [actor]);
    sel.appendChild(opt);
  });
  sel.onchange = e => {
    activeRole = e.target.value;
    updateStepVisibility();
    ensureCurrentStepVisible();
    render();
  };
}

function updateStepVisibility() {
  const items = document.querySelectorAll(".step-item");
  items.forEach(it => {
    const stepActor = it.getAttribute("data-actor");
    if (activeRole === "__ALL__" || stepActor === activeRole) {
      it.classList.remove("hidden-role");
    } else {
      it.classList.add("hidden-role");
    }
  });
}

function ensureCurrentStepVisible() {
  if (activeRole === "__ALL__" || processFinished) return;
  const curScreen = DATA.screens[curIndex];
  if (curScreen && curScreen.actor !== activeRole) {
    const nextMatch = DATA.screens.findIndex((s, idx) => idx >= curIndex && s.actor === activeRole);
    if (nextMatch !== -1) {
      curIndex = nextMatch;
    } else {
      const prevMatch = DATA.screens.findIndex(s => s.actor === activeRole);
      if (prevMatch !== -1) curIndex = prevMatch;
    }
  }
}

function producedOutputsSoFar(index) {
  const set = new Set();
  for (let i = 0; i < index; i++) {
    (DATA.screens[i].outputs || []).forEach(o => set.add(o.toLowerCase()));
  }
  return set;
}

function renderTracker() {
  const container = $("stepTracker");
  container.replaceChildren();

  const filterText = ($("stepSearch").value || "").toLowerCase().trim();

  DATA.screens.forEach((sc, idx) => {
    const isDone = idx < curIndex || processFinished;
    const isCur = idx === curIndex && !processFinished;
    let cls = "step-item" + (isCur ? " cur" : "") + (isDone ? " done" : "");
    if (activeRole !== "__ALL__" && sc.actor !== activeRole) {
      cls += " hidden-role";
    }

    if (filterText && !sc.title.toLowerCase().includes(filterText) && !sc.screen_id.toLowerCase().includes(filterText)) {
      cls += " hidden-role";
    }

    const dot = el("div", { class: "step-dot" }, [isDone ? "✓" : String(idx + 1)]);
    const info = el("div", {}, [
      sc.title,
      el("div", { style: "font-size:11px; color:#64748b;" }, [sc.screen_id + " · " + (sc.actor || "Actor not stated")])
    ]);

    const item = el("div", { class: cls, "data-actor": sc.actor || "" }, [dot, info]);
    item.onclick = () => {
      if (processFinished) return;
      curIndex = idx;
      validationError = "";
      render();
    };
    container.appendChild(item);
  });
}

function renderRulesCatalogue() {
  const container = $("rulesList");
  container.replaceChildren();
  if (!DATA.business_rules || !DATA.business_rules.length) {
    $("rulesCard").style.display = "none";
    return;
  }
  DATA.business_rules.forEach(r => {
    const row = el("div", { class: "rules-detail" }, [
      el("span", { class: "rule-pill" }, [r.key]),
      r.description
    ]);
    container.appendChild(row);
  });
}

function handleStepAction(screen, index, decision) {
  const prevProduced = producedOutputsSoFar(index);
  const unsupplied = [];

  (screen.fields || []).forEach((fld, fIdx) => {
    if (prevProduced.has(fld.name.toLowerCase())) return;
    const elem = $("f_" + fIdx);
    let val = "";
    if (elem) {
      if (elem.type === "file") {
        val = elem.files && elem.files[0] ? elem.files[0].name : "";
      } else {
        val = (elem.value || "").trim();
      }
    }
    if (fld.required && !val && decision !== "reject") {
      unsupplied.push(fld.name);
    }
    if (val) {
      enteredValues[fld.name] = val;
    }
  });

  if (unsupplied.length && decision !== "reject") {
    validationError = "Please complete required field(s): " + unsupplied.join(", ") + " (prototype validation).";
    render();
    return;
  }

  validationError = "";
  let resultLabel = "Completed";
  if (decision === "approve") resultLabel = "Approved";
  else if (decision === "changes") resultLabel = "Changes Requested";
  else if (decision === "reject") resultLabel = "Rejected";

  historyLog.push({
    screen_id: screen.screen_id,
    title: screen.title,
    actor: screen.actor || "Actor not stated",
    decision: resultLabel
  });

  if (decision === "reject") {
    processFinished = true;
    terminationReason = "Rejected at " + screen.screen_id + " (" + screen.title + ")";
    render();
    return;
  }

  if (decision === "changes") {
    processFinished = true;
    terminationReason = "Returned for changes at " + screen.screen_id + " (" + screen.title + ")";
    render();
    return;
  }

  // Advance to next screen for active role
  let nextIdx = index + 1;
  if (activeRole !== "__ALL__") {
    while (nextIdx < DATA.screens.length && DATA.screens[nextIdx].actor !== activeRole) {
      nextIdx++;
    }
  }

  if (nextIdx >= DATA.screens.length) {
    processFinished = true;
    terminationReason = null;
  } else {
    curIndex = nextIdx;
  }
  render();
}

function renderCompletionView() {
  const container = $("screenContainer");
  container.replaceChildren();

  const card = el("div", { class: "card" });
  card.appendChild(el("h2", { style: "margin:0 0 8px;" }, [terminationReason ? "Process Terminated" : "Process Simulation Complete"]));
  card.appendChild(el("p", { style: "color:#64748b; font-size:14px; margin:0 0 16px;" }, [
    terminationReason ? terminationReason : "All steps in this process prototype simulation were walked through successfully."
  ]));

  // Log table
  const tbl = el("table", {}, [
    el("tr", {}, [el("th", {}, ["Screen"]), el("th", {}, ["Title"]), el("th", {}, ["Persona"]), el("th", {}, ["Result"])])
  ]);
  historyLog.forEach(item => {
    tbl.appendChild(el("tr", {}, [
      el("td", {}, [item.screen_id]),
      el("td", {}, [item.title]),
      el("td", {}, [item.actor]),
      el("td", { style: "font-weight:600;" }, [item.decision])
    ]));
  });
  card.appendChild(tbl);

  // Entered data summary
  const keys = Object.keys(enteredValues);
  if (keys.length) {
    const summaryCard = el("div", { class: "output-box", style: "margin-top:16px;" }, [
      el("div", { style: "font-weight:700; font-size:13px; margin-bottom:8px; color:#1e293b;" }, ["Data Entered During Simulation (Illustrative Only):"])
    ]);
    const dList = el("ul", { style: "margin:0; padding-left:20px; font-size:13px; color:#475569;" });
    keys.forEach(k => {
      dList.appendChild(el("li", {}, [el("strong", {}, [k + ": "]), enteredValues[k]]));
    });
    summaryCard.appendChild(dList);
    card.appendChild(summaryCard);
  }

  const resetBtn = el("button", { class: "btn-primary", style: "margin-top:20px;" }, ["Restart Prototype Simulation"]);
  resetBtn.onclick = () => {
    curIndex = 0;
    historyLog = [];
    enteredValues = {};
    processFinished = false;
    terminationReason = null;
    validationError = "";
    ensureCurrentStepVisible();
    render();
  };
  card.appendChild(resetBtn);

  container.appendChild(card);
}

function render() {
  renderTracker();

  if (processFinished || curIndex >= DATA.screens.length) {
    renderCompletionView();
    return;
  }

  const sc = DATA.screens[curIndex];
  const container = $("screenContainer");
  container.replaceChildren();

  const card = el("div", { class: "card" });

  // Header
  const stepMeta = el("div", { style: "display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;" }, [
    el("span", { style: "font-size:12px; color:#64748b; font-weight:600;" }, ["SCREEN " + (curIndex + 1) + " OF " + DATA.screens.length + " · " + sc.screen_id]),
    el("div", {}, [
      el("span", { class: "chip chip-actor" }, ["Persona: " + (sc.actor || "Actor not stated")]),
      sc.automation ? el("span", { class: "chip chip-auto" }, [sc.automation.toUpperCase()]) : el("span", {}),
      sc.human_approval_required ? el("span", { class: "chip chip-approval" }, ["APPROVAL REQUIRED"]) : el("span", {})
    ])
  ]);
  card.appendChild(stepMeta);

  card.appendChild(el("h2", { style: "margin:4px 0 16px; font-size:20px;" }, [sc.title]));

  // Missing info / Unknowns notice
  if (sc.unknowns && sc.unknowns.length) {
    const wBox = el("div", { class: "warning-box" }, [
      el("div", { class: "notice-title" }, ["⚠️ Source Ambiguity / Missing Information"]),
      el("div", {}, [sc.unknowns.join("; ")])
    ]);
    card.appendChild(wBox);
  } else if (!sc.actor || sc.actor === "Actor not stated") {
    const wBox = el("div", { class: "warning-box" }, [
      el("div", { class: "notice-title" }, ["⚠️ Actor Undefined"]),
      el("div", {}, ["The original source documents did not state which role executes this step."])
    ]);
    card.appendChild(wBox);
  }

  // Fields
  const prevProduced = producedOutputsSoFar(curIndex);
  const formBox = el("div", { style: "margin-top:12px;" });

  if (!sc.fields || !sc.fields.length) {
    formBox.appendChild(el("div", { style: "color:#64748b; font-size:13.5px; font-style:italic; margin-bottom:12px;" }, [
      "No input fields specified for this step."
    ]));
  } else {
    sc.fields.forEach((fld, fIdx) => {
      const isAlreadyReceived = prevProduced.has(fld.name.toLowerCase());
      if (isAlreadyReceived) {
        formBox.appendChild(el("div", { class: "recv-box" }, [
          "✓ Received from earlier step: ",
          el("strong", {}, [fld.name]),
          enteredValues[fld.name] ? " (" + enteredValues[fld.name] + ")" : ""
        ]));
        return;
      }

      const fg = el("div", { class: "field-group" });
      const lbl = el("label", { for: "f_" + fIdx }, [
        fld.name,
        fld.required ? el("span", { style: "color:#dc2626; margin-left:3px;" }, ["*"]) : el("span", {})
      ]);
      fg.appendChild(lbl);

      let inputEl;
      if (fld.field_type === "textarea") {
        inputEl = el("textarea", { id: "f_" + fIdx, placeholder: "Enter " + fld.name.toLowerCase() + "..." });
      } else if (fld.field_type === "select") {
        inputEl = el("select", { id: "f_" + fIdx });
        inputEl.appendChild(el("option", { value: "" }, ["-- Select " + fld.name + " --"]));
        (fld.options || []).forEach(opt => {
          inputEl.appendChild(el("option", { value: opt }, [opt]));
        });
      } else if (fld.field_type === "file") {
        inputEl = el("input", { id: "f_" + fIdx, type: "file" });
      } else if (fld.field_type === "date") {
        inputEl = el("input", { id: "f_" + fIdx, type: "date" });
      } else if (fld.field_type === "number") {
        inputEl = el("input", { id: "f_" + fIdx, type: "number", placeholder: "Enter number..." });
      } else {
        inputEl = el("input", { id: "f_" + fIdx, type: "text", placeholder: "Enter " + fld.name.toLowerCase() + "..." });
      }

      if (enteredValues[fld.name] && fld.field_type !== "file") {
        inputEl.value = enteredValues[fld.name];
      }

      fg.appendChild(inputEl);
      if (fld.hint) {
        fg.appendChild(el("div", { class: "field-hint" }, [fld.hint]));
      }
      formBox.appendChild(fg);
    });
  }
  card.appendChild(formBox);

  // Table view for list outputs if outputs > 1
  if (sc.outputs && sc.outputs.length > 0) {
    const outBox = el("div", { class: "output-box" }, [
      el("div", { style: "font-weight:700; font-size:13px; color:#334155; margin-bottom:6px;" }, ["Generated Outputs:"])
    ]);
    if (sc.outputs.length > 1) {
      const outTable = el("table", {}, [
        el("tr", {}, [el("th", {}, ["#"]), el("th", {}, ["Artifact / Record Output"]), el("th", {}, ["Type"])])
      ]);
      sc.outputs.forEach((outName, oIdx) => {
        outTable.appendChild(el("tr", {}, [
          el("td", {}, [String(oIdx + 1)]),
          el("td", { style: "font-weight:600;" }, [outName]),
          el("td", {}, ["System Record"])
        ]));
      });
      outBox.appendChild(outTable);
    } else {
      outBox.appendChild(el("div", { style: "font-size:13px; color:#475569;" }, [
        "Produces: " + sc.outputs.join(", ")
      ]));
    }
    card.appendChild(outBox);
  }

  // Linked Requirements and Rules Pills
  if ((sc.requirement_keys && sc.requirement_keys.length) || (sc.business_rule_keys && sc.business_rule_keys.length)) {
    const metaFooter = el("div", { style: "margin-top:16px; padding-top:12px; border-top:1px solid #f1f5f9; font-size:12px; color:#64748b;" });
    if (sc.requirement_keys && sc.requirement_keys.length) {
      metaFooter.appendChild(el("span", { style: "font-weight:600; margin-right:6px;" }, ["Requirements:"]));
      sc.requirement_keys.forEach(rk => {
        metaFooter.appendChild(el("span", { class: "rule-pill", style: "background:#dbeafe; color:#1e40af;" }, [rk]));
      });
    }
    if (sc.business_rule_keys && sc.business_rule_keys.length) {
      metaFooter.appendChild(el("span", { style: "font-weight:600; margin:0 6px 0 12px;" }, ["Rules:"]));
      sc.business_rule_keys.forEach(bk => {
        metaFooter.appendChild(el("span", { class: "rule-pill" }, [bk]));
      });
    }
    card.appendChild(metaFooter);
  }

  // Validation Error
  if (validationError) {
    card.appendChild(el("div", { class: "err-msg" }, [validationError]));
  }

  // Buttons
  const btnRow = el("div", { class: "btn-row" });
  if (sc.human_approval_required) {
    const appBtn = el("button", { class: "btn-success" }, ["Approve Step"]);
    appBtn.onclick = () => handleStepAction(sc, curIndex, "approve");
    const chgBtn = el("button", { class: "btn-warning" }, ["Request Changes"]);
    chgBtn.onclick = () => handleStepAction(sc, curIndex, "changes");
    const rejBtn = el("button", { class: "btn-danger" }, ["Reject"]);
    rejBtn.onclick = () => handleStepAction(sc, curIndex, "reject");
    btnRow.appendChild(appBtn);
    btnRow.appendChild(chgBtn);
    btnRow.appendChild(rejBtn);
  } else {
    const btnLabel = sc.automation === "deterministic" ? "Execute Automated Step" : "Complete & Proceed";
    const nextBtn = el("button", { class: "btn-primary" }, [btnLabel]);
    nextBtn.onclick = () => handleStepAction(sc, curIndex, "complete");
    btnRow.appendChild(nextBtn);
  }

  if (curIndex > 0) {
    const backBtn = el("button", { class: "btn-secondary" }, ["← Previous Screen"]);
    backBtn.onclick = () => {
      let prevIdx = curIndex - 1;
      if (activeRole !== "__ALL__") {
        while (prevIdx >= 0 && DATA.screens[prevIdx].actor !== activeRole) {
          prevIdx--;
        }
      }
      if (prevIdx >= 0) {
        curIndex = prevIdx;
        historyLog.pop();
        validationError = "";
        render();
      }
    };
    btnRow.appendChild(backBtn);
  }

  card.appendChild(btnRow);
  container.appendChild(card);
}

// Bootstrap
$("procTitle").textContent = DATA.process_name || "Process Prototype";
document.title = (DATA.process_name || "Process") + " - Interactive Prototype";
$("stepSearch").oninput = () => renderTracker();
initRoleDropdown();
renderRulesCatalogue();
render();
</script>
</body>
</html>
"""


def render_full_prototype(spec: Union[PrototypeSpec, Dict[str, Any]]) -> str:
    """Render a self-contained interactive prototype HTML string from a PrototypeSpec."""
    if isinstance(spec, PrototypeSpec):
        spec_dict = spec.dict()
    else:
        spec_dict = dict(spec)

    process_name = spec_dict.get("process_name") or "Process"
    escaped_title = html.escape(str(process_name))

    # Serialize JSON with safety escapes
    payload = json.dumps(spec_dict, ensure_ascii=False)
    payload = (
        payload.replace("</", "<\\/")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )

    return (
        _PROTOTYPE_TEMPLATE
        .replace("__TITLE__", escaped_title)
        .replace("__DATA__", payload)
    )
