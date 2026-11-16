"""User-requested, bounded, redacted diagnostics; never read Library contents."""
import json
import platform
import re
import zipfile
from pathlib import Path
from services.app_paths import app_data_dir
from services.crash_evidence import LOG_BYTES, _version, context_snapshot
from services.export_control import staged_export_path, check_export_cancelled
from services.i18n import t


def redact(text):
    # Do not retain absolute directories, URL credentials/queries or account IDs.
    text=re.sub(r'https?://[^\s<>"\']+', '<url>', text, flags=re.I)
    text=re.sub(r'(?i)\b(?:bearer|basic)\s+[A-Za-z0-9+/=._-]+', '<credential>', text)
    text=re.sub(r'(?im)^([^\r\n]*?\b(?:authorization|cookie)\s*[:=])[^\r\n]*',r'\1 <redacted>',text)
    text=re.sub(r'''(?ix)(["']?(?:authorization|cookie|token|access_token|refresh_token|api[_-]?key|password|passwd|secret)["']?\s*[:=]\s*)(?:"[^"\r\n]*"|'[^'\r\n]*'|[^\s,;]+)''',r'\1<redacted>',text)
    def filename(match):
        value=match.group(0).replace('\\','/')
        name=value.rsplit('/',1)[-1]
        # Native traceback code filenames help diagnosis; non-code names don't.
        return '<path>/'+name if re.fullmatch(r'[A-Za-z0-9_.-]+\.py',name) else '<path>'
    text=re.sub(r'''(?:[A-Za-z]:[\\/]|\\\\)[^\r\n"'<>]*''',filename,text)
    text=re.sub(r'''(?<![\w<])/(?:home|Users|tmp|mnt|opt|var)/[^\r\n"'<>]*''',filename,text)
    return re.sub(r'\b\d{5,}\b','<id>',text)


def diagnostic_files(directory):
    directory=Path(directory)
    if not directory.exists():return []
    if directory.is_symlink():raise ValueError('Diagnostics directory is a link')
    files=[directory/name for name in ('exceptions.log','exceptions.log.1','exceptions.log.2')]
    files+=sorted(directory.glob('fatal-*.log'),key=lambda p:p.stat().st_mtime,reverse=True)[:2]
    return [p for p in files if p.is_file() and not p.is_symlink()]


def export_diagnostics(target,progress=lambda *_:None,cancel=None):
    files=diagnostic_files(app_data_dir()/'diagnostics')
    metadata=dict(version=_version(),python=platform.python_version(),system=platform.system(),
                  system_release=platform.release(),system_version=platform.version(),machine=platform.machine(),
                  log_file_limit_bytes=LOG_BYTES,logs=len(files),
                  scope='Redacted application diagnostics only; no settings, images, Library or credentials.')
    metadata['runtime_context']=context_snapshot()
    try:
        from PySide6.QtCore import qVersion
        metadata['qt']=qVersion()
    except ImportError:pass
    with staged_export_path(target,cancel) as temporary:
        with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('environment.json',json.dumps(metadata,ensure_ascii=False,indent=2))
            for i,path in enumerate(files):
                check_export_cancelled(cancel)
                with path.open('rb') as stream:data=stream.read(LOG_BYTES)
                text=redact(data.decode('utf-8',errors='replace'))
                data=text.encode('utf-8')[:LOG_BYTES].decode('utf-8',errors='ignore')
                archive.writestr(f'logs/{i+1:02d}-'+('native.log' if path.name.startswith('fatal-') else 'exceptions.log'),data)
                progress(i+1,len(files),t('写入脱敏诊断日志'))
    return len(files)


# Automatic reports consume saved candidates only; manual export remains unchanged.
REPORT_LIMIT = 8
REPORT_BYTES = 1024 * 1024
REPORT_TOTAL_BYTES = 8 * REPORT_BYTES
_report_lock = __import__('threading').Lock()


def report_path(identity):
    if not re.fullmatch(r'[a-f0-9]{32}',identity):raise ValueError('Invalid session identity')
    return app_data_dir()/'diagnostics'/'reports'/('session-'+identity+'.zip')


def _candidate_digest(candidate):
    import hashlib
    return hashlib.sha256(json.dumps({key:candidate.get(key) for key in ('session','assessment','evidence_kind','native_complete','evidence')},sort_keys=True,ensure_ascii=False).encode('utf-8')).hexdigest()


def valid_automatic_report(path, candidate):
    try:
        if path.is_symlink() or not 0<path.stat().st_size<=REPORT_BYTES:return False
        with zipfile.ZipFile(path) as archive:
            members=archive.infolist()
            if (len(members)>6 or sum(x.file_size for x in members)>REPORT_BYTES
                or any(x.filename not in {'report.json','README.txt',*[f'evidence/{i}.txt' for i in range(4)]} for x in members)):
                return False
            data=json.loads(archive.read('report.json'))
            return (data['session_id']==candidate['session']['id']
                    and data['candidate_sha256']==_candidate_digest(candidate)
                    and archive.testzip() is None)
    except (OSError,ValueError,KeyError,zipfile.BadZipFile,RuntimeError):return False


