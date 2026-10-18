"""Build a fresh allowlisted validation stage; ZIP requires explicit --archive."""
import argparse,json,shutil,subprocess,sys
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.release_layout import source_files,SOURCE_OVERRIDES
from scripts.package_release import package_release

def build(output=None,archive=False):
    out=Path(output).resolve() if output else ROOT.parent/'Build'/('lightweight-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
    if out.exists():raise FileExistsError('Build output must be new: '+str(out))
    release=out/'application';release.mkdir(parents=True)
    for name in source_files():
        target=release/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/SOURCE_OVERRIDES.get(name,name),target)
    subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onefile','--noconsole',
        '--name','SuzuEmojy','--icon',str(ROOT/'ico.ico'),'--add-data',str(ROOT/'ico.ico')+';.',
        '--distpath',str(release),'--workpath',str(out/'compiler'),'--specpath',str(out),str(ROOT/'launcher.py')],cwd=ROOT,check=True)
    commit=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()
    (release/'BUILD_INFO.json').write_text(json.dumps({'version':json.loads((ROOT/'version.json').read_text('utf-8'))['version'],
        'source_commit':commit,'flavor':'lightweight','ocr_included':False},indent=2),encoding='utf-8')
    package_release(release,'lightweight',archive=archive)
    subprocess.run(['git','-C',str(ROOT),'archive','--format=zip','--output='+str(out/'corresponding-source.zip'),'HEAD'],check=True)
    print('VALIDATION_STAGE='+str(release),flush=True)
    return release

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output');p.add_argument('--archive',action='store_true')
    a=p.parse_args();build(a.output,a.archive)
