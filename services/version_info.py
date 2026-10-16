"""One release number, plus local build identity when running a Git checkout."""
import json
import subprocess
import sys
from functools import lru_cache
from services.update_service import current_version,install_root


@lru_cache(maxsize=1)
def version_info():
    root=install_root()
    metadata=json.loads((root/'version.json').read_text(encoding='utf-8'))
    result={'version':current_version(root),'channel':metadata.get('channel','development'),
            'commit':metadata.get('build_commit',''),'dirty':False}
    if not (getattr(sys,'frozen',False) or globals().get('__compiled__')) and (root/'.git').exists():
        options={'capture_output':True,'text':True,'timeout':2,'creationflags':getattr(subprocess,'CREATE_NO_WINDOW',0)}
        try:
            identity=subprocess.run(['git','-C',str(root),'rev-parse','--short=8','HEAD'],**options)
            if identity.returncode==0:
                result['commit']=identity.stdout.strip()
                result['dirty']=subprocess.run(['git','-C',str(root),'diff','--quiet','HEAD','--'],**options).returncode==1
        except (OSError,subprocess.TimeoutExpired):
            pass
    return result


def build_label():
    info=version_info()
    return info['channel']+(' · '+info['commit']+(' *' if info['dirty'] else '') if info['commit'] else '')