def _report_capacity(directory, protected, target):
    """Evict only owned reports; undisclosed candidates are pinned before publication."""
    # Staging files are never published evidence; saved candidates make them replayable.
    # Remove crash leftovers only in this function's exact owned namespace.
    for partial in directory.glob('.session-*.zip.part'):
        if re.fullmatch(r'\.session-[a-f0-9]{32}\.zip\.part',partial.name) and not partial.is_symlink():
            partial.unlink()
    owned=[p for p in directory.glob('session-*.zip')
           if re.fullmatch(r'session-[a-f0-9]{32}\.zip',p.name) and not p.is_symlink() and p!=target]
    owned.sort(key=lambda p:p.stat().st_mtime)
    count=len(owned);total=sum(p.stat().st_size for p in owned)
    for path in owned:
        if count<REPORT_LIMIT and total+REPORT_BYTES<=REPORT_TOTAL_BYTES:break
        if path.stem[8:] in protected:continue
        size=path.stat().st_size;path.unlink();count-=1;total-=size
    if count>=REPORT_LIMIT or total+REPORT_BYTES>REPORT_TOTAL_BYTES:raise OSError('Report capacity unavailable')


def export_automatic_report(candidate, protected=(), cancel=None):
    import os
    path=report_path(candidate['session']['id']);directory=path.parent
    directory.mkdir(parents=True,exist_ok=True)
    if directory.is_symlink() or path.is_symlink():raise OSError('Invalid reports destination')
    if valid_automatic_report(path,candidate):return path
    _report_capacity(directory,set(protected),path)
    temporary=directory/('.'+path.name+'.part')
    if temporary.is_symlink():raise OSError('Invalid report staging file')
    session=candidate['session']
    native=any(e['kind']=='native' and re.search(r'File [\"\']|(?:Current thread|Thread) 0x',e['text']) for e in candidate['evidence'])
    from services.windows_fault_event import query_fault
    native_fault=query_fault(session)
    metadata=dict(native_fault=native_fault,schema=1,session_id=session['id'],version=session['version'],started_at=session['started_at'],
                  assessment=candidate['assessment'],evidence_kind=candidate['evidence_kind'],
                  native_stack_available=native,native_writer_complete=candidate.get('native_complete',False),
                  session_environment=session.get('environment',{}),
                  report_environment=dict(python=platform.python_version(),system=platform.system(),qt=_qt_version()),
                  candidate_sha256=_candidate_digest(candidate))
    note=('Saved redacted diagnostics only. No Library, settings or browser data.\n'
          'The cause of the previous exit is not determined by this report.\n')
    if native_fault.get('status')!='matched':note+='No verified Windows Application Error match was available.\n'
    else:note+='The OS faulting module is a crash location, not proof of the root cause.\n'
    if not session.get('environment'):note+='Previous-session environment metadata was not captured by the older session format.\n'
    if not native:note+='No native stack was available. Evidence is insufficient to identify a crash cause.\n'
    if not candidate.get('native_complete',False):note+='Native writer completion was not confirmed within the bounded capture window.\n'
    try:
        check_export_cancelled(cancel)
        with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('report.json',json.dumps(metadata,ensure_ascii=False,indent=2))
            archive.writestr('README.txt',note)
            for i,entry in enumerate(candidate['evidence']):
                check_export_cancelled(cancel)
                archive.writestr(f'evidence/{i}.txt',redact(entry['text']).encode('utf-8')[:LOG_BYTES])
        if temporary.stat().st_size>REPORT_BYTES:raise ValueError('Automatic report budget exceeded')
        check_export_cancelled(cancel)
        os.replace(temporary,path)
        return path
    finally:
        try:temporary.unlink(missing_ok=True)
        except OSError:pass


def _qt_version():
    try:
        from PySide6.QtCore import qVersion
        return qVersion()
    except ImportError:return 'unknown'


def generate_pending_reports(cancel=None):
    """One startup worker at a time; filesystem/ZIP work never runs in the UI callback."""
    from services import crash_evidence as sessions
    if not _report_lock.acquire(blocking=False):return dict(ready=[],retry=False,busy=True)
    result=dict(ready=[],retry=False,busy=False)
    try:
        value=sessions.session_snapshot()
        if not value or value.get('unavailable'):return result
        protected={c['session']['id'] for c in value['pending'] if c.get('notification_state')!='dismissed'}
        for candidate in value['pending']:
            if cancel and cancel():break
            identity=candidate['session']['id']
            try:
                if candidate.get('capture_state','collecting')=='collecting' or candidate.get('native_complete') is False:
                    if not sessions.refresh_candidate(candidate):
                        result['retry']=True;continue
                    updated=sessions.session_snapshot()
                    if not updated or updated.get('unavailable'):continue
                    candidate=next((c for c in updated['pending'] if c['session']['id']==identity),None)
                    if candidate is None:continue
                export_automatic_report(candidate,protected,cancel)
                if cancel and cancel():break
                if sessions.update_candidate(identity,report_state='ready'):
                    result['ready'].append(identity)
            except Exception:
                # No resource text or raw error strings are persisted here.
                sessions.update_candidate(identity,report_state='failed')
        return result
    finally:_report_lock.release()
