"""Build the ONE verified OCR payload; no downloads or modifications to app deps.

Input is an isolated Windows embeddable runtime with pinned phase-one wheels.
Output is a local/releasable zip plus its SHA256. No publishing is performed.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from services.ocr_data import OCR_VERSION
from services.update_protocol import sha256,atomic_json


def build(runtime,output):
    runtime=Path(runtime).resolve();output=Path(output).resolve()
    output.parent.mkdir(parents=True,exist_ok=True)
    if not (runtime/'python.exe').is_file():raise ValueError('Windows embeddable Python is required')
    stage=output.parent/'ocr-package-stage'
    if stage.exists():raise FileExistsError('Choose an empty output directory: '+str(stage))
    shutil.copytree(runtime,stage,ignore=shutil.ignore_patterns('__pycache__','*.pyc','standalone_smoke.py'))
    (stage/'python312._pth').write_text('python312.zip\n.\nsite-packages\n',encoding='ascii')
    for src,dest in [('ocr_worker.py','worker.py'),('ocr_layout.py','ocr_layout.py'),('image_frames.py','image_frames.py')]:
        shutil.copyfile(ROOT/'services'/src,stage/dest)
    notices=[]
    for meta in sorted((stage/'site-packages').glob('*.dist-info/METADATA')):
        text=meta.read_text(encoding='utf-8')
        fields={k:v.strip() for k,v in (line.split(':',1) for line in text.splitlines() if line.startswith(('Name:','Version:','License:','License-Expression:')))}
        notices.append(f"- {fields.get('Name')} {fields.get('Version')}: {fields.get('License-Expression',fields.get('License','see bundled notices'))}")
    (stage/'THIRD_PARTY_NOTICES.md').write_text('# Nekori optional OCR component\n\nPrivate Python: LICENSE.txt. All wheel notices are retained in site-packages.\n'
        'RapidOCR model provenance: rapidocr-3.10.0.dist-info/licenses/MODEL_LICENSES.md.\n\n'+'\n'.join(notices)+'\n',encoding='utf-8')
    files={p.relative_to(stage).as_posix():sha256(p) for p in sorted(stage.rglob('*')) if p.is_file()}
    atomic_json(stage/'nekori-ocr.json',dict(protocol=1,version=OCR_VERSION,files=files))
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for p in sorted(stage.rglob('*')):
            if p.is_file():archive.write(p,p.relative_to(stage).as_posix())
    output.with_suffix('.zip.sha256').write_text(sha256(output)+'  '+output.name+'\n',encoding='ascii')
    atomic_json(output.with_suffix('.metadata.json'),dict(version=OCR_VERSION,filename=output.name,
        size=output.stat().st_size,installed_size=sum(p.stat().st_size for p in stage.rglob('*') if p.is_file()),sha256=sha256(output)))
    print(json.dumps(dict(archive=str(output),sha256=sha256(output),compressed_bytes=output.stat().st_size,
        deployed_bytes=sum(p.stat().st_size for p in stage.rglob('*') if p.is_file())),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('runtime');p.add_argument('output');args=p.parse_args()
    build(args.runtime,args.output)
