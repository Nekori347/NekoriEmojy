"""Bounded, read-only Windows fault and hang lookups during existing report generation."""
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


_PROVIDERS = {1000: 'Application Error', 1002: 'Application Hang'}


def match_fault(session,xml_events,now=None,*,event_id=1000):
    """PID alone is never sufficient. Old sessions safely yield unknown."""
    unknown=lambda reason:dict(status='unknown',reason=reason)
    if not session.get('process_created') or not session.get('executable_hash'):return unknown('identity_unavailable')
    now=time.time() if now is None else now;matches=[]
    identity_problem = None
    ns={'e':'http://schemas.microsoft.com/win/2004/08/events/event'}
    for xml in xml_events:
        if len(xml)>65536:continue
        try:
            event=ET.fromstring(xml);system=event.find('e:System',ns)
            if system.findtext('e:EventID',namespaces=ns)!=str(event_id):continue
            if system.find('e:Provider',ns).get('Name')!=_PROVIDERS[event_id]:continue
            stamp=system.find('e:TimeCreated',ns).get('SystemTime')
            occurred=datetime.fromisoformat(stamp.replace('Z','+00:00')).timestamp()
            if not session['started_at']-5<=occurred<=now+5:continue
            data={v.get('Name'):v.text or '' for v in event.findall('e:EventData/e:Data',ns)}
            if int(data['ProcessId'],0)!=session['pid']:continue
            creation = data.get('StartTime' if event_id == 1002 else 'ProcessCreationTime')
            path = data.get('ExeFileName' if event_id == 1002 else 'AppPath')
            if not creation or not path or not ntpath.isabs(path):
                identity_problem = 'incomplete_identity'
                continue
            if int(creation,0)!=session['process_created'] or _image_hash(path)!=session['executable_hash']:
                identity_problem = 'different_process'
                continue
            if event_id == 1002:
                matches.append(dict(status='matched', event_id=1002, pid=session['pid'], occurred_at=occurred))
                continue
            fault = dict(status='matched', event_id=1000, pid=session['pid'], occurred_at=occurred)
            module = ntpath.basename(data.get('ModuleName', ''))
            if re.fullmatch(r'[A-Za-z0-9_.+-]{1,128}', module):
                fault['module'] = module
            code = data.get('ExceptionCode', '').lower().removeprefix('0x')
            offset = data.get('FaultingOffset', '').lower().removeprefix('0x')
            if re.fullmatch(r'[0-9a-f]{1,8}', code):
                fault['exception_code'] = f'0x{int(code,16):08x}'
            if re.fullmatch(r'[0-9a-f]{1,16}', offset):
                fault['module_offset'] = f'0x{int(offset,16):x}'
            matches.append(fault)
        except (ET.ParseError,AttributeError,KeyError,TypeError,ValueError):continue
    return matches[0] if len(matches)==1 else unknown('ambiguous' if matches else (identity_problem or 'not_found'))


def _read_events(session,now,event_id=1000):
    import win32evtlog as events
    since=datetime.fromtimestamp(max(session['started_at']-5,now-14*86400),timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')
    until=datetime.fromtimestamp(now+5,timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.999Z')
    # Filter before reading; no unrelated event text is saved or exported.
    query=(f"*[System[Provider[@Name='{_PROVIDERS[event_id]}'] and EventID={event_id} and "
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


def query_fault(session, *, event_id=1000):
    if sys.platform!='win32' or not session.get('process_created') or not session.get('executable_hash'):
        return dict(status='unknown',reason='identity_unavailable')
    try:
        now=min(time.time(),session.get('observed_end',float('inf')))
        events,truncated=_read_events(session,now,event_id)
        if truncated:return dict(status='unknown',reason='query_limit')
        return match_fault(session,events,now,event_id=event_id)
    except Exception:
        # Optional OS evidence never blocks a local report or application startup.
        return dict(status='unknown',reason='query_unavailable')
