from __future__ import annotations
import argparse, hashlib, json, os, re, shlex, subprocess, sys, threading, time
from datetime import datetime, timezone
from pathlib import Path

ACTIONS = {"press", "key_down", "key_up", "wait", "click", "observe", "restart", "input"}
RENDERERS = {"terminal", "pygame", "godot"}

def now():
    return datetime.now(timezone.utc).isoformat()

def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

def read_suite(path):
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict) or not isinstance(obj.get("tests"), list):
        raise ValueError("suite.json must contain a tests array")
    obj["renderer"] = str(obj.get("renderer", "")).lower()
    if obj["renderer"] not in RENDERERS:
        raise ValueError(f"Unsupported renderer: {obj['renderer']}")
    return obj

def gui():
    try:
        import pyautogui
        pyautogui.FAILSAFE = True
        return pyautogui
    except Exception:
        return None

def classify(text, actions):
    hints = []
    patterns = {
      "asset": [r"failed to load", r"resource.*not found", r"missing (asset|texture|sprite|font|audio)", r"cannot open.*\\.(png|jpg|wav|ogg|ttf)"],
      "mechanic": [r"traceback", r"exception", r"error:", r"null instance", r"invalid get index", r"assertionerror", r"collision", r"physics"],
      "planner": [r"requirement.*missing", r"not implemented", r"unsupported feature"]
    }
    low = text.lower()
    for cat, pats in patterns.items():
        matched = [p for p in pats if re.search(p, low, re.I)]
        if matched:
            hints.append({"category": cat, "confidence": "low", "reason": "Runtime text matched: " + ", ".join(matched[:3])})
    unsupported = [a for a in actions if a.get("status") == "unsupported"]
    if unsupported:
        hints.append({"category":"test_harness_or_integration","confidence":"high","reason":f"{len(unsupported)} action(s) were not executed; do not attribute to the game yet."})
    if not hints:
        hints.append({"category":"undetermined","confidence":"low","reason":"Insufficient diagnostic signals; compare brief, plan, code, assets and runtime evidence."})
    return hints

def assert_observation(expected, method, text, error=None):
    if error:
        return "BLOCKED", error
    if method == "manual_inspection" or method not in {"stdout", "log", "screen_text"}:
        return "NEEDS_REVIEW", "This observation needs a renderer-specific assertion or human review."
    if not text.strip():
        return "INCONCLUSIVE", "No process output captured; expected behavior cannot be checked."
    if expected.strip().lower() in text.lower():
        return "PASS", "Expected literal text was found in process output."
    return "FAIL", "Expected literal text was not found. This does not by itself prove a game defect."

def focus_process_window(pid):
    """FIX (focus): bring the game's own window to the front so key presses reach it. Windows only; returns True if focused."""
    if os.name != "nt" or not pid:
        return False
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        found = []
        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def each(hwnd, _):
            owner = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
            if owner.value == pid and user32.IsWindowVisible(hwnd):
                found.append(hwnd)
            return True
        user32.EnumWindows(each, 0)
        if not found:
            return False
        hwnd = found[0]
        user32.keybd_event(0x12, 0, 0, 0)        # tap Alt: Windows only lets a process steal focus right after input
        user32.keybd_event(0x12, 0, 2, 0)
        user32.ShowWindow(hwnd, 9)               # SW_RESTORE
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.2)
        return user32.GetForegroundWindow() == hwnd
    except Exception:
        return False

def win_key(key, down=True, up=True):
    """FIX (scan codes): send a real key event with its hardware scan code (Windows).
    pyautogui sends arrow keys without a scan code, which games that read physical keys (Godot physical_keycode) ignore."""
    if os.name != "nt":
        return False
    try:
        import ctypes
        import pyautogui._pyautogui_win as pw
        vk = pw.keyboardMapping.get(str(key).lower())
        if vk is None:
            return False
        user32 = ctypes.windll.user32
        scan = user32.MapVirtualKeyW(vk & 0xFF, 0)
        ext = 0x0001 if (vk & 0xFF) in (0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E) else 0  # arrows, home/end, ins/del
        if down:
            user32.keybd_event(vk & 0xFF, scan, ext, 0)
        if down and up:
            time.sleep(0.08)   # hold long enough for a game polling once per frame to see it
        if up:
            user32.keybd_event(vk & 0xFF, scan, ext | 0x0002, 0)
        return True
    except Exception:
        return False

