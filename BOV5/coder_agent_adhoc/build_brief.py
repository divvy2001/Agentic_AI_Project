"""Deterministic implementation brief from the unchanged Planner contract.

This assigns no new requirements, renderer, filenames or game mechanics. It makes
the existing implementation obligations visible before the first source write.
"""


def initial_build_brief(plan):
    active = [i for i, r in enumerate(plan['requirements']) if r['status'] != 'dropped']
    milestones = sorted({plan['requirements'][i]['milestone'] for i in active})
    promised = [f['path'] for f in plan['architecture']['files']]
    supplements = (['game/project.godot'] if plan['profile']['renderer'] == 'godot'
                   and 'game/project.godot' not in promised else [])
    return dict(
        source='immutable Planner requirements and file purposes; implementation only',
        active_requirement_indices=active,
        dropped_requirement_indices=[i for i, r in enumerate(plan['requirements']) if r['status'] == 'dropped'],
        milestones=[dict(milestone=m, requirement_indices=[i for i in active if plan['requirements'][i]['milestone'] == m])
                    for m in milestones],
        promised_files=promised, engine_supplements=supplements,
        entry_point=plan['architecture']['entry_point'],
        first_response_contract=['requirement indices -> owning promised files',
                                 'state ownership and concrete cross-file method signatures, including argument/return types',
                                 'input -> action -> state/rules -> visible feedback; one logical/world/sprite coordinate convention',
                                 'init, play, terminal states, reset and quit paths required by Plan'],
        implementation_order=['agree interfaces across all promised files before writing',
                              'connect one complete input-to-feedback path',
                              'implement every remaining active requirement and milestone',
                              'review actual source and integration; run syntax and boot',
                              'write final play manual and coverage after reviewing completeness'],
        completion_review=['every active core AND secondary requirement has a real code path',
                           'every promised file fulfills its stated purpose through used code',
                           'all required supplied assets are loaded and displayed without substitution',
                           'logical positions, node anchors and rendered bounds agree; apply spatial corrections only once',
                           'state transitions and restart restore the objects/state required by Plan',
                           'startup checks and model claims do not establish gameplay acceptance'])
