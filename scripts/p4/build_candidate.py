"""Build the fixed P3 application plus the isolated OCR measurement entry.

Run in a fresh source copy prepared by prepare_builds.py, using the P4 venv.
The application sources in the authoritative checkout are not modified.
"""
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
from unittest.mock import patch


root = Path.cwd().resolve()
marker = root/'p4-build.json'
if not marker.is_file():
    raise SystemExit('Run only in a prepared, task-owned P4 source copy')
settings = json.loads(marker.read_text(encoding='utf-8'))
if root != Path(settings['source_root']).resolve():
    raise SystemExit('P4 source root mismatch')
# Every recursive delete/move in the upstream recipe is restricted to this
# fresh, verified source tree. Refuse a reused or redirected output directory.
for name in ('dist', 'build'):
    path = root/name
    if path.exists() or not path.resolve().is_relative_to(root):
        raise SystemExit('P4 build expects a fresh output path: '+str(path))
sys.path.insert(0, str(root))
os.environ['PYTHONUTF8'] = '1'
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUNBUFFERED'] = '1'
original_popen = subprocess.Popen


def compiler_command(args, *positional, **kwargs):
    if isinstance(args, list) and args[1:3] == ['-m', 'nuitka']:
        if settings['engine'] != 'tesserocr':
            args = [arg for arg in args if arg not in ('--nofollow-import-to=cv2', '--nofollow-import-to=numpy')]
        extra = ['--zig', '--jobs=4',
                 '--include-data-file=p4_models.json=p4_models.json',
                 '--nofollow-import-to=torch', '--nofollow-import-to=paddle',
                 '--nofollow-import-to=openvino', '--nofollow-import-to=tensorrt',
                 '--nofollow-import-to=onnx', '--nofollow-import-to=bidi']
        if settings['engine'] == 'tesserocr':
            extra += ['--include-module=tesserocr', '--include-distribution-metadata=tesserocr',
                      '--nofollow-import-to=rapidocr', '--nofollow-import-to=onnxruntime',
                      '--nofollow-import-to=MNN']
        elif settings['engine'] == 'onnxruntime':
            extra += ['--nofollow-import-to=MNN', '--nofollow-import-to=rapidocr.inference_engine.mnn',
                      '--include-distribution-metadata=onnxruntime']
        else:
            extra += ['--nofollow-import-to=onnxruntime',
                      '--nofollow-import-to=rapidocr.inference_engine.onnxruntime',
                      '--include-module=_mnncengine', '--include-distribution-metadata=MNN']
        if settings['engine'] != 'tesserocr':
            extra += ['--include-module=rapidocr.main', '--include-package-data=rapidocr:*.yaml',
                      '--nofollow-import-to=tesserocr']
        for name in (('Pillow',) if settings['engine'] == 'tesserocr' else ('rapidocr', 'numpy', 'opencv-python', 'Pillow')):
            extra.append('--include-distribution-metadata='+name)
        for path in sorted((root/'ocr_models').iterdir()):
            extra.append('--include-data-file='+str(path)+'=ocr_models/'+path.name)
        args = args[:-1]+extra+args[-1:]
        print('P4 effective compiler command:', subprocess.list2cmdline(args), flush=True)
    return original_popen(args, *positional, **kwargs)


with patch.object(subprocess, 'Popen', compiler_command):
    runpy.run_path('build_nuitka.py', run_name='__main__')
