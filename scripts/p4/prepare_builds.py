"""Prepare fresh fixed-commit copies for actual ORT/MNN Nuitka comparisons."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile


COMMIT = '3c912d2542ba4680b51d33a97ae2d89a2ba836bf'
repo = Path(__file__).resolve().parents[2]
work = Path(sys.argv[1]).resolve()
manifest = json.loads(Path(__file__).with_name('models.json').read_text(encoding='utf-8'))
archive = work/'baseline-source.zip'
if not archive.exists():
    subprocess.run(['git', 'archive', '--format=zip', '-o', str(archive), COMMIT], cwd=repo, check=True)
for candidate in (sys.argv[2:] or ('ort-v6', 'mnn-v6')):
    source = work/(candidate+'-source')
    source.mkdir(exist_ok=False)
    with zipfile.ZipFile(archive) as zipped:
        for name in zipped.namelist():
            if not (source/name).resolve().is_relative_to(source):
                raise ValueError('Unexpected archive path')
        zipped.extractall(source)
    metadata = {'source_root': str(source), 'base_commit': COMMIT,
                'candidate': candidate, 'engine': manifest[candidate]['engine']}
    (source/'p4-build.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    (source/'p4_models.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    (source/'ocr_models').mkdir()
    for info in manifest[candidate]['files'].values():
        shutil.copy2(work/'models'/info['file'], source/'ocr_models'/info['file'])
    for local, target in [('probe.py', 'p4_probe.py'), ('build_candidate.py', 'p4_build.py')]:
        shutil.copy2(Path(__file__).with_name(local), source/target)
    entry = source/'main.py'
    prefix = '''# P4 isolated measurement entry; not part of production behavior.
import sys
if __name__ == '__main__' and sys.argv[1:2] == ['--p4-ocr-probe']:
    from p4_probe import main as _p4_probe_main
    raise SystemExit(_p4_probe_main(sys.argv[2:]))

'''
    entry.write_text(prefix+entry.read_text(encoding='utf-8'), encoding='utf-8')
    print('Prepared', candidate, 'from', COMMIT)
