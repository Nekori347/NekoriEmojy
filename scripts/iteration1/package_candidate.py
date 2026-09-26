"""Package a verified standalone tree, local third-party notices and matching source.

Run with the same baseline venv as build_nuitka.py. Does not build or publish.
"""
import argparse
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.release_policy import assert_clean_release

parser = argparse.ArgumentParser()
parser.add_argument('--output', required=True, type=Path)
args = parser.parse_args()
output = args.output.resolve()
output.mkdir(parents=True, exist_ok=True)
release = REPO / 'dist/NekoriEmojy_Release'
assert_clean_release(release)
commit = subprocess.check_output(['git', '-C', str(REPO), 'rev-parse', 'HEAD'], text=True).strip()
if subprocess.check_output(['git', '-C', str(REPO), 'status', '--porcelain'], text=True).strip():
    raise RuntimeError('Commit candidate sources before packaging')

licenses = release / 'licenses'
licenses.mkdir(exist_ok=True)
components = []
for name in ('certifi', 'charset-normalizer', 'darkdetect', 'idna', 'keyboard', 'Pillow',
             'pynput', 'PySide6', 'PySide6-Essentials', 'PySide6-Addons',
             'PySide6-Fluent-Widgets', 'PySideSix-Frameless-Window', 'pywin32',
             'requests', 'shiboken6', 'six', 'urllib3', 'Nuitka', 'imageio-ffmpeg'):
    dist = metadata.distribution(name)
    dest = licenses / name
    for item in dist.files or []:
        if not any(word in item.name.upper() for word in ('LICENSE', 'NOTICE', 'COPYING')):
            continue
        origin = Path(dist.locate_file(item))
        if not origin.is_file():
            continue
        # Preserve path suffixes to avoid overwriting identically named licenses.
        relative = Path(*item.parts[1:]) if len(item.parts) > 1 else Path(item.name)
        target = dest / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origin, target)
    components.append({'name': name, 'version': dist.version,
                       'license': dist.metadata.get('License-Expression') or dist.metadata.get('License', ''),
                       'project': dist.metadata.get_all('Project-URL') or [dist.metadata.get('Home-page', '')]})
shutil.copy2(Path(sys.base_prefix) / 'LICENSE.txt', licenses / 'Python-LICENSE.txt')
ffmpeg = release / 'bin/ffmpeg/ffmpeg.exe'
ffmpeg_info = subprocess.check_output([str(ffmpeg), '-L'], stderr=subprocess.STDOUT, text=True, encoding='utf-8')
(licenses / 'FFmpeg-build-license.txt').write_text(ffmpeg_info, encoding='utf-8')
(release / 'THIRD_PARTY_NOTICES.md').write_text('''# Third-party notices

NekoriEmojy derives from IxinorTyan/SuzuEmojy under GPL-3.0. See LICENSE.
Bundled Python, Qt/PySide, Pillow, Requests and other runtime components retain
their licenses and copyright notices in licenses/. Component metadata records
the exact build environment, not a claim that every file of every package ships.
Nuitka is the compiler (its runtime exception is included). imageio-ffmpeg is
used only to locate the bundled FFmpeg executable; its Python wrapper does not ship.
FFmpeg build configuration and license output are in licenses/FFmpeg-build-license.txt.
Qt/PySide wheels declare LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only in metadata;
their wheel-provided license files are preserved as supplied.

Source projects: https://github.com/Nekori347/NekoriEmojy,
https://github.com/IxinorTyan/SuzuEmojy,
https://www.python.org/downloads/source/,
https://code.qt.io/cgit/pyside/pyside-setup.git/,
https://code.qt.io/cgit/qt/,
https://ffmpeg.org/download.html,
https://github.com/imageio/imageio-ffmpeg,
https://github.com/Nuitka/Nuitka.
Additional project links and versions are recorded in BUILD_INFO.json.

This is a release candidate pending the planned final review, not a signed installer.
''', encoding='utf-8')
info = {'version': '0.1.0-rc1', 'source_commit': commit, 'python': sys.version.split()[0],
        'cpu_target': 'x86-64-v3 / AVX2', 'ocr_included': False, 'components': components}
(release / 'BUILD_INFO.json').write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding='utf-8')
assert_clean_release(release)
files = sorted(path for path in release.rglob('*') if path.is_file())
for path in files:
    if any(part.lower() in {'numpy', 'cv2', 'onnxruntime', 'rapidocr', 'mnn', 'tessdata', 'models'} for part in path.relative_to(release).parts):
        raise RuntimeError('Deferred OCR/dependency leaked into package: ' + str(path))
target = output / 'NekoriEmojy-0.1.0-rc1-windows-x64.zip'
with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zipped:
    for path in files:
        zipped.write(path, Path('NekoriEmojy') / path.relative_to(release))
source = output / 'NekoriEmojy-0.1.0-rc1-source.zip'
subprocess.run(['git', '-C', str(REPO), 'archive', '--format=zip', '--prefix=NekoriEmojy/',
                '--output=' + str(source), commit], check=True)
report = {'source_commit': commit, 'files': len(files), 'unpacked_bytes': sum(p.stat().st_size for p in files),
          'zip_bytes': target.stat().st_size, 'zip_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
          'source_zip_sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'release_policy': 'passed',
          'ocr_included': False}
(output / 'package-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
(output / 'SHA256SUMS.txt').write_text(report['zip_sha256'] + '  ' + target.name + '\n' +
                                     report['source_zip_sha256'] + '  ' + source.name + '\n', encoding='utf-8')
print(json.dumps(report, indent=2))
