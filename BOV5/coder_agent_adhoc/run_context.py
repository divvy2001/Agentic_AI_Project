"""Per-call tool state and a process-safe workspace lock. No persistent state database."""
import contextvars
import copy
import hashlib
import os
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from coder_agent_adhoc.contracts import path


@dataclass
class RunContext:
    mode: str
    plan: dict
    attempt_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    evidence: set = field(default_factory=set)
    written: set = field(default_factory=set)
    protected: dict = field(default_factory=dict)
    read_versions: dict = field(default_factory=dict)
    write_versions: dict = field(default_factory=dict)
    changes: list = field(default_factory=list)
    repair_original: dict = field(default_factory=dict)
    debug_statistics: dict = field(default_factory=lambda: dict(local_failure_events=0,self_debug_attempts=0,external_repair_invocations=0))
    pending_failure_step: int | None = None
    started: float = field(default_factory=time.monotonic)
    elapsed_before_resume: float = 0.0
    pending_calls: list = field(default_factory=list)
    checkpoint_phase: str = 'between_turns'
    request_in_flight: bool = False
    provider_retries: int = 0
    provider_consecutive: int = 0
    resuming: bool = False
    integration: dict = field(default_factory=dict)
    integration_write_turns: int = 0
    last_tool_error: str = ''
    same_tool_failures: int = 0


CURRENT=contextvars.ContextVar('coder_run_context',default=None)


def current_plan():
    from coder_agent_adhoc.contracts import plan
    ctx=CURRENT.get()
    return copy.deepcopy(ctx.plan) if ctx else plan()


def digest(data): return hashlib.sha256(data).hexdigest()


@contextmanager
def workspace_lock():
    # OS releases locks on crash; an existing unlocked lock file is harmless.
    lock_path=path('.coder.lock')
    with lock_path.open('a+b') as handle:
        handle.seek(0,2)
        if handle.tell()==0: handle.write(b'0'); handle.flush()
        handle.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError as exc:
            raise ValueError('workspace_busy') from exc
        try: yield
        finally:
            handle.seek(0)
            if os.name=='nt': msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
            else: fcntl.flock(handle,fcntl.LOCK_UN)
