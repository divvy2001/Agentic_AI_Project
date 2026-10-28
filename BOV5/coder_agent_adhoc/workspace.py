"""Prepare an Initial Build without losing the previous game or upstream inputs.

The new game/ keeps only game/tests/ and the asset files the current Plan/manifest
authorize. Everything else (old code, assets of earlier tasks, caches) is moved to a
complete backup first; nothing is deleted.
"""
from datetime import datetime, timezone
import hashlib
import shutil
import uuid
import json
from pathlib import Path

from coder_agent_adhoc.configuration import config as C
from coder_agent_adhoc.contracts import path


def snapshot(directory):
    result = {}
    for item in directory.rglob('*'):
        # Check every component, including directory junctions, before reading.
        relative = item.relative_to(C.ROOT).as_posix()
        checked = path(relative)
        if checked.is_file():
            result[item.relative_to(directory).as_posix()] = hashlib.sha256(checked.read_bytes()).hexdigest()
    return result


def _current_asset_paths():
    from coder_agent_adhoc.contracts import plan, assets
    return {a['path'] for a in assets(plan())}


def prepare_initial_workspace(dry_run=False, allowed_assets=None):
    """allowed_assets: project-relative asset paths ('game/assets/x.png') valid for the
    current Plan. None derives them from the current Plan and manifest."""
    game = path('game', game=True)
    journal = path('traces/workspace_swap.json')
    if journal.is_file():
        transaction = json.loads(journal.read_text(encoding='utf-8'))
        if not isinstance(transaction, dict) or transaction.get('state') not in ('committed', 'rolled_back'):
            raise ValueError('workspace_recovery_required: inspect traces/workspace_swap.json before another build')
    if game != C.GAME_DIR.resolve():
        raise ValueError('game_directory_configuration_mismatch')
    result = dict(action='empty', backup_path=None, preserved_directories=[], preserved_files=0,
                  stale_files_backed_up=[], previous_file_count=0)
    if not game.exists():
        result['action'] = 'would_create' if dry_run else 'created'
        if not dry_run:
            game.mkdir()
        return result
    if not game.is_dir():
        raise ValueError('game_is_not_a_directory')
    allowed = set(_current_asset_paths() if allowed_assets is None else allowed_assets)
    original = snapshot(game)
    result['previous_file_count'] = len(original)
    keep = sorted(rel for rel in original if rel.startswith('tests/') or 'game/' + rel in allowed)
    stale = sorted(rel for rel in original if rel not in keep)
    result['preserved_directories'] = sorted({Path(rel).parts[0] for rel in keep})
    result['preserved_files'] = len(keep)
    result['stale_files_backed_up'] = [rel for rel in stale if rel.startswith('assets/')]
    if not stale:
        result['action'] = 'upstream_directories_only' if original else 'empty'
        return result
    if dry_run:
        result['action'] = 'would_backup_and_reset'
        return result

    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    identity = uuid.uuid4().hex[:10]
    backup = path(f'backups/game-{stamp}-{identity}')
    staging = path(f'.coder-game-{identity}')
    boundary = C.ROOT.resolve()
    if not (backup.is_relative_to(boundary / 'backups') and staging.parent == boundary):
        raise ValueError('unsafe_workspace_target')
    if backup.exists() or staging.exists():
        raise ValueError('workspace_target_already_exists')
    staging.mkdir()
    moved = False

    def record(state):
        from coder_agent_adhoc.tools.tools_coder import atomic_write
        from coder_agent_adhoc.run_context import CURRENT
        ctx = CURRENT.get()
        payload = dict(state=state, backup=backup.relative_to(C.ROOT).as_posix(), staging=staging.relative_to(C.ROOT).as_posix(),
                       original_files=original, preserved_files=keep, stale_files=stale,
                       plan_sha256=hashlib.sha256(C.PLAN_FILE.read_bytes()).hexdigest() if C.PLAN_FILE.is_file() else None,
                       attempt_id=ctx.attempt_id if ctx else None)
        atomic_write(journal, json.dumps(payload, indent=2).encode('utf-8'))
    try:
        # Prepare the new tree FIRST. A failed copy leaves the old game intact.
        for rel in keep:
            target = staging / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(game / rel, target)
        if snapshot(staging) != {rel: original[rel] for rel in keep} or snapshot(game) != original:
            raise ValueError('workspace_changed_during_preparation')
        backup.parent.mkdir(parents=True, exist_ok=True)
        record('prepared')
        game.rename(backup)
        moved = True
        try:
            staging.rename(game)
        except OSError:
            # Restore the original directory when the new-tree swap cannot complete.
            if not game.exists():
                backup.rename(game)
                moved = False
                record('rolled_back')
            raise
        record('committed')
        # Keep the old game's hashes/provenance outside the backup game tree.
        from coder_agent_adhoc.tools.tools_coder import atomic_write
        atomic_write(backup.with_suffix('.json'), journal.read_bytes())
        result.update(action='backed_up_and_reset', backup_path=backup.relative_to(C.ROOT).as_posix())
        return result
    finally:
        # The only recursive cleanup target is our checked, newly-created staging directory.
        checked = staging.resolve()
        if staging.exists() and checked.parent == boundary and checked.name == f'.coder-game-{identity}':
            shutil.rmtree(checked)
        # If a concurrent actor prevented rollback, the complete original remains at backup.
        if moved and not game.exists():
            raise ValueError('workspace_swap_failed_original_preserved_at:' + str(backup))
