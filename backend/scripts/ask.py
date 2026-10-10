"""Run the agent from the terminal: python -m scripts.ask <persona> "<question>" """
import json
import sys

from app.config import get_settings
from app.container import build_container


def main() -> None:
    persona, question = sys.argv[1], " ".join(sys.argv[2:])
    c = build_container(get_settings())
    print("ingest:", c.ingest())
    user = c.auth.personas[persona]
    for ev in c.orchestrator.run(question, user):
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


if __name__ == "__main__":
    main()
