# 15-game Eval Generator benchmark

Contains 15 game descriptions: 6 simple, 6 medium, and 3 complex, spanning Terminal, Pygame, and Godot.

## Run from the Bo Project V4 root
Copy the `game_eval_benchmark_15` folder into your project root. Run:

```powershell
py game_eval_benchmark_15/run_eval_benchmark.py --project-root . --dataset game_eval_benchmark_15/dataset.json --budget-usd 1.00 --max-tokens 2500
```

It prompts once for the OpenRouter API key. The key is passed in memory and not written to disk by the runner. Model defaults to `openai/gpt-4.1-mini`.

The bundled `eval_generator_module` is a self-contained version with token-usage capture and a per-call output-token cap. The batch script imports it directly. It writes each suite to `traces/eval/benchmark-gxx/suite.json` and a combined `game_eval_benchmark_15/batch_report.json`.

## Cost control
- The $1 budget is a ceiling, not a target to spend.
- `--max-tokens 2500` caps output tokens per game call.
- The script estimates total cost from token counts using $0.40/M input and $1.60/M output when provider cost is unavailable. A single call can cross the limit slightly because the final usage is only known after that call.
- At these rates, 15 calls should usually cost substantially less than $1. Verify current OpenRouter pricing before running.

## Important
This tests test-generation quality from game specifications, not actual games. `ready_for_validator` does not mean PASS; a renderer-specific Tester must execute the tests.
