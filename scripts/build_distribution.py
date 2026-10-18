"""Create ZIP and per-user Inno installer from one verified standalone inventory."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from services.update_protocol import MANIFEST,read_manifest,sha256
from scripts.release_layout import validate_layout

def build(stage,compiler,iscc,output):
    stage=Path(stage).resolve();output=Path(output).resolve()
    manifest=read_manifest(stage,verify=True)
    if manifest['flavor']!='standalone':raise ValueError('Distribution requires standalone output')
    inventory=json.loads(Path(compiler).read_text('utf-8'))
    actual=set(validate_layout(stage,'standalone',inventory))
    if actual!=set(manifest['files']):raise ValueError('Manifest and positive inventory differ')
    output.mkdir(parents=True,exist_ok=False)
    version=manifest['version'];names=sorted(actual|{MANIFEST})
    archive=output/f'NekoriEmojy-{version}-Windows-Portable.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as package:
        for name in names:package.write(stage/name,name)
    source=output/f'NekoriEmojy-{version}-Source.zip'
    subprocess.run(['git','-C',str(ROOT),'archive','--format=zip','--output='+str(source),'HEAD'],check=True)
    def quoted(path):return str(path).replace('"','""')
    files=[]
    for name in names:
        target=Path(name)
        directory='{app}' if str(target.parent)=='.' else '{app}'+chr(92)+str(target.parent)
        files.append(f'Source: "{quoted(stage/target)}"; DestDir: "{directory}"; Flags: ignoreversion')
    script=stage.parent/'NekoriEmojy.iss'
    script.write_text(f'''[Setup]
AppId={{{{CF92A7A8-2028-40BD-9EAA-8DD896C73407}}
AppName=NekoriEmojy
AppVersion={version}
AppPublisher=Nekori_Net
DefaultDirName={{localappdata}}\\Programs\\NekoriEmojy
DefaultGroupName=NekoriEmojy
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableDirPage=no
DisableProgramGroupPage=yes
DisableWelcomePage=no
SetupIconFile={quoted(stage/'ico.ico')}
UninstallDisplayIcon={{app}}\\NekoriEmojy.exe
LicenseFile={quoted(stage/'LICENSE')}
OutputDir={quoted(output)}
OutputBaseFilename=NekoriEmojy-Setup-{version}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
[Tasks]
Name: "desktopicon"; Description: "{{cm:CreateDesktopIcon}}"; GroupDescription: "{{cm:AdditionalIcons}}"; Flags: unchecked
[Files]
'''+ '\n'.join(files)+'''
[Icons]
Name: "{group}\\NekoriEmojy"; Filename: "{app}\\NekoriEmojy.exe"; WorkingDir: "{app}"; AppUserModelID: "Nekori.NekoriEmojy"
Name: "{autodesktop}\\NekoriEmojy"; Filename: "{app}\\NekoriEmojy.exe"; WorkingDir: "{app}"; Tasks: desktopicon; AppUserModelID: "Nekori.NekoriEmojy"
[Run]
Filename: "{app}\\NekoriEmojy.exe"; Description: "{cm:LaunchProgram,NekoriEmojy}"; Flags: nowait postinstall skipifsilent
''',encoding='utf-8-sig')
    subprocess.run([str(Path(iscc).resolve()),str(script)],check=True)
    # Verify both packaging operations left the source application set unchanged.
    read_manifest(stage,verify=True)
    checks={p.name:{'bytes':p.stat().st_size,'sha256':sha256(p)} for p in output.iterdir() if p.is_file()}
    (output/'SHA256SUMS.txt').write_text(''.join(v['sha256']+'  '+n+'\n' for n,v in checks.items()),encoding='ascii')
    (output/'artifacts.json').write_text(json.dumps({'stage':str(stage),'source_commit':subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip(),'files':checks},indent=2),encoding='utf-8')
    print(json.dumps(checks,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage');p.add_argument('--compiler-files',required=True);p.add_argument('--iscc',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();build(a.stage,a.compiler_files,a.iscc,a.output)
