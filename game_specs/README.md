# Game specs

One game per `.md` file. `run_pipeline.py` sends **only the text under `## Spec`** to the Planner;
the title and `## Notes` are for you and are ignored.

Pick a spec:
- set `SPEC_FILE = "snake.md"` at the top of `BOV5/run_pipeline.py`, or
- run `python run_pipeline.py snake.md` (overrides SPEC_FILE).

Template:

```
# Game title

## Spec

One paragraph describing the game...

## Notes

- Expected engine: pygame
- Anything else for you (ignored by the pipeline)
```
