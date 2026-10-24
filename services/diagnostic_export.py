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
