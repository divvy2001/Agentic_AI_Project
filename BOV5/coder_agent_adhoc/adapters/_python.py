"""Shared T3 interpretation for the Python renderers (terminal and pygame)."""
import json
import re


def observation(result):
    found = re.findall(r'CODER_OBSERVED:(\{[^\n]*\})', result.get('output', ''))
    return json.loads(found[-1]) if found else {}