class Session:
    def __init__(self, root, renderer, command, evidence):
        self.root, self.renderer, self.command, self.evidence = root, renderer, command, evidence
        self.pg = gui() if renderer != "terminal" else None
        self.proc = None
        self.out, self.err = [], []
    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try: self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None
    def start(self):
        self.stop()
        self.out, self.err = [], []
        args = [a.strip('"') for a in shlex.split(self.command, posix=(os.name != "nt"))]
        if not args: raise ValueError("Empty launch command")
        self.proc = subprocess.Popen(args, cwd=str(self.root),
            stdin=subprocess.PIPE if self.renderer == "terminal" else subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            encoding="utf-8", errors="replace", bufsize=1,
            creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0))
        def drain(stream, bucket):
            try:
                for line in iter(stream.readline, ""): bucket.append(line)
            except (OSError, ValueError): pass
        threading.Thread(target=drain, args=(self.proc.stdout, self.out), daemon=True).start()
        threading.Thread(target=drain, args=(self.proc.stderr, self.err), daemon=True).start()
        time.sleep(.5)
    def send(self, text):
        if self.proc and self.proc.stdin and self.proc.poll() is None:
            self.proc.stdin.write(text + ("" if text.endswith("\n") else "\n"))   # FIX (terminal newline): send a real newline, not backslash-n
            self.proc.stdin.flush()
    def action(self, a):
        typ = str(a.get("type", a.get("action", ""))).lower()
        rec = {"type": typ, "at_utc": now(), "status": "executed"}
        if typ not in ACTIONS: return {**rec, "status":"unsupported", "error":f"Unsupported action {typ!r}"}
        if typ == "wait":
            secs = max(0, min(float(a.get("seconds", a.get("duration", 1)),), 30))
            time.sleep(secs); rec["seconds"] = secs
        elif typ == "observe": rec["observation_requested"] = True
        elif typ == "restart": self.start(); rec["restarted"] = True
        if typ in {"press", "key_down", "key_up", "input", "click"} and self.renderer != "terminal" and self.proc:
            rec["window_focused"] = focus_process_window(self.proc.pid)   # FIX (focus)
        if typ in {"press", "key_down", "key_up"}:
            key = str(a.get("key", a.get("value", "")))
            if self.renderer == "terminal":
                if typ == "press": self.send(key)
                else: return {**rec, "status":"unsupported", "error":"Terminal stdin cannot model held keys."}
            elif not self.pg: return {**rec, "status":"unsupported", "error":"GUI input needs pyautogui: py -m pip install pyautogui"}
            elif win_key(key, down=typ in {"press","key_down"}, up=typ in {"press","key_up"}): rec["sent_with"] = "scan_code"   # FIX (scan codes)
            elif typ == "press": self.pg.press(key)
            elif typ == "key_down": self.pg.keyDown(key)
            else: self.pg.keyUp(key)
            rec["key"] = key
        elif typ == "input":
            val = str(a.get("text", a.get("value", "")))
            if self.renderer == "terminal": self.send(val)
            elif self.pg: self.pg.write(val, interval=.02)
            else: return {**rec, "status":"unsupported", "error":"GUI input needs pyautogui."}
            rec["text_length"] = len(val)
        elif typ == "click":
            if not self.pg: return {**rec, "status":"unsupported", "error":"Click needs pyautogui."}
            if a.get("x") is None or a.get("y") is None: return {**rec, "status":"unsupported", "error":"Click needs x and y."}
            self.pg.click(int(a["x"]), int(a["y"]), clicks=int(a.get("clicks", 1)))
        return rec
    def observe(self, method, test_id, folder):
        obs = {"method":method, "captured_at_utc":now()}
        if method in {"stdout","log","screen_text"}:
            obs["text"] = "".join(self.out)[-20000:]
            obs["stderr_tail"] = "".join(self.err)[-10000:]
            if method == "screen_text": obs["limitation"] = "No OCR; this is process output, not pixel text."
        elif method == "screenshot":
            if not self.pg: obs.update(captured=False,error="Screenshot needs pyautogui.")
            else:
                try:
                    p = folder / f"{test_id}.png"; self.pg.screenshot().save(p)
                    obs.update(captured=True,path=str(p))
                except Exception as e: obs.update(captured=False,error=str(e))
        elif method == "game_state":
            obs.update(captured=False,error="Generic game state is unavailable without game-side instrumentation. Emit structured state to stdout/log.")
        elif method == "manual_inspection":
            obs.update(captured=False,needs_human_review=True)
        else: obs.update(captured=False,error=f"Unknown observation method {method!r}")
        return obs
    def flush(self, folder):
        folder.mkdir(parents=True, exist_ok=True)
        (folder/"stdout.log").write_text("".join(self.out), encoding="utf-8")
        (folder/"stderr.log").write_text("".join(self.err), encoding="utf-8")

