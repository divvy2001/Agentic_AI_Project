"""Renderer adapters: generation guidance plus renderer-specific gate checks.

Every adapter module exposes:
  playbook(plan) -> str                      guidance appended to the system prompt
  contract_check(plan) -> (reason, msg)|None T1 project/engine file contract
  source_check(plan) -> (reason, msg)|None   T2 checks that need no engine
  boot_check(plan, result) -> reason|None    T3 interpretation of a boot run
Running the engine itself lives in execution.py / *_runtime.py.
"""
from importlib import import_module


def adapter(renderer):
    if renderer not in ('terminal', 'pygame', 'godot'):
        raise ValueError('invalid_renderer')
    return import_module('coder_agent_adhoc.adapters.' + renderer)


def playbook(p):
    return adapter(p['profile']['renderer']).playbook(p)
