# GenAI Eval Generator for Bo's Project V4

This module uses an OpenRouter-hosted LLM to propose evaluation test specifications from:
- `plans/coder_plan.json` (game plan and requirements)
- `plans/play_manual.json` (controls and play instructions)
- optionally `plans/asset_manifest.json` (used for source tracking; the model currently receives the plan and manual)

It writes a versioned `traces/eval/<suite-version>/suite.json`. It does **not** run the game or claim tests passed. A renderer-specific Tester/Validator still has to execute each test and create `test_results.json`.

## Install
Copy the `eval_generator` folder into the root of Bo's Project V4. No third-party Python packages are required; it uses the standard library.

## Run
The generator prompts for your OpenRouter API key if `OPENROUTER_API_KEY` is not already set. The key is entered with hidden input and is not saved by this module.

```powershell
python -m eval_generator.generator --project-root . --plan plans/dummy_coder_plan.json --manual plans/dummy_play_manual.json --suite-version dummy-eval-genai-v1
```

The model is hardcoded as `openai/gpt-4.1-mini` in `generator.py`. Change the `selected_model` default there if needed. API usage may incur charges.

## Run (GenAI mode is the default)
```powershell
python -m eval_generator.generator --project-root . --plan plans/dummy_coder_plan.json --manual plans/dummy_play_manual.json --suite-version dummy-eval-genai-v1
```

For normal project inputs:
```powershell
python -m eval_generator.generator --project-root . --suite-version eval-genai-v1
```

Use a **new** suite version each time inputs or generator settings change. Existing suite versions are frozen and will not be silently overwritten.

## Offline mode
```powershell
python -m eval_generator.generator --project-root . --plan plans/dummy_coder_plan.json --manual plans/dummy_play_manual.json --suite-version dummy-eval-rules-v1 --backend rules
```
Rules mode does not use GenAI; it only packages explicitly structured `manual.eval.tests` entries. Requirements without such entries become `not_testable`.

## Output contract
Each test includes:
- `test_id`, `requirement_index`, `requirement`, `assertion`
- declarative `actions`
- `observation.method` and `observation.target`
- `expected`, `status`, `not_testable_reason`
- `renderer`, `timeout_seconds`, `script_path`

The LLM is instructed not to generate executable code or invent driver scripts. Output is structurally validated; malformed tests are marked `not_testable`. Every plan requirement must have at least one structurally valid test or a generated not-testable placeholder.

## Safety and limits
- The LLM proposes test cases; it does not execute them.
- Structural validation does not prove tests are meaningful or supported by a real driver.
- The Tester must interpret the declarative action vocabulary for each renderer.
- Do not treat `ready_for_validator` as PASS.
- Model names, pricing, and availability can change. Check your OpenRouter account for current model availability and rates.
