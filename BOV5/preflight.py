"""
preflight.py: free system check before running test.py.

Run from VS Code (Run button) or:  python preflight.py
Optional:                           python preflight.py --unit   (also runs the 153 offline tests, ~6 min)

Makes no paid model calls. The only network call is OpenRouter's free key-status endpoint.
"""
import importlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

results = []  # (status, check, detail)


def ok(check, detail=""):   results.append(("PASS", check, detail))
def warn(check, detail=""): results.append(("WARN", check, detail))
def bad(check, detail=""):  results.append(("FAIL", check, detail))


# 1. Python and environment ---------------------------------------------------
v = sys.version_info
(ok if v >= (3, 10) else bad)("Python version", f"{v.major}.{v.minor}.{v.micro} (need 3.10+, tested 3.11)")
exe = sys.executable
if "pe6203-logic-coder" in exe:
    ok("Conda env", exe)
else:
    warn("Conda env", f"{exe}: not the pe6203-logic-coder env. Select it as the VS Code interpreter.")

# 2. Project layout -------------------------------------------------------------
need = ["test.py", "coder_agent_adhoc", "master_planner", "tests_coder", "plans", "traces"]
missing = [n for n in need if not (ROOT / n).exists()]
(bad if missing else ok)("Project folder", f"missing: {missing}" if missing else str(ROOT))

# 3. OS / sandbox ---------------------------------------------------------------
if platform.system() == "Windows":
    ok("Operating system", f"Windows {platform.release()} (AppContainer sandbox needs Windows)")
else:
    bad("Operating system", f"{platform.system()}: her native checks need Windows; the coder will block")

# 4. Packages -------------------------------------------------------------------
reqs = []
for f in ("requirements.txt", "requirements-coder.txt"):
    p = ROOT / f
    if p.exists():
        reqs += [l.strip() for l in p.read_text().splitlines() if l.strip() and not l.startswith(("#", "-r"))]
import importlib.metadata as md
bad_pk = []
for r in reqs:
    name, _, want = r.partition("==")
    try:
        have = md.version(name)
        if want and have != want:
            bad_pk.append(f"{name} {have} (pinned {want})")
    except md.PackageNotFoundError:
        bad_pk.append(f"{name} NOT INSTALLED")
if not reqs:
    warn("Packages", "requirements files not found")
elif any("NOT INSTALLED" in b for b in bad_pk):
    bad("Packages", "; ".join(bad_pk) + "  → pip install -r requirements.txt")
elif bad_pk:
    warn("Packages", "version differs: " + "; ".join(bad_pk))
else:
    ok("Packages", f"{len(reqs)} pinned packages match")

# 4b. LangChain runtime actually works (catches a leftover `langchain` package clashing
#     with the pinned langchain-core: "module 'langchain' has no attribute 'verbose'")
try:
    from langchain_core.globals import get_verbose
    get_verbose()
    from langchain_openai import ChatOpenAI
    ChatOpenAI(model="x", api_key="sk-test", base_url="https://openrouter.ai/api/v1")
    ok("LangChain runtime", "langchain-core and langchain-openai initialise")
except Exception as e:
    try:
        stray = md.version("langchain")
        hint = f"stray `langchain` {stray} installed → pip uninstall langchain (or use the conda env)"
    except md.PackageNotFoundError:
        hint = "reinstall: pip install -r requirements.txt"
    bad("LangChain runtime", f"{type(e).__name__}: {e}  → {hint}")

# 4c. Folders the pipeline expects
for d in ("game", "game/assets", "plans", "traces"):
    (ROOT / d).mkdir(parents=True, exist_ok=True)

# 5. Module imports -------------------------------------------------------------
mods = sorted({f"coder_agent_adhoc.{p.stem}" for p in (ROOT / "coder_agent_adhoc").glob("*.py")
               if p.stem != "__init__" and not p.stem.endswith("_child")}  # *_child.py run on import
              | {"master_planner.run", "master_planner.planner.call_planner", "master_planner.asset.planner"})
fails = []
for m in mods:
    try:
        importlib.import_module(m)
    except Exception as e:
        if platform.system() != "Windows" and "win" in str(e).lower():
            continue  # Windows-only module on a non-Windows machine
        fails.append(f"{m}: {type(e).__name__}: {e}")
(bad if fails else ok)("Module imports", "\n      ".join(fails) if fails else f"{len(mods)} modules import cleanly")

# 6. .env keys ------------------------------------------------------------------
env_file = ROOT / ".env"
if not env_file.exists():
    alt = [p.name for p in ROOT.glob(".env*")]
    bad(".env file", f"not found next to test.py (found: {alt})  → copy .env.example to .env")
else:
    try:
        from dotenv import load_dotenv
        load_dotenv(env_file, override=True)
    except Exception:
        pass
    ok(".env file", str(env_file))
