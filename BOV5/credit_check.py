"""
check_credits.py: show OpenRouter credit for every key in .env (free, makes no model calls).

Run from the project folder:  python check_credits.py
"""
import json
import os
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
KEYS = ["PLANNER_OPENROUTER_API_KEY", "ASSET_OPENROUTER_API_KEY", "CODER_OPENROUTER_API_KEY", "OPENROUTER_API_KEY"]
WARN_BELOW = 1.00  # USD


def load_env():
    env = ROOT / ".env"
    if not env.exists():
        print(f"No .env found at {env}")
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def get(url, key):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode()).get("data", {})


def main():
    load_env()
    seen = {}
    rows = []
    for name in KEYS:
        key = os.getenv(name, "").strip()
        if not key:
            continue
        if key in seen:
            rows.append((name, f"same key as {seen[key]}", "", "", ""))
            continue
        seen[key] = name
        try:
            d = get("https://openrouter.ai/api/v1/auth/key", key)
            used = d.get("usage") or 0
            limit = d.get("limit")
            left = None if limit is None else limit - used
            try:  # account balance (may be refused for some key types)
                c = get("https://openrouter.ai/api/v1/credits", key)
                acct = f"${c.get('total_credits', 0) - c.get('total_usage', 0):.2f}"
            except Exception:
                acct = "n/a"
            flag = "LOW" if (left is not None and left < WARN_BELOW) else "OK"
            rows.append((name, f"${used:.2f}", "no limit" if limit is None else f"${left:.2f} of ${limit:.2f}", acct, flag))
        except urllib.error.HTTPError as e:
            rows.append((name, "", "", "", f"HTTP {e.code} (bad or disabled key)"))
        except Exception as e:
            rows.append((name, "", "", "", f"error: {e}"))

    if not rows:
        print("No OpenRouter keys found in .env")
        return
    head = ("Key", "Used", "Key limit left", "Account balance", "Status")
    w = [max(len(str(r[i])) for r in rows + [head]) for i in range(5)]
    print()
    for r in [head, tuple("-" * x for x in w)] + rows:
        print("  ".join(str(c).ljust(w[i]) for i, c in enumerate(r)))
    print("\nLOW = under $%.2f left on that key's limit. Top up at https://openrouter.ai/settings/credits" % WARN_BELOW)


if __name__ == "__main__":
    main()