def run_one(root, suite, test, command, outdir, startup_wait):
    tid = str(test.get("test_id", "unnamed"))
    folder = outdir/"evidence"/re.sub(r"[^A-Za-z0-9_.-]", "_", tid)
    folder.mkdir(parents=True, exist_ok=True)
    r = {"test_id":tid,"requirement_index":test.get("requirement_index"),"requirement":test.get("requirement"),
         "assertion":test.get("assertion"),"expected":test.get("expected"),"generator_status":test.get("status"),
         "started_at_utc":now(),"evidence_dir":str(folder),"action_results":[],"observations":[]}
    if test.get("status") != "ready_for_validator":
        r.update(status="NOT_RUN",reason=test.get("not_testable_reason","Test not marked ready_for_validator"))
        dump(folder/"evidence.json", r); return r
    s = Session(root, suite["renderer"], command, folder)
    t0 = time.monotonic()
    try:
        s.start(); time.sleep(max(0,min(startup_wait,20)))
        mark = None   # FIX (after-press): output index at the first input action
        for i,a in enumerate(test.get("actions", [])):
            if isinstance(a,dict) and mark is None and str(a.get("type",a.get("action",""))).lower() in {"press","key_down","input","click"}:
                time.sleep(0.15); mark = (len(s.out), len(s.err))   # anything printed before this (e.g. at startup) is ignored
            if not isinstance(a,dict): ar={"status":"unsupported","error":"Action must be object"}
            else: ar=s.action(a)
            ar["index"]=i; r["action_results"].append(ar)
        spec = test.get("observation") or {}
        method = str(spec.get("method",spec.get("type","stdout"))).lower()
        time.sleep(0.15)  # allow reader threads to drain recent output
        obs = s.observe(method,tid,folder); r["observations"].append(obs); s.flush(folder)
        text = str(obs.get("text",""))+"\\n"+str(obs.get("stderr_tail",""))
        if mark is not None and method in {"stdout","log","screen_text"}:   # FIX (after-press): judge only output after the key press
            text = "".join(s.out[mark[0]:]) + "\\n" + "".join(s.err[mark[1]:])
            r["checked_output"] = "after first input action only"
        status,reason = assert_observation(str(test.get("expected","")),method,text,obs.get("error"))
        # FIX (retry): a key press can get lost on Windows. If the line is missing, repeat the input actions
        # (up to 2 more times, game still running) and re-check. Retries are recorded in the evidence.
        retries = 0
        inputs = [a for a in test.get("actions", []) if isinstance(a,dict) and str(a.get("type",a.get("action",""))).lower() in {"press","key_down","key_up","input","wait"}]
        while status == "FAIL" and mark is not None and retries < 2 and s.proc and s.proc.poll() is None and inputs:
            retries += 1
            for a in inputs:
                ar = s.action(a); ar["retry"] = retries; r["action_results"].append(ar)
            time.sleep(0.15)
            text = "".join(s.out[mark[0]:]) + "\\n" + "".join(s.err[mark[1]:])
            status,reason = assert_observation(str(test.get("expected","")),method,text,None)
        r["input_retries"] = retries
        if retries and status == "PASS":
            reason += f" (passed after {retries} retry/retries of the key press)"
        s.flush(folder)
        if any(a.get("status")=="unsupported" for a in r["action_results"]):
            status,reason="BLOCKED","One or more actions were unsupported; fix adapter/test before interpreting game behavior."
        r.update(status=status,reason=reason,process={"pid":s.proc.pid if s.proc else None,"returncode":s.proc.poll() if s.proc else None},
                 runtime_evidence={"stdout_file":str(folder/"stdout.log"),"stderr_file":str(folder/"stderr.log"),
                                   "screenshot_file":obs.get("path")})
        r["triage_hints"]=classify(text,r["action_results"])
    except Exception as e:
        r.update(status="ERROR",reason=f"{type(e).__name__}: {e}",
                 triage_hints=[{"category":"test_harness_or_integration","confidence":"high","reason":"Runner error; diagnose harness before game."}])
        try: s.flush(folder)
        except Exception: pass
    finally: s.stop()
    r["duration_seconds"]=round(time.monotonic()-t0,3); r["finished_at_utc"]=now()
    dump(folder/"evidence.json",r)
    return r

