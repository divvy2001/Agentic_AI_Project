"""Real engine regression: imported PNG sidecars must survive staging before boot."""
import os,unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
import test_harness as H
from coder_agent_adhoc import contracts,execution,godot_runtime as G
from coder_agent_adhoc.configuration import config as C

class GodotAssetCache(unittest.TestCase):
    setUp=H.Harness.setUp
    tearDown=H.Harness.tearDown
    stage=H.Harness.stage

    def asset_scene(self):
        self.stage('godot')
        f=C.GAME_DIR/'assets/probe.png';f.parent.mkdir(exist_ok=True)
        Image.new('RGBA',(64,64),(10,80,200,255)).save(f)
        (C.GAME_DIR/'main.tscn').write_text('[gd_scene load_steps=2 format=3]\n[ext_resource type="Texture2D" path="res://assets/probe.png" id="1"]\n[node name="Main" type="Sprite2D"]\ntexture = ExtResource("1")\n',encoding='utf-8')

    def test_staging_preserves_only_live_source_sidecars(self):
        self.asset_scene();self.addCleanup(G.release_stage)
        stage,_=G.stage_game();game=stage/'game'
        keep=game/'assets/probe.png.import';keep.write_text('engine metadata')
        stale=game/'assets/deleted.png.import';stale.write_text('stale metadata')
        extra=game/'runtime_extra.gd';extra.write_text('untrusted extra')
        extra.with_suffix('.gd.uid').write_text('stale uid')
        G.stage_game()
        self.assertTrue(keep.is_file());self.assertFalse(stale.exists());self.assertFalse(extra.exists());self.assertFalse(extra.with_suffix('.gd.uid').exists())
        (C.GAME_DIR/'assets/probe.png').unlink();G.stage_game();self.assertFalse(keep.exists())

    def test_scene_rejects_script_constructor_but_accepts_serialized_resource(self):
        self.asset_scene()
        from coder_agent_adhoc.adapters.godot import source_check
        f=C.GAME_DIR/'main.tscn'
        f.write_text('[gd_scene format=3]\n[node name="Main" type="CollisionShape2D"]\nshape = RectangleShape2D.new()\n',encoding='utf-8')
        self.assertEqual(source_check(contracts.plan())[0],'godot_scene_format')
        with patch.object(G,'run_godot') as native:
            import json
            from coder_agent_adhoc.tools.tools_coder import run_shell
            checked=json.loads(run_shell.invoke(dict(argv=['syntax'])))
            native.assert_not_called();self.assertEqual(checked['phase'],'source_precheck')
        f.write_text('[gd_scene load_steps=2 format=3]\n[sub_resource type="RectangleShape2D" id="shape"]\nsize = Vector2(64, 64)\n[node name="Main" type="CollisionShape2D"]\nshape = SubResource("shape")\n',encoding='utf-8')
        self.assertIsNone(source_check(contracts.plan()))

    def test_real_png_import_then_boot(self):
        self.asset_scene();self.addCleanup(G.release_stage)
        binary=Path(__file__).resolve().parents[3]/'work/godot/Godot_v4.7.2-stable_win64.exe'
        with patch.dict(os.environ,{'GODOT_BINARY':str(binary)}):
            p=contracts.plan();syntax=execution.run_action(p,'syntax')
            self.assertEqual(syntax.get('returncode'),0,syntax);self.assertIsNone(syntax.get('reason'),syntax)
            stage,_=G.stage_game();self.assertTrue((stage/'game/assets/probe.png.import').is_file(),'import metadata was lost between syntax and boot')
            boot=execution.run_action(p,'boot')
            self.assertEqual(boot.get('returncode'),0,boot);self.assertIsNone(boot.get('reason'),boot)
            self.assertNotRegex(boot.get('error_check_output',''),r'(?i)error:|parse error')
            self.assertEqual(boot['observed']['update_frames'],3,boot)

    def test_boot_alone_imports_png_and_reimports_changed_source(self):
        self.asset_scene();self.addCleanup(G.release_stage)
        binary=Path(__file__).resolve().parents[3]/'work/godot/Godot_v4.7.2-stable_win64.exe'
        with patch.dict(os.environ,{'GODOT_BINARY':str(binary)}):
            for changed in (False,True):
                if changed:
                    Image.new('RGBA',(64,64),(220,40,60,255)).save(C.GAME_DIR/'assets/probe.png')
                boot=execution.run_action(contracts.plan(),'boot')
                self.assertEqual(boot.get('returncode'),0,boot);self.assertIsNone(boot.get('reason'),boot)
                self.assertNotRegex(boot.get('error_check_output',''),r'(?i)error:|parse error')
                self.assertEqual(boot['observed']['update_frames'],3,boot)

    def test_empty_referenced_action_fails_until_real_key_is_bound(self):
        self.asset_scene();self.addCleanup(G.release_stage)
        project=C.GAME_DIR/'project.godot'
        project.write_text('[application]\nrun/main_scene="res://main.tscn"\n[input]\ncoder_probe={"deadzone":0.5,"events":[]}\n',encoding='utf-8')
        script=C.GAME_DIR/'main.gd'
        script.write_text('extends Node2D\nfunc _input(event):\n\tif event.is_action_pressed("coder_probe"):\n\t\tpass\n',encoding='utf-8')
        (C.GAME_DIR/'main.tscn').write_text('[gd_scene load_steps=2 format=3]\n[ext_resource type="Script" path="res://main.gd" id="1"]\n[node name="Main" type="Node2D"]\nscript = ExtResource("1")\n',encoding='utf-8')
        binary=Path(__file__).resolve().parents[3]/'work/godot/Godot_v4.7.2-stable_win64.exe'
        with patch.dict(os.environ,{'GODOT_BINARY':str(binary)}):
            bad=execution.run_action(contracts.plan(),'boot')
            self.assertIn('input action has no bound events: coder_probe',bad['output']);self.assertNotEqual(bad['returncode'],0)
            script.write_text(script.read_text(encoding='utf-8')+'func _ready():\n\tvar key := InputEventKey.new()\n\tkey.physical_keycode = KEY_D\n\tInputMap.action_add_event("coder_probe",key)\n',encoding='utf-8')
            good=execution.run_action(contracts.plan(),'boot')
            self.assertEqual(good['returncode'],0,good);self.assertEqual(good['observed']['update_frames'],3,good)

    def test_keyboard_plan_rejects_extends_only_controller(self):
        self.asset_scene();p=contracts.plan()
        p['requirements'].append(dict(text='WASD and arrow keys move the player',check='Escape quits',status='full'))
        (C.GAME_DIR/'main.gd').write_text('extends Node2D\n',encoding='utf-8')
        from coder_agent_adhoc.adapters.godot import source_check
        self.assertEqual(source_check(p)[0],'godot_input_implementation_missing')
        (C.GAME_DIR/'main.gd').write_text('extends Node2D\nfunc _input(event):\n\tif event is InputEventKey:\n\t\tpass\n',encoding='utf-8')
        self.assertIsNone(source_check(p))

    def test_invalid_project_write_is_rejected_before_disk_mutation(self):
        self.asset_scene();f=C.GAME_DIR/'project.godot';original=f.read_bytes()
        from coder_agent_adhoc.tools.tools_coder import write_file
        bad='[application]\nrun/main_scene="res://main.tscn"\n[input]\nmove={"events":[{"type":"InputEventKey","physical_keycode":87}]}\n'
        with self.assertRaisesRegex(ValueError,'invalid_godot_input_events'):
            write_file.invoke(dict(path='game/project.godot',content=bad))
        self.assertEqual(f.read_bytes(),original)

    def test_scene_preload_write_rejected_without_mutation(self):
        self.asset_scene();f=C.GAME_DIR/'main.tscn';original=f.read_bytes()
        from coder_agent_adhoc.tools.tools_coder import write_file
        for bad in ('[gd_scene format=3]\n[node name="Main" type="Node2D"]\nscript = preload("res://main.gd")\n',
                    '[gd_scene format=3]\n[node name="Main" instance=preload("res://player.tscn")]\n'):
            with self.assertRaisesRegex(ValueError,'godot_scene_format'):
                write_file.invoke(dict(path='game/main.tscn',content=bad))
            self.assertEqual(f.read_bytes(),original)

    def test_scene_guard_allows_valid_resources_and_script_preload(self):
        from coder_agent_adhoc.adapters.godot import scene_text_problem
        valid='[gd_scene load_steps=2 format=3]\n[ext_resource type="PackedScene" path="res://player.tscn" id="1"]\n[node name="Main" instance=ExtResource("1")]\nposition = Vector2(32,64)\n'
        self.assertIsNone(scene_text_problem(valid,'game/main.tscn'))

if __name__=='__main__':unittest.main()
