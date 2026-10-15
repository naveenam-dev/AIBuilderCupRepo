"""Run the agent from the terminal: python -m scripts.ask <persona> "<question>"
(AGENT_RUNTIME=adk or native selects the runtime, as in the server.)"""
import asyncio
import json
import sys

from app.config import get_settings
from app.container import build_container


def show(ev: dict) -> None:
    if ev["type"] == "tool_call":
        print(f"-> {ev['name']}({json.dumps(ev['args'])})")
    elif ev["type"] == "tool_result":
        print(f"   <- {ev['preview']}")
    elif ev["type"] == "action_proposed":
        print(f"   [approval needed] {ev['action']['summary']}")
    elif ev["type"] == "sop":
        print(json.dumps(ev["sop"], indent=2))
    else:
        print(f"[{ev['type']}] {ev.get('message', '')}")


async def consume(events) -> None:
    async for ev in events:
        show(ev)


def main() -> None:
    persona, question = sys.argv[1], " ".join(sys.argv[2:])
    c = build_container(get_settings())
    print("ingest:", c.ingest())
    events = c.orchestrator.run(question, c.auth.personas[persona])
    if hasattr(events, "__aiter__"):
        asyncio.run(consume(events))
    else:
        for ev in events:
            show(ev)


if __name__ == "__main__":
    main()
