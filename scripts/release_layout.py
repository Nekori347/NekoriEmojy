"""Positive release inventory. Developer trees are never packaging inputs."""
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
FILES=('main.py','requirements.txt','ocr-component.json','ico.ico','README.md','LICENSE','THIRD_PARTY_NOTICES.md')
PACKAGES=('fluent_ui/','services/')
LANGUAGES=tuple('translations/'+lang+'.json' for lang in ('zh','en','ja','zh_TW'))
SOURCE_OVERRIDES={'README.md':'docs/PACKAGE_README.md'}
GENERATED=('SuzuEmojy.exe','SuzuEmojyUpdater.exe','version.json','BUILD_INFO.json')

def source_files():
    # Git defines the reviewed source/resource set; caches/untracked data cannot leak in.
    paths=subprocess.check_output(['git','-C',str(ROOT),'ls-files','-z'],text=True,encoding='utf-8').split('\0')
    result=set(FILES+LANGUAGES)
    for name in paths:
        if name.startswith(PACKAGES) and (name.endswith('.py') or name.startswith('fluent_ui/assets/')):
            result.add(name)
    for name in result:
        if not (ROOT/SOURCE_OVERRIDES.get(name,name)).is_file():raise FileNotFoundError(name)
    return result

def allowed_files(flavor,compiler_files=None):
    if flavor=='lightweight':return source_files()|set(GENERATED)
    if flavor!='standalone' or compiler_files is None:
        raise ValueError('Standalone packaging requires its fresh compiler dependency inventory')
    names=set(compiler_files)
    if any(not n.startswith('bin/') or '..' in Path(n).parts or Path(n).is_absolute() for n in names):
        raise ValueError('Invalid compiler dependency path')
    return set(FILES[3:])|set(GENERATED)|names

def validate_layout(directory,flavor,compiler_files=None):
    allowed=allowed_files(flavor,compiler_files)
    actual={p.relative_to(directory).as_posix() for p in Path(directory).rglob('*') if p.is_file()}
    from services.update_protocol import MANIFEST
    unexpected=actual-allowed-{MANIFEST}
    if unexpected:raise ValueError('Files outside release allowlist: '+', '.join(sorted(unexpected)))
    return sorted(actual-{MANIFEST})
