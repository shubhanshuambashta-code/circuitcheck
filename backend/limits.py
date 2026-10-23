"""Hard per-process limits on supported hosts. Docker additionally isolates the worker."""
import os

def unix_limits():
    import resource
    from .config import ENGINE_TIMEOUT
    resource.setrlimit(resource.RLIMIT_CPU,(ENGINE_TIMEOUT,ENGINE_TIMEOUT+1))
    resource.setrlimit(resource.RLIMIT_AS,(1536*1024**2,1536*1024**2))
    resource.setrlimit(resource.RLIMIT_FSIZE,(100*1024**2,100*1024**2))

def windows_job(proc):
    """Nested Windows Job Object: 1.5 GiB memory, kill descendants on handle close.
    If the host sandbox disallows nested jobs, the caller fails explicitly.
    """
    if os.name!='nt':return None
    import ctypes as c
    from ctypes import wintypes as w
    class BASIC(c.Structure):
        _fields_=[('PerProcessUserTimeLimit',c.c_longlong),('PerJobUserTimeLimit',c.c_longlong),('LimitFlags',w.DWORD),('MinimumWorkingSetSize',c.c_size_t),('MaximumWorkingSetSize',c.c_size_t),('ActiveProcessLimit',w.DWORD),('Affinity',c.c_size_t),('PriorityClass',w.DWORD),('SchedulingClass',w.DWORD)]
    class IO(c.Structure):
        _fields_=[(name,c.c_ulonglong) for name in ('ReadOperationCount','WriteOperationCount','OtherOperationCount','ReadTransferCount','WriteTransferCount','OtherTransferCount')]
    class EXTENDED(c.Structure):
        _fields_=[('BasicLimitInformation',BASIC),('IoInfo',IO),('ProcessMemoryLimit',c.c_size_t),('JobMemoryLimit',c.c_size_t),('PeakProcessMemoryUsed',c.c_size_t),('PeakJobMemoryUsed',c.c_size_t)]
    kernel=c.WinDLL('kernel32',use_last_error=True)
    kernel.CreateJobObjectW.argtypes=[c.c_void_p,w.LPCWSTR];kernel.CreateJobObjectW.restype=w.HANDLE
    kernel.SetInformationJobObject.argtypes=[w.HANDLE,c.c_int,c.c_void_p,w.DWORD];kernel.SetInformationJobObject.restype=w.BOOL
    kernel.AssignProcessToJobObject.argtypes=[w.HANDLE,w.HANDLE];kernel.AssignProcessToJobObject.restype=w.BOOL
    kernel.CloseHandle.argtypes=[w.HANDLE];kernel.CloseHandle.restype=w.BOOL
    job=kernel.CreateJobObjectW(None,None)
    if not job:raise OSError(c.get_last_error(),'Could not create resource-limit job')
    info=EXTENDED();info.BasicLimitInformation.LimitFlags=0x2000|0x100|0x8
    info.BasicLimitInformation.ActiveProcessLimit=4
    info.ProcessMemoryLimit=1536*1024**2
    if not kernel.SetInformationJobObject(job,9,c.byref(info),c.sizeof(info)) or not kernel.AssignProcessToJobObject(job,w.HANDLE(int(proc._handle))):
        error=c.get_last_error();kernel.CloseHandle(job)
        raise OSError(error,'Could not enforce native engine resource limits')
    return lambda:kernel.CloseHandle(job)
