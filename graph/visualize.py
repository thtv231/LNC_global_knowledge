"""
Generate an interactive HTML graph visualization using pyvis.
Samples up to 20 chunks per category + all Category/Site nodes.
Color: blue=USA, red=Canada, orange=Category, purple=Site
Edge: gray=SIMILAR_TO, orange=BELONGS_TO, purple=FROM_SITE
"""
from __future__ import annotations
import os
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase
from pyvis.network import Network

load_dotenv()

CHUNKS_PER_CAT = 20
OUT_FILE = "graph_viz.html"

# Node colors
C_USA       = "#4A90D9"
C_CANADA    = "#E85D4A"
C_NEWZEALAND= "#22C55E"
C_CATEGORY  = "#F5A623"
C_SITE      = "#A855F7"

# Edge colors
E_SIMILAR  = "#6B7280"
E_BELONGS  = "#F5A62388"
E_SITE     = "#A855F744"


def _country_color(country: str) -> str:
    if country == "usa":
        return C_USA
    if country == "newzealand":
        return C_NEWZEALAND
    return C_CANADA


def main() -> None:
    driver = GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]),
    )

    net = Network(
        height="820px", width="100%",
        bgcolor="#0f172a", font_color="#e2e8f0",
        directed=False,
        cdn_resources="in_line",   # embed JS → works on any device, no internet needed
    )

    added: set[str] = set()

    with driver.session() as s:
        # ── 1. Category nodes ─────────────────────────────────────────────
        cats = s.run("MATCH (c:Category) RETURN c.name AS name, c.country AS country").data()
        for c in cats:
            nid = f"cat|{c['name']}"
            net.add_node(nid, label=c["name"], color=C_CATEGORY,
                         size=38, shape="diamond",
                         title=f"<b>Category:</b> {c['name']}<br/><b>Country:</b> {c['country']}")
            added.add(nid)

        # ── 2. Site nodes ─────────────────────────────────────────────────
        sites = s.run("MATCH (s:Site) RETURN s.name AS name").data()
        for s_ in sites:
            nid = f"site|{s_['name']}"
            net.add_node(nid, label=s_["name"], color=C_SITE,
                         size=44, shape="star",
                         title=f"<b>Site:</b> {s_['name']}")
            added.add(nid)

        # ── 3. Sample KnowledgeChunk nodes (top N per category) ───────────
        chunks = s.run("""
            MATCH (c:KnowledgeChunk)
            WITH c.category AS cat, collect(c) AS all_chunks
            UNWIND all_chunks[0..$n] AS chunk
            RETURN chunk.chunk_id  AS chunk_id,
                   chunk.title     AS title,
                   chunk.category  AS category,
                   chunk.country   AS country,
                   chunk.content   AS content,
                   chunk.site      AS site
        """, n=CHUNKS_PER_CAT).data()

        sampled: set[str] = set()
        for ch in chunks:
            cid = ch["chunk_id"]
            sampled.add(cid)
            label = (ch["title"] or cid)[:28]
            preview = (ch["content"] or "")[:150].replace("<", "&lt;")
            tooltip = (
                f"<b>{(ch['title'] or '')[:60]}</b><br/>"
                f"<i>{ch['category']} | {(ch['country'] or '').upper()}</i><br/>"
                f"{preview}…"
            )
            net.add_node(
                cid, label=label,
                color=_country_color(ch["country"] or ""),
                size=10, shape="dot", title=tooltip,
            )
            added.add(cid)

        # ── 4. BELONGS_TO edges ───────────────────────────────────────────
        for ch in chunks:
            cat_nid = f"cat|{ch['category']}"
            if cat_nid in added:
                net.add_edge(ch["chunk_id"], cat_nid, color=E_BELONGS, width=1)

        # ── 5. FROM_SITE edges ────────────────────────────────────────────
        site_rels = s.run("""
            MATCH (c:KnowledgeChunk)-[:FROM_SITE]->(st:Site)
            WHERE c.chunk_id IN $ids
            RETURN c.chunk_id AS cid, st.name AS site
        """, ids=list(sampled)).data()
        for r in site_rels:
            site_nid = f"site|{r['site']}"
            if site_nid in added:
                net.add_edge(r["cid"], site_nid, color=E_SITE, width=1)

        # ── 6. SIMILAR_TO edges (only between sampled nodes) ─────────────
        sim_rels = s.run("""
            MATCH (a:KnowledgeChunk)-[r:SIMILAR_TO]->(b:KnowledgeChunk)
            WHERE a.chunk_id IN $ids AND b.chunk_id IN $ids
            RETURN a.chunk_id AS src, b.chunk_id AS dst, r.score AS score
        """, ids=list(sampled)).data()
        for r in sim_rels:
            net.add_edge(
                r["src"], r["dst"],
                color=E_SIMILAR, width=1,
                title=f"similarity: {r['score']}",
            )

    driver.close()

    node_count = len([n for n in added])
    print(f"Nodes: {node_count} | SIMILAR_TO edges: {len(sim_rels)} | "
          f"BELONGS_TO: {len(chunks)} | FROM_SITE: {len(site_rels)}")

    # ── Physics & interaction options ─────────────────────────────────────
    net.set_options("""{
      "physics": {
        "barnesHut": {
          "gravitationalConstant": -9000,
          "centralGravity": 0.25,
          "springLength": 130,
          "springConstant": 0.035,
          "damping": 0.12
        },
        "stabilization": { "iterations": 200 }
      },
      "interaction": {
        "hover": true,
        "tooltipDelay": 80,
        "navigationButtons": true,
        "keyboard": true
      },
      "nodes": { "borderWidth": 0, "shadow": true },
      "edges": { "smooth": { "type": "continuous" }, "shadow": false }
    }""")

    out = Path(OUT_FILE)
    out.write_text(net.generate_html(), encoding="utf-8")

    # ── Inject legend into HTML ───────────────────────────────────────────
    legend_html = """
<div style="position:fixed;top:12px;left:12px;background:#1e293b;border:1px solid #334155;
     border-radius:10px;padding:14px 18px;font-family:sans-serif;font-size:13px;
     color:#e2e8f0;z-index:9999;min-width:170px">
  <div style="font-weight:700;margin-bottom:10px;font-size:14px">Legend</div>
  <div><span style="display:inline-block;width:13px;height:13px;border-radius:50%;
       background:#4A90D9;margin-right:8px"></span>Chunk — USA</div>
  <div style="margin-top:5px"><span style="display:inline-block;width:13px;height:13px;
       border-radius:50%;background:#E85D4A;margin-right:8px"></span>Chunk — Canada</div>
  <div style="margin-top:5px"><span style="display:inline-block;width:13px;height:13px;
       border-radius:50%;background:#22C55E;margin-right:8px"></span>Chunk — New Zealand</div>
  <div style="margin-top:5px"><span style="display:inline-block;width:13px;height:13px;
       transform:rotate(45deg);background:#F5A623;margin-right:8px"></span>Category</div>
  <div style="margin-top:5px"><span style="display:inline-block;width:13px;height:13px;
       background:#A855F7;margin-right:8px;clip-path:polygon(50% 0%,61% 35%,98% 35%,
       68% 57%,79% 91%,50% 70%,21% 91%,32% 57%,2% 35%,39% 35%)"></span>Site</div>
  <hr style="border-color:#334155;margin:10px 0"/>
  <div style="color:#94a3b8;font-size:11px">Drag to explore<br/>Scroll to zoom<br/>Hover for details</div>
</div>
"""
    html = out.read_text(encoding="utf-8")
    html = html.replace("</body>", legend_html + "\n</body>")
    out.write_text(html, encoding="utf-8")

    print(f"\nSaved: {out.resolve()}")
    print("Open this file in Chrome/Edge to explore the graph.")


if __name__ == "__main__":
    main()
