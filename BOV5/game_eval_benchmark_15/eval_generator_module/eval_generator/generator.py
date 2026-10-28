from __future__ import annotations
import argparse, getpass, hashlib, json, os, re, urllib.error, urllib.request
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

VALID_RENDERERS={"terminal","pygame","godot"}
VERSION_RE=re.compile(r"^[A-Za-z0-9_-]+$")
URL="https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL="openai/gpt-4.1-mini"
INPUT_RATE=0.40
OUTPUT_RATE=1.60

def read_json(path,label):
    if not path.is_file(): raise FileNotFoundError(f"Missing {label}: {path}")
    try: data=json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError,json.JSONDecodeError) as e: raise ValueError(f"Invalid JSON in {label}: {e}") from e
    if not isinstance(data,dict): raise ValueError(f"{label} must be a JSON object")
    return data

def safe_path(root,value):
    if not isinstance(value,str) or not value.strip(): return None
    pp=PurePosixPath(value.replace("\\\\","/"))
    if pp.is_absolute() or ".." in pp.parts: return None
    candidate=(root/Path(*pp.parts)).resolve()
    try: rel=candidate.relative_to(root.resolve())
    except ValueError: return None
    if not candidate.is_file() or candidate.is_symlink(): return None
    return rel.as_posix()

def extract_json(text):
    text=text.strip()
    if text.startswith("```"):
        text=re.sub(r"^```(?:json)?\\s*","",text,flags=re.I)
        text=re.sub(r"\\s*```$","",text)
    try: obj=json.loads(text)
    except json.JSONDecodeError:
        a,b=text.find("{"),text.rfind("}")
        if a<0 or b<=a: raise ValueError("LLM response did not contain JSON")
        obj=json.loads(text[a:b+1])
    if not isinstance(obj,dict): raise ValueError("LLM response must be an object")
    return obj

def call_llm(plan,manual,renderer,model,key,max_tokens):
    system=("You are a careful game QA test designer. Return only valid JSON. Generate test specifications, never test results. "
    "Do not generate code or invent hidden APIs, test hooks, or script paths. Actions must be declarative and grounded in documented controls. "
    "Cover every requirement. For complex mechanics, use multi-step scenarios with explicit preconditions, state transitions, boundary/negative cases. "
    "If a test cannot be reliably performed or observed using the provided information, mark it not_testable.")
    shape={"tests":[{"test_id":"T01","requirement_index":0,"assertion":"measurable assertion",
        "actions":[{"type":"press|key_down|key_up|wait|click|observe|restart|input","value":"example","duration_frames":1}],
        "observation":{"method":"screen_text|game_state|screenshot|stdout|log|manual_inspection","target":"observable"},
        "expected":"measurable outcome","status":"ready_for_validator or not_testable","not_testable_reason":None,"timeout_seconds":30}],
        "generation_notes":["coverage note"]}
    payload={"renderer":renderer,"game_title":plan.get("game_title","Untitled game"),"plan":plan,"play_manual":manual,
      "required_output_shape":shape,"constraints":["requirement_index is zero-based","generate 1-3 tests per requirement plus useful edge cases",
      "never use set_test_state or undocumented state mutation","script_path is not allowed","ready_for_validator requires documented actions and observable outcomes",
      "never claim execution or pass/fail"]}
    body={"model":model,"temperature":0.2,"max_tokens":max_tokens,
      "messages":[{"role":"system","content":system},{"role":"user","content":json.dumps(payload,ensure_ascii=False)}],
      "response_format":{"type":"json_object"}}
    req=urllib.request.Request(URL,data=json.dumps(body).encode(),headers={"Authorization":"Bearer "+key,
      "Content-Type":"application/json","HTTP-Referer":"https://openrouter.ai/","X-Title":"Bo Project V4 Eval Benchmark"},method="POST")
    try:
        with urllib.request.urlopen(req,timeout=120) as r: data=json.loads(r.read().decode())
    except urllib.error.HTTPError as e: raise RuntimeError(f"OpenRouter HTTP {e.code}: {e.read().decode(errors='replace')[:1000]}") from e
    except urllib.error.URLError as e: raise RuntimeError(f"OpenRouter connection error: {e.reason}") from e
    content=data["choices"][0]["message"]["content"]
    if isinstance(content,list): content="".join(x.get("text","") for x in content if isinstance(x,dict))
    raw=extract_json(content)
    if not isinstance(raw.get("tests"),list): raise ValueError("Model output missing tests array")
    u=data.get("usage") or {}
    inp=int(u.get("prompt_tokens") or u.get("input_tokens") or 0)
    out=int(u.get("completion_tokens") or u.get("output_tokens") or 0)
    cost=u.get("cost")
    try: cost=float(cost) if cost is not None else None
    except (TypeError,ValueError): cost=None
    estimated=(inp*INPUT_RATE+out*OUTPUT_RATE)/1_000_000
    usage={"prompt_tokens":inp,"completion_tokens":out,"total_tokens":int(u.get("total_tokens") or inp+out),
      "provider_reported_cost_usd":cost,"estimated_cost_usd":round(estimated,8),
      "cost_source":"OpenRouter usage.cost" if cost is not None else "estimate using configured model rates"}
    return raw,usage

