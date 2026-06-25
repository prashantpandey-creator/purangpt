"""graph_viz — render a MEANINGFUL, self-updating picture of graph_manifest.json.

The full graph (8,755 nodes) is a grey hairball; rendering all of it shows nothing.
This distills a readable view and writes a self-contained D3 HTML you re-run after
any rebuild ("updates as we update" = re-run this one command):

  - the gravitational centres (top-N entities by degree) — the pantheon mass
  - the Kriya LINEAGE spine FORCE-INCLUDED even though it is low-degree (Babaji →
    Lahiri → Tinkori → Satyacharan → Sharma) + the bridge edges that tie it into
    the pantheon, because a view that omitted Guruji would miss the whole point
  - node size = degree, colour = kind, lineage edges highlighted in saffron

Input contract:  run(top_n=48, out_html="", manifest_path="") -> envelope
Output (envelope.data): {n_nodes, n_edges_shown, n_entities_total, n_edges_total,
                         lineage_present, out_html, view:{nodes,links,stats}}
"""
from __future__ import annotations

import collections
import json
import os
import sys
from typing import Any, Dict, List

_BASE = os.path.join(os.path.dirname(__file__), "..", "read_pass", "out")
_MANIFEST = os.path.join(_BASE, "graph_manifest.json")
_OUT = os.path.join(_BASE, "graph_viz.html")

# The Kriya lineage spine — force-included regardless of degree (it is the heart).
_LINEAGE = ["babaji", "mahavatar babaji", "lahiri mahasaya", "tinkori lahiri",
            "satyacharan lahiri", "shailendra sharma"]

# Structural predicates worth drawing (keeps the induced edge set readable).
_STRUCTURAL = {"father", "son", "mother", "daughter", "husband", "wife", "brother",
               "avatar", "incarnation", "guru", "guru_of", "disciple", "teaches",
               "killed", "kills", "fights", "born_from", "founder"}


def _envelope(success, data, metadata, errors):
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


def distill(manifest: Dict[str, Any], top_n: int = 48) -> Dict[str, Any]:
    """Pick the readable subgraph: top-degree centres + lineage spine + bridges."""
    ents = {e["id"]: e for e in manifest["entities"]}
    deg = collections.Counter()
    for e in manifest["edges"]:
        deg[e["src"]] += 1
        deg[e["dst"]] += 1

    keep = {eid for eid, _ in deg.most_common(top_n)}
    # force-include the lineage spine that actually exists in the graph
    lineage_present = [lid for lid in _LINEAGE if lid in ents]
    keep.update(lineage_present)
    # one-hop bridges FROM the lineage into whatever it connects to (so the thread
    # is not a floating island) — keeps the Babaji→Shankaracharya tie visible
    for e in manifest["edges"]:
        if e["src"] in lineage_present and e["dst"] in ents:
            keep.add(e["dst"])
        if e["dst"] in lineage_present and e["src"] in ents:
            keep.add(e["src"])

    lineage_set = set(lineage_present)
    nodes = []
    for eid in keep:
        e = ents.get(eid)
        if not e:
            continue
        nodes.append({
            "id": eid,
            "name": e.get("name", eid),
            "kind": e.get("kind", "") or "other",
            "deg": deg.get(eid, 0),
            "lineage": eid in lineage_set,
        })

    seen = set()
    links = []
    for e in manifest["edges"]:
        s, t, r = e["src"], e["dst"], (e.get("rel") or "")
        if s not in keep or t not in keep or s == t:
            continue
        is_lineage = s in lineage_set or t in lineage_set
        # draw structural edges, plus ALL edges touching the lineage (so the spine
        # reads in full even for non-structural predicates)
        if r not in _STRUCTURAL and not is_lineage:
            continue
        k = (s, t, r)
        if k in seen:
            continue
        seen.add(k)
        links.append({"s": s, "t": t, "r": r, "lineage": is_lineage})

    rels = collections.Counter(str(e.get("rel", "")) for e in manifest["edges"])
    kinds = collections.Counter(n["kind"] for n in nodes)
    stats = {
        "n_entities_total": len(manifest["entities"]),
        "n_edges_total": len(manifest["edges"]),
        "top_predicates": rels.most_common(8),
        "kinds_in_view": dict(kinds),
        "lineage_present": lineage_present,
    }
    return {"nodes": nodes, "links": links, "stats": stats}


