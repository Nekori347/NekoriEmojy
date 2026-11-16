"""One bounded, read-only Event 1000 lookup during existing report generation."""
import hashlib
import ntpath
import re
import sys
import time
from datetime import datetime,timezone
from xml.etree import ElementTree as ET


def _image_hash(path):
    return hashlib.sha256(ntpath.normcase(ntpath.normpath(path.removeprefix('\\\\?\\'))).encode()).hexdigest()


def process_identity():
    if sys.platform!='win32':return {}
    try:
        import ctypes
        from ctypes import wintypes as W
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.GetCurrentProcess.restype=W.HANDLE
        kernel.GetProcessTimes.argtypes=[W.HANDLE]+[ctypes.POINTER(W.FILETIME)]*4
        kernel.GetModuleFileNameW.argtypes=[W.HMODULE,W.LPWSTR,W.DWORD]
        created,exited,cpu,user=(W.FILETIME() for _ in range(4))
        if not kernel.GetProcessTimes(kernel.GetCurrentProcess(),*(ctypes.byref(v) for v in (created,exited,cpu,user))):return {}
        name=ctypes.create_unicode_buffer(32768)
        if not kernel.GetModuleFileNameW(None,name,len(name)):return {}
        return dict(process_created=(created.dwHighDateTime<<32)|created.dwLowDateTime,
                    executable_hash=_image_hash(name.value))
    except (OSError,AttributeError,ValueError):return {}


def match_fault(session,xml_events,now=None):
    """PID alone is never sufficient. Old sessions safely yield unknown."""
    unknown=lambda reason:dict(status='unknown',reason=reason)
    if not session.get('process_created') or not session.get('executable_hash'):return unknown('identity_unavailable')
    now=time.time() if now is None else now;matches=[]
    ns={'e':'http://schemas.microsoft.com/win/2004/08/events/event'}
    for xml in xml_events:
        if len(xml)>65536:continue
        try:
            event=ET.fromstring(xml);system=event.find('e:System',ns)
            if system.findtext('e:EventID',namespaces=ns)!='1000':continue
            if system.find('e:Provider',ns).get('Name')!='Application Error':continue
            stamp=system.find('e:TimeCreated',ns).get('SystemTime')
            occurred=datetime.fromisoformat(stamp.replace('Z','+00:00')).timestamp()
            if not session['started_at']-5<=occurred<=now+5:continue
            data={v.get('Name'):v.text or '' for v in event.findall('e:EventData/e:Data',ns)}
            if int(data['ProcessId'],0)!=session['pid']:continue
            if int(data['ProcessCreationTime'],0)!=session['process_created']:continue
            if _image_hash(data['AppPath'])!=session['executable_hash']:continue
            module=ntpath.basename(data['ModuleName'])
            if not re.fullmatch(r'[A-Za-z0-9_.+-]{1,128}',module):continue
            code=int(data['ExceptionCode'].removeprefix('0x'),16)
            offset=int(data['FaultingOffset'].removeprefix('0x'),16)
            if not 0<=code<2**32 or not 0<=offset<2**64:continue
            matches.append(dict(status='matched',event_id=1000,pid=session['pid'],
                                occurred_at=occurred,exception_code=f'0x{code:08x}',
                                module=module,module_offset=f'0x{offset:x}'))
        except (ET.ParseError,AttributeError,KeyError,TypeError,ValueError):continue
    return matches[0] if len(matches)==1 else unknown('ambiguous' if matches else 'not_found')


def _read_events(session,now):
    import win32evtlog as events
    since=datetime.fromtimestamp(max(session['started_at']-5,now-14*86400),timezone.utc).isoformat()
    until=datetime.fromtimestamp(now+5,timezone.utc).isoformat()
    # Filter before reading; no unrelated event text is saved or exported.
    query=("*[System[Provider[@Name='Application Error'] and EventID=1000 and "
           f"TimeCreated[@SystemTime>='{since}' and @SystemTime<='{until}']] and "
           f"EventData[Data[@Name='ProcessId']='0x{session['pid']:x}']]")
    result=events.EvtQuery('Application',events.EvtQueryReverseDirection,query)
    xml=[]
    try:
        for _ in range(4):
            batch=events.EvtNext(result,8,50,0)
            if not batch:return xml,False
            for event in batch:
                try:
                    text=events.EvtRender(event,events.EvtRenderEventXml)
                    if len(text)<=65536:xml.append(text)
                finally:event.Close()
        return xml,True
    finally:result.Close()


def query_fault(session):
    if sys.platform!='win32' or not session.get('process_created') or not session.get('executable_hash'):
        return dict(status='unknown',reason='identity_unavailable')
    try:
        now=time.time();events,truncated=_read_events(session,now)
        if truncated:return dict(status='unknown',reason='query_limit')
        return match_fault(session,events,now)
    except Exception:
        # Optional OS evidence never blocks a local report or application startup.
        return dict(status='unknown',reason='query_unavailable')