def generate_suite(project_root,suite_version,plan_path,manual_path,api_key,model=DEFAULT_MODEL,max_tokens=2500):
    root=Path(project_root).resolve()
    if not VERSION_RE.fullmatch(suite_version): raise ValueError("Invalid suite version")
    pr=safe_path(root,plan_path); mr=safe_path(root,manual_path)
    if not pr: raise ValueError(f"Plan must be project-relative and exist: {plan_path}")
    plan=read_json(root/pr,"plan"); manual=read_json(root/mr,"manual") if mr else {}
    profile=plan.get("profile") or {}; renderer=str(profile.get("renderer","")).lower()
    if renderer not in VALID_RENDERERS: raise ValueError(f"Unsupported renderer: {renderer}")
    requirements=plan.get("requirements")
    if not isinstance(requirements,list) or not requirements: raise ValueError("Plan needs non-empty requirements")
    raw,usage=call_llm(plan,manual,renderer,model,api_key,max_tokens)
    warnings=[]; tests=[]; represented=set(); covered=set()
    action_types={"press","key_down","key_up","wait","click","observe","restart","input"}
    obs_types={"screen_text","game_state","screenshot","stdout","log","manual_inspection"}
    for item in raw["tests"]:
        if not isinstance(item,dict): continue
        ri=item.get("requirement_index")
        if not isinstance(ri,int) or isinstance(ri,bool) or not 0<=ri<len(requirements): continue
        represented.add(ri); requirement=requirements[ri]
        actions=item.get("actions"); obs=item.get("observation"); expected=item.get("expected")
        valid=(isinstance(actions,list) and len(actions)>0 and all(isinstance(a,dict) and a.get("type") in action_types for a in actions)
          and isinstance(obs,dict) and obs.get("method") in obs_types and isinstance(obs.get("target"),str) and bool(obs["target"].strip())
          and isinstance(expected,str) and bool(expected.strip()))
        status=item.get("status")
        if status=="ready_for_validator" and valid:
            reason=None; covered.add(ri)
        else:
            status="not_testable"; reason=item.get("not_testable_reason") or "Test did not meet the generator's structural validation rules."
            actions=actions if isinstance(actions,list) else []; obs=obs if isinstance(obs,dict) else {"method":None}
            expected=expected if isinstance(expected,str) and expected else str(requirement.get("check") or requirement.get("text") or "")
        tests.append({"test_id":str(item.get("test_id") or f"T{len(tests)+1:02d}"),"requirement_index":ri,
          "requirement":str(requirement.get("text") or requirement.get("check") or ""),"assertion":str(item.get("assertion") or requirement.get("check") or ""),
          "actions":actions,"observation":obs,"expected":expected,"status":status,"not_testable_reason":reason,
          "renderer":renderer,"timeout_seconds":int(item.get("timeout_seconds",30)) if str(item.get("timeout_seconds",30)).isdigit() else 30,"script_path":None})
    for i,req in enumerate(requirements):
        if i not in represented:
            txt=str(req.get("text") or req.get("check") or "")
            tests.append({"test_id":f"T{len(tests)+1:02d}","requirement_index":i,"requirement":txt,"assertion":str(req.get("check") or txt),
             "actions":[],"observation":{"method":None},"expected":str(req.get("check") or txt),"status":"not_testable",
             "not_testable_reason":"No test was generated for this requirement.","renderer":renderer,"timeout_seconds":30,"script_path":None})
            warnings.append(f"Requirement {i} has no generated test")
    hashes={pr:hashlib.sha256((root/pr).read_bytes()).hexdigest()}
    if mr: hashes[mr]=hashlib.sha256((root/mr).read_bytes()).hexdigest()
    outdir=root/"traces"/"eval"/suite_version; outdir.mkdir(parents=True,exist_ok=True); outfile=outdir/"suite.json"
    suite={"schema_version":"1.0","suite_version":suite_version,"generated_at_utc":datetime.now(timezone.utc).isoformat(),
      "renderer":renderer,"game_title":plan.get("game_title","Untitled game"),"generator":{"backend":"openrouter","model":model},
      "generation_notes":[x for x in raw.get("generation_notes",[]) if isinstance(x,str)],"generation_usage":usage,"source_hashes":hashes,
      "tests":tests,"summary":{"total":len(tests),"ready_for_validator":sum(t["status"]=="ready_for_validator" for t in tests),
      "not_testable":sum(t["status"]=="not_testable" for t in tests)},"warnings":warnings,
      "important":"Generation is not execution. This file does not claim PASS and must not be used as test_results.json."}
    if outfile.exists(): raise FileExistsError(f"{outfile} already exists; choose a new suite version")
    outfile.write_text(json.dumps(suite,indent=2,ensure_ascii=False)+"\\n",encoding="utf-8")
    return suite
