"""Trusted startup observer inside a native sandbox; never asserts gameplay PASS."""
import json, os, runpy, sys, time
from pathlib import Path
renderer,entry=sys.argv[1:3]
action=sys.argv[3] if len(sys.argv)>3 else 'boot'
root=Path.cwd().resolve(); game=root/'game'
frames=inputs=game_lines=loop_cycles=0
pixel_colors=0
first_presentation=None
waiting=False
class SmokeComplete(BaseException): pass
read_roots=[game,Path(sys.prefix).resolve()]
# Read-only system fonts so pygame font fallbacks do not crash the startup check.
if os.getenv('WINDIR'): read_roots.append((Path(os.environ['WINDIR'])/'Fonts').resolve())
def audit(event,args):
    if event.startswith(('socket.','subprocess.','os.system','os.exec','os.spawn','ctypes.dlopen')):
        raise PermissionError('smoke child disallows network/process/native loading')
    if event=='open' and isinstance(args[0],(str,bytes,os.PathLike)):
        dest=Path(os.fsdecode(args[0])).resolve(); mode,flags=args[1:3]
        writing=(isinstance(mode,str) and any(c in mode for c in 'wax+')) or (isinstance(flags,int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT))
        if dest.name=='.env' or dest.suffix.lower() in ('.env','.key','.pem'): raise PermissionError('child secret read denied')
        if writing or not any(dest.is_relative_to(base) for base in read_roots): raise PermissionError('child file access denied')
    if event in ('os.remove','os.rename','os.rmdir','os.mkdir','os.link','os.symlink','os.chmod','os.truncate','os.utime','shutil.copyfile'):
        raise PermissionError('child file mutation denied')
# Load trusted engine bindings before denying further native-library loading.
if renderer=='pygame' and action=='boot': import pygame
sys.addaudithook(audit)
if action=='syntax':
    for source in sorted(game.rglob('*.py')):
        if '__pycache__' not in source.parts and 'tests' not in source.relative_to(game).parts:
            compile(source.read_bytes(),str(source),'exec')
    print('CODER_SYNTAX_OK',flush=True)
    raise SystemExit(0)
last_line={}
def trace(frame,event,arg):
    global game_lines,loop_cycles
    if not frame.f_code.co_filename.startswith(str(game)+os.sep): return None
    if event=='line':
        game_lines+=1; key=id(frame)
        if frame.f_lineno<last_line.get(key,0): loop_cycles+=1
        last_line[key]=frame.f_lineno
    elif event=='return': last_line.pop(id(frame),None)
    return trace
has_sample=os.getenv('CODER_HAS_STDIN_SAMPLE')=='1'
class ObservedInput:
    def __init__(self,original): self.original=original
    def _read(self,method,*args):
        global inputs,waiting
        inputs+=1
        if not has_sample:
            waiting=True
            raise SmokeComplete()
        return getattr(self.original,method)(*args)
    def read(self,*a): return self._read('read',*a)
    def readline(self,*a): return self._read('readline',*a)
    def readlines(self,*a): return self._read('readlines',*a)
    def __iter__(self): return self
    def __next__(self):
        line=self.readline()
        if not line: raise StopIteration
        return line
    def __getattr__(self,name): return getattr(self.original,name)
if renderer=='terminal': sys.stdin=ObservedInput(sys.stdin)
else:
    original_flip=pygame.display.flip; original_update=pygame.display.update
    def presented(fn,*a,**kw):
        global frames,pixel_colors,first_presentation
        result=fn(*a,**kw); frames+=1
        if first_presentation is None: first_presentation=time.monotonic()
        surface=pygame.display.get_surface()
        if surface is not None:
            colors={tuple(surface.get_at((x,y))) for y in range(0,surface.get_height(),max(1,surface.get_height()//48))
                    for x in range(0,surface.get_width(),max(1,surface.get_width()//64))}
            pixel_colors=max(pixel_colors,len(colors))
        if frames>=8 and time.monotonic()-first_presentation>=0.6: raise SmokeComplete()
        return result
    pygame.display.flip=lambda:presented(original_flip)
    pygame.display.update=lambda *a,**kw:presented(original_update,*a,**kw)
try:
    sys.path.insert(0,str(root)); sys.path.insert(0,str((root/entry).parent))
    sys.settrace(trace)
    runpy.run_path(str(root/entry),run_name='__main__')
except SmokeComplete: pass
except SystemExit as exc:
    if exc.code not in (0,None): raise
finally:
    sys.settrace(None)
    if renderer=='pygame': pygame.quit()
    print('CODER_OBSERVED:'+json.dumps(dict(frames=frames,inputs=inputs,game_lines=game_lines,
                                           loop_cycles=loop_cycles,waiting_for_input=waiting,pixel_colors=pixel_colors)),flush=True)