# kind → colour (mystical dark theme; saffron reserved for the lineage)
_KIND_COLORS = {
    "deity": "#7c6fe0", "king": "#3b82c4", "queen": "#c9608f", "sage": "#1d9e75",
    "demon": "#d85a30", "concept": "#888780", "place": "#ba7517", "practice": "#0fb5a5",
    "text": "#b06fd0", "other": "#6b6a66",
}


def _html(view: Dict[str, Any]) -> str:
    payload = json.dumps(view, ensure_ascii=False)
    colors = json.dumps(_KIND_COLORS)
    s = view["stats"]
    legend = "".join(
        f'<span style="display:inline-flex;align-items:center;gap:5px;margin-right:14px">'
        f'<i style="width:10px;height:10px;border-radius:50%;background:{c};display:inline-block"></i>{k}</span>'
        for k, c in _KIND_COLORS.items() if k in s["kinds_in_view"]
    )
    return """<!DOCTYPE html><html><head><meta charset="utf-8">
<title>PuranGPT Knowledge Graph</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.5/d3.min.js"></script>
<style>
 html,body{margin:0;background:#0d0b1a;color:#e8e4f0;font-family:-apple-system,Segoe UI,Roboto,sans-serif;overflow:hidden}
 #hud{position:fixed;top:14px;left:16px;z-index:10;font-size:13px;line-height:1.6;max-width:300px}
 #hud h1{font-size:15px;font-weight:500;margin:0 0 6px;color:#ff9933}
 #hud .stat{color:#a99fc0}
 #hud b{color:#d4af37;font-weight:500}
 #legend{position:fixed;bottom:12px;left:16px;z-index:10;font-size:12px;color:#a99fc0}
 .ttip{position:fixed;pointer-events:none;background:#1a1730;border:1px solid #3a3358;border-radius:6px;
   padding:6px 9px;font-size:12px;color:#e8e4f0;z-index:20;opacity:0;transition:opacity .12s}
 text{font-family:inherit;pointer-events:none;text-shadow:0 1px 3px #0d0b1a}
</style></head><body>
<div id="hud"><h1>PuranGPT — the graph mind</h1>
 <div class="stat"><b>__NENT__</b> entities · <b>__NEDG__</b> edges total</div>
 <div class="stat">showing <b>__NSHOW__</b> centres + lineage</div>
 <div class="stat">lineage: __LIN__</div>
</div>
<div id="legend">__LEGEND__</div>
<div class="ttip" id="tt"></div>
<svg id="svg"></svg>
<script>
const VIEW=__PAYLOAD__, COLORS=__COLORS__;
const W=window.innerWidth,H=window.innerHeight;
const svg=d3.select("#svg").attr("width",W).attr("height",H);
const g=svg.append("g");
svg.call(d3.zoom().scaleExtent([0.2,4]).on("zoom",e=>g.attr("transform",e.transform)));
const nodes=VIEW.nodes.map(d=>({...d})), links=VIEW.links.map(d=>({source:d.s,target:d.t,...d}));
const maxDeg=d3.max(nodes,d=>d.deg)||1;
const R=d=>d.lineage?11:(6+18*Math.sqrt(d.deg/maxDeg));
const sim=d3.forceSimulation(nodes)
 .force("link",d3.forceLink(links).id(d=>d.id).distance(l=>l.lineage?70:120).strength(l=>l.lineage?0.9:0.25))
 .force("charge",d3.forceManyBody().strength(-260))
 .force("center",d3.forceCenter(W/2,H/2))
 .force("collide",d3.forceCollide().radius(d=>R(d)+6));
const link=g.append("g").selectAll("line").data(links).join("line")
 .attr("stroke",l=>l.lineage?"#ff9933":"#4a4470")
 .attr("stroke-width",l=>l.lineage?2.2:0.8)
 .attr("stroke-opacity",l=>l.lineage?0.95:0.35);
const node=g.append("g").selectAll("circle").data(nodes).join("circle")
 .attr("r",R).attr("fill",d=>d.lineage?"#ff9933":(COLORS[d.kind]||"#6b6a66"))
 .attr("stroke",d=>d.lineage?"#ffd089":"#0d0b1a").attr("stroke-width",d=>d.lineage?2:1.2)
 .style("cursor","pointer").call(drag(sim));
const label=g.append("g").selectAll("text").data(nodes.filter(d=>d.lineage||d.deg>maxDeg*0.18)).join("text")
 .text(d=>d.name).attr("font-size",d=>d.lineage?13:11)
 .attr("fill",d=>d.lineage?"#ffd089":"#cfc8e0").attr("dx",d=>R(d)+3).attr("dy",4);
const tt=d3.select("#tt");
node.on("mousemove",(e,d)=>tt.style("opacity",1).style("left",(e.clientX+12)+"px").style("top",(e.clientY+12)+"px")
   .html(`<b style="color:#ff9933">${d.name}</b><br>${d.kind} · ${d.deg} edges`))
 .on("mouseleave",()=>tt.style("opacity",0));
sim.on("tick",()=>{
 link.attr("x1",l=>l.source.x).attr("y1",l=>l.source.y).attr("x2",l=>l.target.x).attr("y2",l=>l.target.y);
 node.attr("cx",d=>d.x).attr("cy",d=>d.y);
 label.attr("x",d=>d.x).attr("y",d=>d.y);
});
function drag(sim){return d3.drag()
 .on("start",(e,d)=>{if(!e.active)sim.alphaTarget(0.3).restart();d.fx=d.x;d.fy=d.y;})
 .on("drag",(e,d)=>{d.fx=e.x;d.fy=e.y;})
 .on("end",(e,d)=>{if(!e.active)sim.alphaTarget(0);d.fx=null;d.fy=null;});}
</script></body></html>""" \
        .replace("__PAYLOAD__", payload).replace("__COLORS__", colors) \
        .replace("__NENT__", f"{s['n_entities_total']:,}").replace("__NEDG__", f"{s['n_edges_total']:,}") \
        .replace("__NSHOW__", str(len(view["nodes"]))).replace("__LEGEND__", legend) \
        .replace("__LIN__", " → ".join(view["stats"]["lineage_present"]) or "(none)")


