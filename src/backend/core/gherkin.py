"""Gherkin validation with the official Cucumber parser."""
from __future__ import annotations

from gherkin.parser import Parser


def validate(text: str) -> dict:
    try:
        parsed = Parser().parse(text)
    except Exception as exc:  # the parser raises composite errors with line details in the message
        return {"valid": False, "errors": [str(exc)], "scenarios": 0, "steps": 0, "feature": None}
    feature = parsed.get("feature")
    if not feature:
        return {"valid": False, "errors": ["No Feature found"], "scenarios": 0, "steps": 0, "feature": None}
    scenarios = steps = 0
    errors: list[str] = []

    def walk(children: list[dict]) -> None:
        nonlocal scenarios, steps
        for child in children:
            if "rule" in child:
                walk(child["rule"]["children"])
            elif "scenario" in child:
                scenario = child["scenario"]
                scenarios += 1
                steps += len(scenario["steps"])
                if not scenario["steps"]:
                    errors.append(f"Scenario '{scenario['name']}' has no steps")

    walk(feature["children"])
    if not scenarios:
        errors.append("Feature has no scenarios")
    return {"valid": not errors, "errors": errors, "scenarios": scenarios, "steps": steps, "feature": feature["name"]}
