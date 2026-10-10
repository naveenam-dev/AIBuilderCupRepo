"""Post-generation verification: every citation must point at evidence this user actually retrieved
in this run (RBAC-filtered chunks or live tool calls). Unsupported claims are flagged, not shown as fact."""
from typing import Any

from app.tools.base import ToolContext


def verify_sop(sop: dict[str, Any], ctx: ToolContext, proposed_action_ids: set[str]) -> dict[str, Any]:
    steps_out, dropped = [], []
    for step in sop.get("steps", []):
        valid = []
        for cid in step.get("citations", []):
            if cid in ctx.citable_chunks or (cid.startswith("tool:") and cid[5:] in ctx.tools_called):
                valid.append(cid)
            else:
                dropped.append(cid)
        steps_out.append(
            {
                **step,
                "citations": valid,
                "action_ids": [a for a in step.get("action_ids", []) if a in proposed_action_ids],
                "grounded": bool(valid),
            }
        )

    grounded = sum(s["grounded"] for s in steps_out)
    confidence = sop.get("confidence", "low")
    if not ctx.citable_chunks or (steps_out and grounded < len(steps_out) / 2):
        confidence = "low"

    cited_chunk_ids = {c for s in steps_out for c in s["citations"] if not c.startswith("tool:")}
    sources = [
        {"chunk_id": cid, "doc_id": ch.doc_id, "title": ch.title, "source": ch.source, "url": ch.url,
         "excerpt": ch.text[:400]}
        for cid, ch in ctx.citable_chunks.items()
        if cid in cited_chunk_ids
    ]
    return {
        **sop,
        "steps": steps_out,
        "confidence": confidence,
        "gaps": sop.get("gaps", []),
        "sources": sources,
        "verification": {
            "steps_total": len(steps_out),
            "steps_grounded": grounded,
            "dropped_citations": dropped,
            "documents_retrieved": len({c.doc_id for c in ctx.citable_chunks.values()}),
        },
    }
