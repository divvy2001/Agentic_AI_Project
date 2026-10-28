"""Windows native Godot isolation: no network capabilities, scoped file ACLs and a Job.

No fallback to an unrestricted Godot process. Windows 8+ AppContainer is required.
The caller owns an isolated staging directory containing game data, not credentials.
"""
import ctypes as ct
from ctypes import wintypes as W
import os, subprocess, time, uuid, tempfile
from contextlib import contextmanager
from pathlib import Path

class SandboxUnavailable(RuntimeError): pass

@contextmanager
def _native_lock():
    # icacls propagates inherited ACEs asynchronously across a shared runtime tree.
    # Serialize grant/run/revoke across threads and processes to prevent lost grants.
    if os.name!='nt':raise SandboxUnavailable('windows_appcontainer_required')
    import msvcrt
    filename=Path(tempfile.gettempdir())/'logic-coder-native-acl.lock'
    with filename.open('a+b') as handle:
        handle.seek(0,2)
        if handle.tell()==0:handle.write(b'0');handle.flush()
        deadline=time.monotonic()+60
        while True:
            handle.seek(0)
            try:msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1);break
            except OSError:
                if time.monotonic()>=deadline:raise SandboxUnavailable('native_runtime_busy')
                time.sleep(.1)
        try:yield
        finally:handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)

def launch(binary, args, root, env, timeout=20, output_limit=32768, read_dirs=(), stdin=None,
           interactive=False, on_started=None):
    with _native_lock():
        return _launch(binary,args,root,env,timeout,output_limit,read_dirs,stdin,interactive,on_started)