def run(top_n: int = 48, out_html: str = "", manifest_path: str = "") -> Dict[str, Any]:
    manifest_path = manifest_path or os.path.abspath(_MANIFEST)
    out_html = out_html or os.path.abspath(_OUT)
    metadata = {"manifest_path": manifest_path, "out_html": out_html, "top_n": top_n}

    if not os.path.isfile(manifest_path):
        return _envelope(False, None, metadata,
                         [{"code": "missing_manifest", "message": f"not found: {manifest_path}"}])
    with open(manifest_path) as f:
        manifest = json.load(f)
    if not manifest.get("entities"):
        return _envelope(False, None, metadata,
                         [{"code": "empty_graph", "message": "manifest has no entities"}])

    view = distill(manifest, top_n=top_n)
    with open(out_html, "w") as f:
        f.write(_html(view))

    data = {
        "n_nodes": len(view["nodes"]),
        "n_edges_shown": len(view["links"]),
        "n_entities_total": view["stats"]["n_entities_total"],
        "n_edges_total": view["stats"]["n_edges_total"],
        "lineage_present": view["stats"]["lineage_present"],
        "out_html": out_html,
        "view": view,
    }
    return _envelope(True, data, metadata, [])


def main(argv: List[str]) -> int:
    as_json = "--json" in argv
    top_n = 48
    if "--top" in argv:
        top_n = int(argv[argv.index("--top") + 1])
    env = run(top_n=top_n)
    if as_json:
        # the view can be large; by default print without it unless --full
        out = dict(env)
        if "--full" not in argv and env.get("data"):
            out = json.loads(json.dumps(env))
            out["data"].pop("view", None)
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        if not env["success"]:
            print(f"ERROR: {env['errors'][0]['message']}")
            return 2
        d = env["data"]
        print("=== GRAPH VIZ GENERATED ===")
        print(f"Nodes shown: {d['n_nodes']} (of {d['n_entities_total']:,})")
        print(f"Edges shown: {d['n_edges_shown']} (of {d['n_edges_total']:,})")
        print(f"Lineage present: {' → '.join(d['lineage_present'])}")
        print(f"Open: {d['out_html']}")
    return 0 if env["success"] else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
