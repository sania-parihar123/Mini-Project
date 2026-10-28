"""ProcessFoundry AI: Workflow Preview and Prototype Generator (design doc A11).

Pure Python, no model calls, no extra packages, no database access. Both outputs
are built from the project's own workflow JSON (the `workflow_json` artifact):

* `preview_html(...)`   - a swimlane diagram (one lane per actor) as inline SVG.
* `prototype_html(...)` - a self-contained, clickable step-by-step prototype that
                          walks through the proposed process as each actor.

The prototype is illustrative only. It stores nothing, sends nothing and says so
on screen. Field types are guessed from input names; anything the sources did not
state is not invented.
"""
import html
import json
import re
from typing import Any, Dict, List, Optional

AUTOMATION_STYLE = {
    "deterministic": ("#dbeafe", "#2563eb", "Automated"),
    "ai_assisted": ("#ede9fe", "#7c3aed", "AI-assisted"),
    "human": ("#ffedd5", "#ea580c", "Human"),
    "hybrid": ("#ccfbf1", "#0d9488", "Hybrid"),
}
DEFAULT_STYLE = ("#e5e7eb", "#6b7280", "Not classified")


def normalise(workflow: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Return a clean {name, steps, transitions} dict, or None if there are no steps."""
    if not workflow or not isinstance(workflow, dict):
        return None
    raw_steps = workflow.get("steps") or []
    if not raw_steps:
        return None
    steps = []
    for i, s in enumerate(raw_steps):
        steps.append({
            "id": str(s.get("id") or f"STEP-{i + 1:03d}"),
            "name": str(s.get("name") or f"Step {i + 1}"),
            "actor": str(s.get("actor") or "Process Participant"),
            "kind": str(s.get("kind") or "task"),
            "automation": str(s.get("automation") or ""),
            "inputs": [str(x) for x in (s.get("inputs") or [])],
            "outputs": [str(x) for x in (s.get("outputs") or [])],
            "approval": bool(s.get("human_approval_required")),
        })
    ids = {s["id"] for s in steps}
    transitions = [
        {"from": str(t.get("from")), "to": str(t.get("to")), "condition": str(t.get("condition") or "")}
        for t in (workflow.get("transitions") or [])
        if str(t.get("from")) in ids and str(t.get("to")) in ids
    ]
    if not transitions:
        transitions = [
            {"from": steps[i]["id"], "to": steps[i + 1]["id"], "condition": ""}
            for i in range(len(steps) - 1)
        ]
    return {
        "name": str(workflow.get("process_name") or workflow.get("name") or "Process"),
        "steps": steps,
        "transitions": transitions,
    }


def _wrap(text: str, width: int, max_lines: int) -> List[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 <= width:
            cur = (cur + " " + w).strip()
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1][: max(0, width - 3)] + "..."
    return lines or [""]


# ---------------------------------------------------------------------------
# Swimlane preview
# ---------------------------------------------------------------------------
def preview_html(workflow: Optional[Dict[str, Any]]) -> Optional[tuple]:
    """Return (html, suggested_height_px), or None when there are no steps."""
    wf = normalise(workflow)
    if not wf:
        return None
    steps = wf["steps"]
    lanes: List[str] = []
    for s in steps:
        if s["actor"] not in lanes:
            lanes.append(s["actor"])

    BOX_W, BOX_H, GAP_X, LANE_H, LEFT, TOP = 170, 70, 40, 120, 150, 20
    width = LEFT + len(steps) * (BOX_W + GAP_X) + 20
    height = TOP + len(lanes) * LANE_H + 10

    pos: Dict[str, Dict[str, int]] = {}
    for i, s in enumerate(steps):
        lane = lanes.index(s["actor"])
        pos[s["id"]] = {
            "x": LEFT + i * (BOX_W + GAP_X),
            "y": TOP + lane * LANE_H + (LANE_H - BOX_H) // 2,
        }

    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
           f'viewBox="0 0 {width} {height}" font-family="Segoe UI, Arial, sans-serif">',
           '<defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
           'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#64748b"/></marker></defs>']

    for li, lane in enumerate(lanes):
        y = TOP + li * LANE_H
        fill = "#f8fafc" if li % 2 == 0 else "#f1f5f9"
        svg.append(f'<rect x="0" y="{y}" width="{width}" height="{LANE_H}" fill="{fill}" stroke="#e2e8f0"/>')
        svg.append(f'<rect x="0" y="{y}" width="{LEFT - 20}" height="{LANE_H}" fill="#e2e8f0"/>')
        for k, line in enumerate(_wrap(lane, 16, 3)):
            svg.append(f'<text x="10" y="{y + LANE_H // 2 - 8 + k * 16}" font-size="13" font-weight="700" '
                       f'fill="#1e293b">{html.escape(line)}</text>')

    # Edges first so boxes sit on top
    for t in wf["transitions"]:
        a, b = pos[t["from"]], pos[t["to"]]
        x1, y1 = a["x"] + BOX_W, a["y"] + BOX_H // 2
        x2, y2 = b["x"], b["y"] + BOX_H // 2
        if y1 == y2:
            d = f"M{x1},{y1} L{x2},{y2}"
        else:
            mx = x1 + GAP_X // 2
            d = f"M{x1},{y1} H{mx} V{y2} H{x2}"
        svg.append(f'<path d="{d}" fill="none" stroke="#64748b" stroke-width="2" marker-end="url(#arr)"/>')
        if t["condition"] and t["condition"] != "on_success":
            # Label sits just above the target box, clear of arrows and other boxes.
            svg.append(f'<text x="{b["x"] + 4}" y="{b["y"] - 5}" font-size="10" font-style="italic" '
                       f'fill="#475569">if {html.escape(t["condition"][:26])}</text>')

    for s in steps:
        p = pos[s["id"]]
        bg, border, label = AUTOMATION_STYLE.get(s["automation"], DEFAULT_STYLE)
        sw = 3 if s["approval"] else 1.5
        svg.append(f'<rect x="{p["x"]}" y="{p["y"]}" width="{BOX_W}" height="{BOX_H}" rx="10" '
                   f'fill="{bg}" stroke="{border}" stroke-width="{sw}"/>')
        svg.append(f'<text x="{p["x"] + 8}" y="{p["y"] + 15}" font-size="10" font-weight="700" '
                   f'fill="{border}">{html.escape(s["id"])} · {label}{" · APPROVAL" if s["approval"] else ""}</text>')
        for k, line in enumerate(_wrap(s["name"], 25, 3)):
            svg.append(f'<text x="{p["x"] + 8}" y="{p["y"] + 32 + k * 14}" font-size="12" '
                       f'fill="#0f172a">{html.escape(line)}</text>')
    svg.append("</svg>")

    legend = "".join(
        f'<span style="display:inline-flex;align-items:center;margin-right:14px;font-size:12px;color:#334155;">'
        f'<span style="width:14px;height:14px;background:{bg};border:2px solid {bd};border-radius:4px;'
        f'margin-right:6px;"></span>{lbl}</span>'
        for bg, bd, lbl in AUTOMATION_STYLE.values()
    ) + ('<span style="font-size:12px;color:#334155;">Thick border = human approval required</span>')

    return (
        '<div style="font-family:Segoe UI,Arial,sans-serif;background:#ffffff;padding:8px;">'
        f'<div style="font-weight:700;font-size:15px;color:#0f172a;margin:0 0 6px 2px;">'
        f'{html.escape(wf["name"])} - proposed workflow</div>'
        f'<div style="margin:0 0 8px 2px;">{legend}</div>'
        f'<div style="overflow-x:auto;border:1px solid #e2e8f0;border-radius:8px;">{"".join(svg)}</div>'
        '</div>'
    ), len(lanes) * LANE_H + 130


# ---------------------------------------------------------------------------
# Clickable prototype
# ---------------------------------------------------------------------------
_PROTOTYPE_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__ - clickable prototype</title>
<style>
*{box-sizing:border-box}body{margin:0;font-family:Segoe UI,Arial,sans-serif;background:#f1f5f9;color:#0f172a}
.banner{background:#fef3c7;color:#92400e;padding:8px 14px;font-size:13px;border-bottom:1px solid #fde68a}
.wrap{display:flex;gap:16px;padding:16px;max-width:1100px;margin:0 auto}
.side{width:260px;flex:none}.main{flex:1;min-width:0}
.card{background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:18px;margin-bottom:14px}
h1{font-size:18px;margin:0 0 4px}h2{font-size:17px;margin:0 0 4px}.muted{color:#64748b;font-size:13px}
.step{display:flex;gap:8px;align-items:flex-start;padding:7px 8px;border-radius:8px;font-size:13px;margin-bottom:2px}
.step.cur{background:#dbeafe;font-weight:600}.step.done{color:#15803d}
.dot{width:18px;height:18px;border-radius:50%;background:#e2e8f0;flex:none;font-size:11px;display:flex;align-items:center;justify-content:center;margin-top:1px}
.done .dot{background:#bbf7d0}.cur .dot{background:#2563eb;color:#fff}
.chip{display:inline-block;padding:3px 10px;border-radius:999px;font-size:12px;font-weight:600;margin-right:6px}
label{display:block;font-size:13px;font-weight:600;margin:12px 0 4px}
input[type=text],input[type=date],input[type=file],select{width:100%;padding:9px;border:1px solid #cbd5e1;border-radius:8px;font-size:14px;background:#fff}
.recv{background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:8px 10px;font-size:13px;margin-top:8px}
.out{background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;padding:8px 10px;font-size:13px;margin-top:14px}
button{border:0;border-radius:8px;padding:10px 16px;font-size:14px;font-weight:600;cursor:pointer;margin-right:8px;margin-top:16px}
.pri{background:#2563eb;color:#fff}.ok{background:#16a34a;color:#fff}.warn{background:#f59e0b;color:#fff}.bad{background:#dc2626;color:#fff}.ghost{background:#e2e8f0;color:#0f172a}
.err{color:#b91c1c;font-size:13px;margin-top:10px}
table{width:100%;border-collapse:collapse;font-size:13px}td,th{border-bottom:1px solid #e2e8f0;padding:6px;text-align:left;vertical-align:top}
details summary{cursor:pointer;font-weight:600;font-size:13px}
@media(max-width:760px){.wrap{flex-direction:column}.side{width:100%}}
</style></head><body>
<div class="banner"><b>PROTOTYPE</b> - illustrative only. Nothing you type is saved or sent anywhere, and this is not a working system or official college policy.</div>
<div class="wrap">
 <div class="side"><div class="card"><h1 id="pname"></h1><div class="muted">Process progress</div><div id="tracker" style="margin-top:8px"></div></div>
  <div class="card" id="rulesBox"></div></div>
 <div class="main"><div id="screen"></div></div>
</div>
<script>
const DATA=__DATA__;
const STYLE={deterministic:["#dbeafe","#2563eb","Automated step"],ai_assisted:["#ede9fe","#7c3aed","AI-assisted step"],human:["#ffedd5","#ea580c","Human step"],hybrid:["#ccfbf1","#0d9488","Hybrid step"]};
const FILE_RE=/document|certificate|proof|receipt|upload|marksheet|photo|scan|attachment|copy|letter|id card|aadhaar|statement/i;
const DATE_RE=/date|deadline|period|time/i;
let idx=0,log=[],entered={},ended=null,err="";
const $=id=>document.getElementById(id);
function el(tag,attrs,kids){const e=document.createElement(tag);for(const k in(attrs||{})){if(k==="class")e.className=attrs[k];else if(k==="style")e.setAttribute("style",attrs[k]);else e.setAttribute(k,attrs[k]);}
 (kids||[]).forEach(c=>e.appendChild(typeof c==="string"?document.createTextNode(c):c));return e}
function producedBefore(i){const s=new Set();for(let k=0;k<i;k++)DATA.steps[k].outputs.forEach(o=>s.add(o.toLowerCase()));return s}
function fieldKind(n){return FILE_RE.test(n)?"file":(DATE_RE.test(n)?"date":"text")}
function renderTracker(){const t=$("tracker");t.replaceChildren();
 DATA.steps.forEach((s,i)=>{const cls="step"+(ended?"":(i<idx?" done":(i===idx?" cur":"")))+(ended&&i<idx?" done":"");
  t.appendChild(el("div",{class:cls},[el("div",{class:"dot"},[i<idx?"✓":String(i+1)]),el("div",{},[s.name,el("div",{class:"muted"},[s.actor])])]))})}
function renderRules(){const b=$("rulesBox");b.replaceChildren();
 if(!DATA.rules.length){b.style.display="none";return}
 const d=el("details",{},[el("summary",{},["Business rules in force ("+DATA.rules.length+")"])]);
 DATA.rules.forEach(r=>d.appendChild(el("div",{class:"muted",style:"margin-top:8px"},[r.key+": "+r.text])));b.appendChild(d)}
function collect(s,i){const need=[];const prev=producedBefore(i);
 s.inputs.forEach((n,k)=>{if(prev.has(n.toLowerCase()))return;const f=$("f"+k);const v=f?(f.type==="file"?(f.files[0]?f.files[0].name:""):f.value.trim()):"";need.push([n,v])});return need}
function finishStep(s,i,decision){
 const vals=collect(s,i);
 if(decision!=="reject"){const miss=vals.filter(x=>!x[1]);if(miss.length){err="Please complete: "+miss.map(x=>x[0]).join(", ")+" (prototype validation).";render();return}}
 vals.forEach(x=>{entered[x[0]]=x[1]});
 log.push({id:s.id,name:s.name,actor:s.actor,result:decision==="reject"?"Rejected":(decision==="changes"?"Changes requested":(s.approval?"Approved":"Completed"))});
 err="";
 if(decision==="reject"){ended="Rejected at "+s.id+" ("+s.name+")";idx=i+1;render();return}
 if(decision==="changes"){ended="Sent back for changes at "+s.id+" ("+s.name+")";idx=i+1;render();return}
 idx=i+1;render()}
function render(){renderTracker();const sc=$("screen");sc.replaceChildren();
 if(ended||idx>=DATA.steps.length){
  const c=el("div",{class:"card"},[el("h2",{},[ended?"Process stopped":"Process complete"]),el("div",{class:"muted"},[ended||"All steps in the proposed workflow were walked through."])]);
  const tb=el("table",{},[el("tr",{},[el("th",{},["Step"]),el("th",{},["Actor"]),el("th",{},["Result"])])]);
  log.forEach(l=>tb.appendChild(el("tr",{},[el("td",{},[l.id+" "+l.name]),el("td",{},[l.actor]),el("td",{},[l.result])])));
  c.appendChild(el("div",{style:"margin-top:12px"},[tb]));
  const ks=Object.keys(entered);if(ks.length){c.appendChild(el("div",{class:"out"},["Entered (demo only): "+ks.map(k=>k+" = "+entered[k]).join("; ")]))}
  const b=el("button",{class:"pri"},["Start over"]);b.onclick=()=>{idx=0;log=[];entered={};ended=null;err="";render()};c.appendChild(b);sc.appendChild(c);return}
 const i=idx,s=DATA.steps[i],st=STYLE[s.automation]||["#e5e7eb","#6b7280","Step"];
 const c=el("div",{class:"card"});
 c.appendChild(el("div",{class:"muted"},["Step "+(i+1)+" of "+DATA.steps.length+" · "+s.id]));
 c.appendChild(el("h2",{},[s.name]));
 c.appendChild(el("div",{style:"margin:6px 0"},[el("span",{class:"chip",style:"background:#e2e8f0"},["Acting as: "+s.actor]),el("span",{class:"chip",style:"background:"+st[0]+";color:"+st[1]},[st[2]]),...(s.approval?[el("span",{class:"chip",style:"background:#fee2e2;color:#b91c1c"},["Approval required"])]:[])]));
 const prev=producedBefore(i);
 s.inputs.forEach((n,k)=>{
  if(prev.has(n.toLowerCase())){c.appendChild(el("div",{class:"recv"},["Received from earlier step: "+n]));return}
  c.appendChild(el("label",{for:"f"+k},[n]));
  const kind=fieldKind(n);const f=el("input",{id:"f"+k,type:kind==="file"?"file":(kind==="date"?"date":"text")});
  if(kind==="text")f.setAttribute("placeholder","Enter "+n.toLowerCase());c.appendChild(f)});
 if(!s.inputs.length)c.appendChild(el("div",{class:"muted",style:"margin-top:10px"},["No inputs were stated for this step in the source documents."]));
 if(s.outputs.length)c.appendChild(el("div",{class:"out"},["This step produces: "+s.outputs.join(", ")]));
 if(s.automation==="deterministic")c.appendChild(el("div",{class:"muted",style:"margin-top:10px"},["In the proposed design the system performs this step automatically."]));
 if(err)c.appendChild(el("div",{class:"err"},[err]));
 if(s.approval){
  const a=el("button",{class:"ok"},["Approve"]);a.onclick=()=>finishStep(s,i,"approve");
  const w=el("button",{class:"warn"},["Request changes"]);w.onclick=()=>finishStep(s,i,"changes");
  const r=el("button",{class:"bad"},["Reject"]);r.onclick=()=>finishStep(s,i,"reject");
  c.appendChild(a);c.appendChild(w);c.appendChild(r)}
 else{const n=el("button",{class:"pri"},[s.automation==="deterministic"?"Run automated step":"Complete step"]);n.onclick=()=>finishStep(s,i,"ok");c.appendChild(n)}
 if(i>0){const bk=el("button",{class:"ghost"},["Back"]);bk.onclick=()=>{idx=i-1;log.pop();err="";render()};c.appendChild(bk)}
 sc.appendChild(c)}
$("pname").textContent=DATA.name;document.title=DATA.name+" - prototype";renderRules();render();
</script></body></html>
"""


def prototype_html(workflow: Optional[Dict[str, Any]],
                   rules: Optional[List[Dict[str, Any]]] = None) -> Optional[str]:
    wf = normalise(workflow)
    if not wf:
        return None
    rule_items = [
        {"key": str(r.get("rule_key") or ""), "text": str(r.get("description") or "")}
        for r in (rules or [])[:12] if r.get("description")
    ]
    data = {"name": wf["name"], "steps": wf["steps"], "rules": rule_items}
    payload = json.dumps(data, ensure_ascii=False)
    # Keep the JSON safe inside a <script> block.
    payload = payload.replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    return (_PROTOTYPE_TEMPLATE
            .replace("__TITLE__", html.escape(wf["name"]))
            .replace("__DATA__", payload))
