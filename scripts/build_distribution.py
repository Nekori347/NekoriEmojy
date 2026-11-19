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

def installation_guards(names):
    binaries = {name for name in names if Path(name).suffix.lower() in {'.exe', '.dll', '.pyd'}}
    ordered = sorted(names, key=lambda name: (name != 'bin/NekoriEmojy.exe', name not in binaries, name))
    entries = []
    for name in ordered:
        path = name.replace('/', chr(92)).replace("'", "''")
        prefix = "" if name in binaries else "if Installing then "
        entries.append(f"    {prefix}Files.Add('{path}');")
    checks = '\n'.join(entries)
    return r'''
[CustomMessages]
english.UninstallFilesInUse=Close NekoriEmojy, including from the system tray, and wait for any update to finish before uninstalling. If the files remain inaccessible, check the uninstall log.
chinesesimp.UninstallFilesInUse=请从系统托盘完全退出 NekoriEmojy，并等待更新完成后再卸载。如果仍无法访问程序文件，请查看卸载日志。
chinesetrad.UninstallFilesInUse=請從系統匣完全關閉 NekoriEmojy，並等待更新完成後再解除安裝。如果仍無法存取程式檔案，請查看解除安裝記錄。
japanese.UninstallFilesInUse=システムトレイから NekoriEmojy を終了し、更新が終わってからアンインストールしてください。ファイルにアクセスできない場合は、アンインストールログを確認してください。

english.InstallFilesInUse=Exit NekoriEmojy from the system tray and wait for any update to finish. Then close this installer and run it again. If files remain inaccessible, check the setup log.
chinesesimp.InstallFilesInUse=请从系统托盘完全退出 NekoriEmojy，并等待更新完成，然后关闭并重新运行安装程序。如果仍无法访问文件，请查看安装日志。
chinesetrad.InstallFilesInUse=請從系統匣完全關閉 NekoriEmojy，並等待更新完成，再關閉並重新執行安裝程式。如果仍無法存取檔案，請查看安裝記錄。
japanese.InstallFilesInUse=システムトレイから NekoriEmojy を終了し、更新が終わるまでお待ちください。その後、セットアップを閉じて再実行してください。ファイルにアクセスできない場合は、セットアップログを確認してください。

[Code]
const
  WriteAndDelete = $40010000; { GENERIC_WRITE or DELETE }
  ShareReadWriteDelete = 7;
  OpenExisting = 3;

function OpenForReplacementCheck(const FileName: String; Access, ShareMode: Cardinal;
  Security: Cardinal; Disposition, Flags: Cardinal; Template: Cardinal): Cardinal;
  external 'CreateFileW@kernel32.dll stdcall';
function CloseReplacementCheckHandle(Handle: Cardinal): Boolean;
  external 'CloseHandle@kernel32.dll stdcall';

function ReplacementError(const FileName: String): Integer;
var
  Handle: Cardinal;
begin
  { Request access only. Never write, rename or delete a probed file. }
  Handle := OpenForReplacementCheck(FileName, WriteAndDelete,
    ShareReadWriteDelete, 0, OpenExisting, 0, 0);
  if Handle <> $FFFFFFFF then begin
    if CloseReplacementCheckHandle(Handle) then
      Result := 0
    else
      Result := DLLGetLastError;
    Exit;
  end;
  Result := DLLGetLastError;
  { Missing files and directories require no replacement. }
  if (Result = 2) or (Result = 3) then Result := 0;
end;

function BlockedReleaseFile(const Operation: String; Installing: Boolean): Boolean;
var
  AppDir: String;
  Files: TStringList;
  I, ErrorCode: Integer;
begin
  Result := False;
  AppDir := AddBackslash(ExpandConstant('{app}'));
  Files := TStringList.Create;
  try
''' + checks + r'''
    if not Installing then Files.Add('.update\NekoriEmojyUpdater.exe');
    for I := 0 to Files.Count - 1 do begin
      ErrorCode := ReplacementError(AppDir + Files[I]);
      if ErrorCode <> 0 then begin
        Log(Operation + ' blocked: ' + Files[I] + ' (Win32 ' + IntToStr(ErrorCode) + ').');
        Result := True;
        Exit;
      end;
    end;
  finally
    Files.Free;
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  if BlockedReleaseFile('Install', True) then
    Result := CustomMessage('InstallFilesInUse');
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep <> usUninstall then Exit;
  if not BlockedReleaseFile('Uninstall', False) then Exit;
  if not UninstallSilent then
    MsgBox(CustomMessage('UninstallFilesInUse'), mbError, MB_OK);
  Abort;
end;
'''


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
    snapshot=ROOT/'rc-source-manifest.json'
    if snapshot.is_file():
        records=json.loads(snapshot.read_text('utf-8'))['files']
        with zipfile.ZipFile(source,'x',zipfile.ZIP_DEFLATED) as package:
            for name,digest in sorted(records.items()):
                path=ROOT/name
                if not path.is_relative_to(ROOT) or sha256(path)!=digest:raise ValueError('RC source snapshot changed: '+name)
                package.write(path,name)
            package.write(snapshot,snapshot.name)
    else:
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
VersionInfoVersion={version}.0
VersionInfoProductVersion={version}
AppPublisher=Nekori_Net
DefaultDirName={{localappdata}}\\Programs\\NekoriEmojy
AppendDefaultDirName=no
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
CloseApplicationsFilter=*.exe,*.dll
RestartApplications=no
LanguageDetectionMethod=uilanguage
ShowLanguageDialog=auto
[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "chinesesimp"; MessagesFile: "{quoted(ROOT/'scripts/installer_languages/ChineseSimplified.isl')}"
Name: "chinesetrad"; MessagesFile: "{quoted(ROOT/'scripts/installer_languages/ChineseTraditional.isl')}"
Name: "japanese"; MessagesFile: "{quoted(ROOT/'scripts/installer_languages/Japanese.isl')}"
[Tasks]
Name: "desktopicon"; Description: "{{cm:CreateDesktopIcon}}"; GroupDescription: "{{cm:AdditionalIcons}}"; Flags: unchecked
[Files]
'''+ '\n'.join(files)+'''
[Icons]
Name: "{group}\\NekoriEmojy"; Filename: "{app}\\NekoriEmojy.exe"; WorkingDir: "{app}"; AppUserModelID: "Nekori.NekoriEmojy"
Name: "{autodesktop}\\NekoriEmojy"; Filename: "{app}\\NekoriEmojy.exe"; WorkingDir: "{app}"; Tasks: desktopicon; AppUserModelID: "Nekori.NekoriEmojy"
[Run]
Filename: "{app}\\NekoriEmojy.exe"; Description: "{cm:LaunchProgram,NekoriEmojy}"; Flags: nowait postinstall skipifsilent
'''+installation_guards(names),encoding='utf-8-sig')
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
