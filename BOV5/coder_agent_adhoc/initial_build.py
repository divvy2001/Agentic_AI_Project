"""Stable Initial Build entrypoint for the future workflow.

Delegates to the shared bounded harness with mandatory smoke gates.
"""
import argparse
import json


def run_initial_build(dry_run: bool = False, launch_game: bool = True, resume_attempt_id: str | None = None) -> dict:
    from coder_agent_adhoc.agent_coder import run_coder
    from coder_agent_adhoc.launch_game import finish_with_play
    options = dict(resume_attempt_id=resume_attempt_id) if resume_attempt_id else {}
    return finish_with_play(run_coder(dry_run=dry_run, mode="initial_build", **options), enabled=launch_game and not dry_run)



def main() -> int:
    ap = argparse.ArgumentParser(description="PE6203 Coder Initial Build entrypoint")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-launch", action="store_true", help="Do not open a manual play session (automation/eval)")
    ap.add_argument("--resume", metavar="ATTEMPT_ID", help="Continue the same failed Initial Build without resetting game or budgets")
    args = ap.parse_args()
    result = run_initial_build(dry_run=args.dry_run, launch_game=not args.no_launch, resume_attempt_id=args.resume)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") in ("ready_for_testing", "dry_run") and result.get('play_session', {}).get('status') != 'failed' else 2


if __name__ == "__main__":
    raise SystemExit(main())
