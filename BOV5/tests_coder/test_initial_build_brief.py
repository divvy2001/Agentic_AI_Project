"""Implementation brief completeness and isolation; no model/network requests."""
import copy,json,unittest
from coder_agent_adhoc.build_brief import initial_build_brief
from coder_agent_adhoc.context import first_message,system_prompt,remember_initial_notes,compact
from langchain_core.messages import AIMessage,SystemMessage

def sample(renderer='pygame'):
    req=lambda status,m:dict(text='Keep the required behavior',check='Observable result',priority='core',status=status,milestone=m,quote='source')
    return dict(status='success',game_title='Brief test',profile=dict(renderer=renderer,dimensions='2d',pace='turn-based'),
                requirements=[req('full',1),req('approximated',2),req('dropped',2)],
                architecture=dict(entry_point='game/main.tscn' if renderer=='godot' else 'game/main.py',
                                  files=[dict(path='game/__init__.py',purpose='package marker'),dict(path='game/main.tscn' if renderer=='godot' else 'game/main.py',purpose='controller')],
                                  assets=dict(strategy='none',sprites=[]),resolution=dict(width=640,height=480),fps=60))

class InitialBuildBrief(unittest.TestCase):
    def test_each_active_requirement_has_exactly_one_milestone_slot(self):
        p=sample();before=copy.deepcopy(p);brief=initial_build_brief(p)
        assigned=[i for m in brief['milestones'] for i in m['requirement_indices']]
        self.assertEqual(assigned,[0,1]);self.assertEqual(brief['active_requirement_indices'],[0,1])
        self.assertEqual(brief['dropped_requirement_indices'],[2]);self.assertEqual(p,before)

    def test_original_file_order_entry_and_no_file_ceiling(self):
        p=sample();p['architecture']['files'] += [dict(path=f'game/module_{i}.py',purpose='planned helper') for i in range(20)]
        brief=initial_build_brief(p)
        self.assertEqual(brief['promised_files'],[f['path'] for f in p['architecture']['files']])
        self.assertEqual(brief['entry_point'],p['architecture']['entry_point']);self.assertEqual(len(brief['promised_files']),22)

    def test_godot_project_supplement_never_duplicated(self):
        p=sample('godot');self.assertEqual(initial_build_brief(p)['engine_supplements'],['game/project.godot'])
        p['architecture']['files'].append(dict(path='game/project.godot',purpose='engine configuration'))
        self.assertEqual(initial_build_brief(p)['engine_supplements'],[])
        message=json.loads(first_message('initial_build',p,[]).content)
        self.assertEqual(message['files_to_write'].count('game/project.godot'),1)

    def test_initial_message_contains_brief_and_unmodified_plan(self):
        p=sample();context=json.loads(first_message('initial_build',p,[]).content)
        self.assertEqual(context['plan'],p);self.assertIn('implementation_brief',context)
        self.assertEqual(len(context['implementation_brief']['first_response_contract']),4)
        review=' '.join(context['implementation_brief']['completion_review'])
        self.assertIn('secondary',review);self.assertIn('assets',review)
        self.assertIn('rendered bounds',review)
        self.assertIn('argument/return types',' '.join(context['implementation_brief']['first_response_contract']))

    def test_initial_prompt_requires_complete_lifecycle_before_manual(self):
        text=system_prompt('initial_build',sample())
        self.assertIn('concrete shared interfaces',text);self.assertIn('ALL milestones',text)
        self.assertIn('LAST: write_play_manual',text);self.assertIn('restarting midway',text)
        self.assertIn('one cell/action per KEYDOWN',text)

    def test_turn_based_godot_does_not_require_physics(self):
        text=system_prompt('initial_build',sample('godot'))
        self.assertIn('physics is actually needed',text);self.assertIn('one\n  move per non-echo key press',text)
        self.assertIn('do not add another half-tile sprite offset',text)

    def test_first_implementation_notes_survive_compaction_without_changing_plan(self):
        p=sample();first=first_message('initial_build',p,[]);messages=[SystemMessage(content='s'),first]
        response=AIMessage(content='Player owns movement; controller calls player.move; HUD reads committed state.')
        note=remember_initial_notes(messages,response)
        for i in range(4):messages.append(AIMessage(content='continue'))
        view=compact(messages,recent_turns=2);context=json.loads(view[1].content)
        self.assertEqual(context['initial_build_notes'],note);self.assertIn('unverified',note['source'])
        self.assertEqual(json.loads(first.content)['plan'],p)

    def test_empty_tool_only_response_does_not_fabricate_notes(self):
        messages=[SystemMessage(content='s'),first_message('initial_build',sample(),[])]
        self.assertIsNone(remember_initial_notes(messages,AIMessage(content='')))
        self.assertNotIn('initial_build_notes',json.loads(messages[1].content))

    def test_terminal_keyboard_requirements_have_interactive_and_pipe_modes(self):
        text=system_prompt('initial_build',sample('terminal'))
        self.assertIn('sys.stdin.isatty()',text);self.assertIn('msvcrt.getwch()',text)
        self.assertIn('do not call getwch in that mode',text);self.assertIn('EOF handling',text)

if __name__=='__main__':unittest.main()
