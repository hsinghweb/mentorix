import json
import re


def parse_llm_json(text: str):
    if not text:
        return {}
    candidate = text.strip()
    try:
        return json.loads(candidate)
    except Exception:
        pass

    # Extract first JSON object/array if model wrapped content in prose.
    match = re.search(r"(\{.*\}|\[.*\])", candidate, re.DOTALL)
    if not match:
        return {}
    snippet = match.group(1)
    try:
        return json.loads(snippet)
    except Exception:
        return {}