def _launch(binary, args, root, env, timeout=20, output_limit=32768, read_dirs=(), stdin=None,
            interactive=False, on_started=None):
    if os.name!='nt': raise SandboxUnavailable('windows_appcontainer_required')
    root=Path(root).resolve(); binary=Path(binary).resolve()
    if binary.name.endswith('_console.exe'):
        direct=binary.with_name(binary.name.replace('_console.exe','.exe'))
        if direct.is_file(): binary=direct
    if not binary.is_file(): raise SandboxUnavailable('godot_binary_missing')
    k=ct.WinDLL('kernel32',use_last_error=True)
    adv=ct.WinDLL('advapi32',use_last_error=True)
    user=ct.WinDLL('userenv',use_last_error=True)
    P=ct.c_void_p; SZ=ct.c_size_t
    class SECATTR(ct.Structure): _fields_=[('length',W.DWORD),('descriptor',P),('inherit',W.BOOL)]
    class STARTUP(ct.Structure):
        _fields_=[('cb',W.DWORD),('reserved',W.LPWSTR),('desktop',W.LPWSTR),('title',W.LPWSTR),
                  ('x',W.DWORD),('y',W.DWORD),('xs',W.DWORD),('ys',W.DWORD),('xc',W.DWORD),('yc',W.DWORD),
                  ('fill',W.DWORD),('flags',W.DWORD),('show',W.WORD),('reserved2len',W.WORD),('reserved2',P),
                  ('stdin',W.HANDLE),('stdout',W.HANDLE),('stderr',W.HANDLE)]
    class STARTUPEX(ct.Structure): _fields_=[('startup',STARTUP),('attrs',P)]
    class PROCINFO(ct.Structure): _fields_=[('process',W.HANDLE),('thread',W.HANDLE),('pid',W.DWORD),('tid',W.DWORD)]
    class CAPS(ct.Structure): _fields_=[('sid',P),('capabilities',P),('count',W.DWORD),('reserved',W.DWORD)]
    class BASICLIMIT(ct.Structure):
        _fields_=[('process_time',ct.c_longlong),('job_time',ct.c_longlong),('flags',W.DWORD),
                  ('min_ws',SZ),('max_ws',SZ),('active',W.DWORD),('affinity',SZ),('priority',W.DWORD),('scheduling',W.DWORD)]
    class IO(ct.Structure): _fields_=[(n,ct.c_ulonglong) for n in ('read_ops','write_ops','other_ops','read_bytes','write_bytes','other_bytes')]
    class LIMIT(ct.Structure): _fields_=[('basic',BASICLIMIT),('io',IO),('process_memory',SZ),('job_memory',SZ),('peak_process',SZ),('peak_job',SZ)]
    def sig(dll,name,restype,args):
        f=getattr(dll,name);f.restype=restype;f.argtypes=args;return f
    create_profile=sig(user,'CreateAppContainerProfile',ct.c_long,[W.LPCWSTR,W.LPCWSTR,W.LPCWSTR,P,W.DWORD,ct.POINTER(P)])
    delete_profile=sig(user,'DeleteAppContainerProfile',ct.c_long,[W.LPCWSTR])
    convert_sid=sig(adv,'ConvertSidToStringSidW',W.BOOL,[P,ct.POINTER(W.LPWSTR)])
    free_sid=sig(adv,'FreeSid',P,[P]); localfree=sig(k,'LocalFree',P,[P])
    initattrs=sig(k,'InitializeProcThreadAttributeList',W.BOOL,[P,W.DWORD,W.DWORD,ct.POINTER(SZ)])
    updateattrs=sig(k,'UpdateProcThreadAttribute',W.BOOL,[P,W.DWORD,SZ,P,SZ,P,P])
    delattrs=sig(k,'DeleteProcThreadAttributeList',None,[P])
    createfile=sig(k,'CreateFileW',W.HANDLE,[W.LPCWSTR,W.DWORD,W.DWORD,ct.POINTER(SECATTR),W.DWORD,W.DWORD,W.HANDLE])
    createproc=sig(k,'CreateProcessW',W.BOOL,[W.LPCWSTR,W.LPWSTR,P,P,W.BOOL,W.DWORD,P,W.LPCWSTR,ct.POINTER(STARTUPEX),ct.POINTER(PROCINFO)])
    close=sig(k,'CloseHandle',W.BOOL,[W.HANDLE])
    createjob=sig(k,'CreateJobObjectW',W.HANDLE,[P,W.LPCWSTR])
    setjob=sig(k,'SetInformationJobObject',W.BOOL,[W.HANDLE,ct.c_int,P,W.DWORD])
    assign=sig(k,'AssignProcessToJobObject',W.BOOL,[W.HANDLE,W.HANDLE])
    terminatejob=sig(k,'TerminateJobObject',W.BOOL,[W.HANDLE,W.UINT])
    terminateproc=sig(k,'TerminateProcess',W.BOOL,[W.HANDLE,W.UINT])
    resume=sig(k,'ResumeThread',W.DWORD,[W.HANDLE])
    exitcode=sig(k,'GetExitCodeProcess',W.BOOL,[W.HANDLE,ct.POINTER(W.DWORD)])
    wait=sig(k,'WaitForSingleObject',W.DWORD,[W.HANDLE,W.DWORD])
    opentoken=sig(adv,'OpenProcessToken',W.BOOL,[W.HANDLE,W.DWORD,ct.POINTER(W.HANDLE)])
    tokeninfo=sig(adv,'GetTokenInformation',W.BOOL,[W.HANDLE,ct.c_int,P,W.DWORD,ct.POINTER(W.DWORD)])
    def check(ok,label):
        if not ok: raise SandboxUnavailable(label+': '+str(ct.WinError(ct.get_last_error())))
    def acl(target,*options):
        r=subprocess.run(['icacls',str(target),*options],capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=120)
        if r.returncode: raise SandboxUnavailable('sandbox_acl_failed: '+r.stderr[-500:])
    name='LogicCoder.'+uuid.uuid4().hex
    sid=P(); sidstr=W.LPWSTR(); attrs=None; allocated=False; handles=[]; job=None; info=PROCINFO(); token=W.HANDLE()
    granted=[]; started=time.monotonic(); completed=False
    logfile=root/'runtime_stdout.log'
    try:
        hr=create_profile(name,name,'Ephemeral offline Logic Coder Godot smoke',None,0,ct.byref(sid))
        if hr<0: raise SandboxUnavailable('CreateAppContainerProfile HRESULT '+hex(hr & 0xffffffff))
        allocated=True; check(convert_sid(sid,ct.byref(sidstr)),'sid_to_string'); sidtext=sidstr.value
        grants=[(root,'(OI)(CI)M'),(binary.parent,'RX'),(binary,'RX')]
        grants.extend((Path(directory).resolve(),'(OI)(CI)RX') for directory in read_dirs)
        for target,permission in grants:
            acl(target,'/grant',f'*{sidtext}:{permission}','/Q');granted.append(target)
        acl(root,'/setintegritylevel','(OI)(CI)L','/T','/Q')
        for directory in ('home','home/AppData/Roaming','home/AppData/Local','tmp'):(root/directory).mkdir(parents=True,exist_ok=True)
        env=dict(env,USERPROFILE=str(root/'home'),HOME=str(root/'home'),APPDATA=str(root/'home/AppData/Roaming'),
                 LOCALAPPDATA=str(root/'home/AppData/Local'),TEMP=str(root/'tmp'),TMP=str(root/'tmp'),
                 PATH=str(binary.parent)+os.pathsep+str(Path(os.environ['SYSTEMROOT'])/'System32'))
        sa=SECATTR(ct.sizeof(SECATTR),None,True)
        # The Terminal child owns a new console. Its hidden host stays alive to
        # revoke ACLs even when the user closes the Terminal window with X.
        # Existing smoke/eval callers retain redirected IO and no console.
        output=createfile(str(logfile),0x40000000,3,ct.byref(sa),2,0x80,None)
        check(output not in (None,ct.c_void_p(-1).value),'stdout_file');handles.append(output)
        input_path='NUL'
        if stdin is not None:
            input_file=root/'runtime_stdin.txt'
            input_file.write_text(stdin,encoding='utf-8')
            input_path=str(input_file)
        null=createfile(input_path,0x80000000,3,ct.byref(sa),3,0x80,None)
        check(null not in (None,ct.c_void_p(-1).value),'stdin_null');handles.append(null)
        size=SZ();initattrs(None,1,0,ct.byref(size));buf=ct.create_string_buffer(size.value);attrs=ct.cast(buf,P)
        check(initattrs(attrs,1,0,ct.byref(size)),'initialize_attributes')
        caps=CAPS(sid,None,0,0)
        check(updateattrs(attrs,0,0x20009,ct.byref(caps),ct.sizeof(caps),None,None),'security_capabilities')
        si=STARTUPEX();si.startup.cb=ct.sizeof(si);si.startup.flags=0 if interactive else 0x100;si.startup.stdin=null;si.startup.stdout=output;si.startup.stderr=output;si.attrs=attrs
        command=ct.create_unicode_buffer(subprocess.list2cmdline([str(binary),*args]))
        environment=ct.create_unicode_buffer('\0'.join(f'{key}={value}' for key,value in sorted(env.items(),key=lambda x:x[0].upper()))+'\0\0')
        job=createjob(None,None);check(job,'create_job')
        limits=LIMIT();limits.basic.flags=0x2000|0x8;limits.basic.active=1
        check(setjob(job,9,ct.byref(limits),ct.sizeof(limits)),'configure_job')
        flags=0x80000|0x400|0x4|(0x10 if interactive else 0x08000000)
        check(createproc(str(binary),command,None,None,not interactive,flags,environment,str(root),ct.byref(si),ct.byref(info)),'create_appcontainer_process')
        handles.extend([info.process,info.thread])
        check(assign(job,info.process),'assign_job')
        check(opentoken(info.process,8,ct.byref(token)),'open_process_token'); handles.append(token)
        is_container=W.DWORD();needed=W.DWORD()
        check(tokeninfo(token,29,ct.byref(is_container),ct.sizeof(is_container),ct.byref(needed)),'query_appcontainer_token')
        if is_container.value!=1: raise SandboxUnavailable('process_token_is_not_appcontainer')
        check(resume(info.thread)!=0xffffffff,'resume_sandbox_process')
        if on_started:
            on_started(info.pid)
        reason=None; code=W.DWORD(259)
        while True:
            check(exitcode(info.process,ct.byref(code)),'get_process_exit')
            if logfile.exists() and logfile.stat().st_size>output_limit: reason='output_limit';break
            if code.value!=259: break
            if time.monotonic()-started>timeout:reason='timeout';break
            time.sleep(.02)
        if reason:terminatejob(job,124);wait(info.process,3000);exitcode(info.process,ct.byref(code))
        completed=True
        output_text=logfile.read_bytes()[:output_limit].decode('utf-8',errors='replace') if logfile.is_file() else ''
        return dict(argv=[str(binary),*args],returncode=code.value,output=output_text,reason=reason,seconds=round(time.monotonic()-started,3),
                    sandbox=dict(kind='windows_appcontainer',token_is_appcontainer=True,network_capabilities=[],active_process_limit=1))
    except OSError as exc:
        raise SandboxUnavailable(str(exc)) from exc
    finally:
        if info.process and not completed:terminateproc(info.process,125);wait(info.process,3000)
        if job:close(job)
        for handle in reversed(handles):close(handle)
        if attrs:delattrs(attrs)
        cleanup=[]
        if sidstr:
            for target in reversed(granted):
                try:acl(target,'/remove:g','*'+sidstr.value,'/Q')
                except Exception as exc:cleanup.append(str(exc))
            localfree(sidstr)
        if sid:free_sid(sid)
        if allocated:
            hr=delete_profile(name)
            if hr<0:cleanup.append('DeleteAppContainerProfile '+hex(hr & 0xffffffff))
        if cleanup: raise SandboxUnavailable('sandbox_cleanup_failed: '+'; '.join(cleanup))