def main():
    p=argparse.ArgumentParser(description="Bo V4 tester: execute existing Eval Generator suites and collect runtime evidence.")
    p.add_argument("--project-root",default=".")
    p.add_argument("--suite",help="suite.json path; defaults to newest traces/eval/*/suite.json")
    p.add_argument("--launch-command",required=True,help="Explicit launch command, run from project root")
    p.add_argument("--output",help="Output directory")
    p.add_argument("--startup-wait",type=float,default=1.0)
    p.add_argument("--limit",type=int,default=0)
    a=p.parse_args()
    root=Path(a.project_root).resolve()
    suite_path=Path(a.suite).resolve() if a.suite and Path(a.suite).is_absolute() else (root/a.suite).resolve() if a.suite else None
    if suite_path is None:
        choices=sorted((root/"traces"/"eval").glob("*/suite.json"),key=lambda x:x.stat().st_mtime,reverse=True)
        if not choices: p.error("No suite found; pass --suite path.")
        suite_path=choices[0]
    try: suite=read_suite(suite_path)
    except Exception as e: p.exit(2,f"tester: cannot read suite: {e}\\n")
    stamp=datetime.now().strftime("%Y%m%d_%H%M%S")
    out=Path(a.output).resolve() if a.output else root/"traces"/"eval"/str(suite.get("suite_version","suite"))/f"test_run_{stamp}"
    out.mkdir(parents=True,exist_ok=True)
    tests=suite["tests"][:a.limit] if a.limit>0 else suite["tests"]
    print(f"Bo V4 Tester | {suite.get('game_title','Unknown')} | {suite['renderer']} | {len(tests)} tests")
    print("Suite script_path values are not executed; launch command is explicit.")
    results=[]
    for i,test in enumerate(tests,1):
        print(f"[{i}/{len(tests)}] {test.get('test_id','?')} ...",flush=True)
        item=run_one(root,suite,test,a.launch_command,out,a.startup_wait); results.append(item)
        print(f"  {item['status']}: {item.get('reason','')[:160]}",flush=True)
    files=[]; ignored={".git",".venv","venv","__pycache__","node_modules",".godot"}
    for f in root.rglob("*"):
        if f.is_file() and not f.is_symlink() and not any(x in ignored for x in f.parts):
            try:
                size=f.stat().st_size
                files.append({"path":f.relative_to(root).as_posix(),"size_bytes":size,
                              "sha256":hashlib.sha256(f.read_bytes()).hexdigest() if size<25*1024*1024 else None})
            except OSError: pass
            if len(files)>=2500: break
    dump(out/"project_inventory.json",{"root":str(root),"files":files,"truncated":len(files)>=2500})
    counts={}
    for x in results: counts[x["status"]]=counts.get(x["status"],0)+1
    report={"schema_version":"1.0","run_id":f"test-run-{stamp}","created_at_utc":now(),"suite_path":str(suite_path),
       "suite_version":suite.get("suite_version"),"game_title":suite.get("game_title"),"renderer":suite["renderer"],
       "project_root":str(root),"launch_command":a.launch_command,"summary":{"total":len(results),"counts":counts},
       "results":results,"project_inventory":str(out/"project_inventory.json"),
       "triage_note":"Hints are heuristics, not definitive root-cause labels. Correlate brief, plan, code, asset manifest and runtime evidence."}
    dump(out/"test_results.json",report)
    print("\\nSUMMARY\\n"+json.dumps(report["summary"],indent=2))
    print("Results:",out/"test_results.json")
    print("Evidence:",out/"evidence")
    return 0 if counts.get("ERROR",0)==0 else 1

if __name__=="__main__": raise SystemExit(main())
