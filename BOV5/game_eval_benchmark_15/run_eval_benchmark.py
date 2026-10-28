from pathlib import Path
import argparse, getpass, json, sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from eval_generator_module.eval_generator.generator import generate_suite, DEFAULT_MODEL

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--project-root",default=".")
    p.add_argument("--dataset",default="game_eval_benchmark_15/dataset.json")
    p.add_argument("--model",default=DEFAULT_MODEL)
    p.add_argument("--max-tokens",type=int,default=2500)
    p.add_argument("--budget-usd",type=float,default=1.00)
    a=p.parse_args()
    project=Path(a.project_root).resolve()
    dp=Path(a.dataset); dp=dp if dp.is_absolute() else project/dp
    data=json.loads(dp.read_text(encoding="utf-8"))
    key=getpass.getpass("Enter your OpenRouter API key (input hidden): ").strip()
    if not key: raise SystemExit("No API key entered.")
    rows=[]; total=0.0
    for n,c in enumerate(data["cases"],1):
        if total>=a.budget_usd:
            print(f"Budget guard reached at estimated ${total:.4f}; stopping before next game.")
            break
        print(f"[{n}/15] {c['game_id']} — {c['game_title']} ({c['complexity']})")
        try:
            suite=generate_suite(project,c["suite_version"],
              f"game_eval_benchmark_15/{c['plan_path']}",f"game_eval_benchmark_15/{c['manual_path']}",
              key,a.model,a.max_tokens)
            usage=suite["generation_usage"]; cost=float(usage.get("estimated_cost_usd") or 0); total+=cost
            row={"game_id":c["game_id"],"title":c["game_title"],"complexity":c["complexity"],"status":"generated",
              "suite_version":suite["suite_version"],"tests":suite["summary"]["total"],
              "ready_for_validator":suite["summary"]["ready_for_validator"],"not_testable":suite["summary"]["not_testable"],
              "usage":usage,"output":f"traces/eval/{suite['suite_version']}/suite.json"}
            print(f"  {row['tests']} tests; ready={row['ready_for_validator']}; not_testable={row['not_testable']}; est=${cost:.6f}")
        except Exception as e:
            row={"game_id":c["game_id"],"title":c["game_title"],"status":"error","error":str(e)}
            print("  ERROR:",e)
        rows.append(row)
    report={"dataset":data["dataset_name"],"model":a.model,"budget_usd":a.budget_usd,"requested":len(data["cases"]),
      "processed":len(rows),"generated":sum(x["status"]=="generated" for x in rows),"errors":sum(x["status"]=="error" for x in rows),
      "total_tests":sum(x.get("tests",0) for x in rows),"ready_for_validator":sum(x.get("ready_for_validator",0) for x in rows),
      "not_testable":sum(x.get("not_testable",0) for x in rows),"estimated_total_cost_usd":round(total,6),
      "cost_note":"Uses token usage returned by OpenRouter when available; estimate is $0.40/M input and $1.60/M output tokens. Check current rates.",
      "results":rows}
    out=project/"game_eval_benchmark_15"/"batch_report.json"; out.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print("\nSUMMARY\n"+json.dumps({k:report[k] for k in ["requested","processed","generated","errors","total_tests","ready_for_validator","not_testable","estimated_total_cost_usd"]},indent=2))
    print("Report:",out)
if __name__=="__main__": main()