keys = ["PLANNER_OPENROUTER_API_KEY", "ASSET_OPENROUTER_API_KEY", "CODER_OPENROUTER_API_KEY"]
for k in keys:
    val = os.getenv(k, "").strip().strip('"').strip("'")
    if not val:
        bad(k, "empty or missing")
    elif not val.startswith("sk-or-"):
        warn(k, f"set ({len(val)} chars) but doesn't look like an OpenRouter key (sk-or-...)")
    else:
        ok(k, f"set (…{val[-4:]})")

# 7. Key validity + credit (free endpoint) ----------------------------------------
seen = {}
for k in keys:
    val = os.getenv(k, "").strip().strip('"').strip("'")
    if not val or val in seen:
        continue
    seen[val] = k
    try:
        import httpx
        r = httpx.get("https://openrouter.ai/api/v1/auth/key",
                      headers={"Authorization": f"Bearer {val}"}, timeout=15)
        if r.status_code == 200:
            d = r.json().get("data", {})
            limit = d.get("limit")
            used = d.get("usage", 0) or 0
            left = "no limit" if limit is None else f"${limit - used:.2f} left of ${limit:.2f}"
            ok(f"OpenRouter key ({k})", f"valid, used ${used:.2f}, {left}")
        else:
            bad(f"OpenRouter key ({k})", f"HTTP {r.status_code}: {r.text[:120]}")
    except Exception as e:
        warn(f"OpenRouter key ({k})", f"could not reach OpenRouter: {e}")

# 8. Godot ----------------------------------------------------------------------
gb = os.getenv("GODOT_BINARY", "").strip().strip('"')
if not gb:
    warn("GODOT_BINARY", "not set (only needed for Godot games)")
elif not Path(gb).is_file():
    bad("GODOT_BINARY", f"file not found: {gb}")
else:
    try:
        out = subprocess.run([gb, "--headless", "--version"], capture_output=True, text=True, timeout=60)
        ver = (out.stdout or out.stderr).strip().splitlines()[-1] if (out.stdout or out.stderr) else "?"
        (ok if ver.startswith("4.") else warn)("GODOT_BINARY", f"{ver} at {gb}")
    except Exception as e:
        bad("GODOT_BINARY", f"failed to run: {e}")

# 9. Coder config ---------------------------------------------------------------
try:
    from coder_agent_adhoc.configuration import config as C
    ok("Coder config", f"model={C.AGENT_MODEL}, max_steps={C.CODER_MAX_STEPS}")
except Exception as e:
    bad("Coder config", f"{type(e).__name__}: {e}")

# 10. Leftover plan/manifest from a previous run ----------------------------------------
man = ROOT / "plans" / "asset_manifest.json"
if man.exists():
    try:
        m = json.loads(man.read_text(encoding="utf-8"))
        abs_paths = [a.get("id") for a in m.get("assets", [])
                     if isinstance(a, dict) and (":" in str(a.get("path", "")) or str(a.get("path", "")).startswith("/"))]
        if abs_paths:
            bad("Asset manifest paths", f"absolute paths for {abs_paths}: coder will block with unsafe_path. "
                "Apply the planner.py path fix (or edit the manifest to start at game/).")
        else:
            ok("Asset manifest paths", f"{len(m.get('assets', []))} asset paths are relative")
    except Exception as e:
        warn("Asset manifest", f"unreadable: {e}")
else:
    ok("Asset manifest paths", "no leftover manifest (fresh run)")

try:
    src = (ROOT / "master_planner" / "asset" / "planner.py").read_text(encoding="utf-8")
    if "relative_to(Path(__file__).resolve().parents[2])" in src:
        ok("Asset path fix", "planner.py stores relative paths")
    else:
        warn("Asset path fix", "planner.py not patched: AI-art runs will hit unsafe_path again")
except Exception:
    pass

# 11. Optional offline unit tests -------------------------------------------------
if "--unit" in sys.argv:
    print("Running offline test suite (about 6 minutes)...")
    r = subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests_coder", "-p", "test_*.py"],
                       capture_output=True, text=True)
    tail = (r.stderr or "").strip().splitlines()[-3:]
    (ok if r.returncode == 0 else bad)("Offline test suite", " | ".join(tail))

# Report ------------------------------------------------------------------------
w = max(len(c) for _, c, _ in results)
print("\n" + "=" * 72 + "\nPREFLIGHT\n" + "=" * 72)
for s, c, d in results:
    print(f"[{s}] {c.ljust(w)}  {d}")
n_fail = sum(1 for s, _, _ in results if s == "FAIL")
n_warn = sum(1 for s, _, _ in results if s == "WARN")
print("=" * 72)
print("READY: run test.py" if n_fail == 0 else f"NOT READY: fix the {n_fail} FAIL line(s) first",
      f"({n_warn} warning(s))" if n_warn else "")
sys.exit(1 if n_fail else 0)
