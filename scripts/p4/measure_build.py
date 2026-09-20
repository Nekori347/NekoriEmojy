"""Measure a real Nuitka release tree and its actual level-6 ZIP archive."""
import hashlib
import json
from pathlib import Path
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.release_policy import assert_clean_release


def group(name):
    lowered = name.lower()
    if '/ocr_models/' in lowered:
        return 'models'
    if '/cv2/' in lowered:
        return 'opencv'
    if '/numpy' in lowered:
        return 'numpy'
    if 'onnxruntime' in lowered or '_mnncengine' in lowered or 'tesserocr' in lowered:
        return 'ocr_runtime'
    if 'shapely' in lowered or 'geos' in lowered or 'pyclipper' in lowered:
        return 'geometry_dependencies'
    if lowered.endswith('/bin/nekoriemojy.exe'):
        return 'application_and_compiled_python'
    return 'other_application_files'


def measure(release, output, label):
    assert_clean_release(release)
    archive = output.with_suffix('.zip')
    if archive.exists() or output.exists():
        raise FileExistsError('Keep previous measurements; choose a fresh output name')
    files = sorted(p for p in release.rglob('*') if p.is_file())
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zipped:
        for path in files:
            zipped.write(path, 'NekoriEmojy_Release/'+path.relative_to(release).as_posix())
    inventory, totals = [], {}
    with zipfile.ZipFile(archive) as zipped:
        if zipped.testzip() is not None:
            raise RuntimeError('ZIP integrity check failed')
        for info in zipped.infolist():
            category = group(info.filename)
            row = {'path': info.filename, 'bytes': info.file_size,
                   'compressed_bytes': info.compress_size, 'group': category}
            inventory.append(row)
            summary = totals.setdefault(category, {'bytes': 0, 'compressed_bytes': 0})
            summary['bytes'] += info.file_size
            summary['compressed_bytes'] += info.compress_size
    report = {'label': label, 'baseline_commit': '3c912d2542ba4680b51d33a97ae2d89a2ba836bf',
              'zip_method': 'Python zipfile ZIP_DEFLATED level 6',
              'zip_bytes': archive.stat().st_size,
              'zip_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
              'unpacked_bytes': sum(p.stat().st_size for p in files), 'file_count': len(files),
              'zip_integrity': 'passed', 'no_user_data_policy': 'passed',
              'runtime_acceptance': 'recorded separately; successful compilation is insufficient',
              'groups': totals, 'inventory': inventory}
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('label', 'zip_bytes', 'unpacked_bytes', 'groups')}, ensure_ascii=False))


if __name__ == '__main__':
    measure(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve(), sys.argv[3])
