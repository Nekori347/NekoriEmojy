"""Windows PE identity shared by the PyInstaller build entry points."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
def version_resource(destination, executable, description):
    version = json.loads((ROOT / "version.json").read_text("utf-8"))["version"]
    numbers = tuple(map(int, version.split("."))) + (0,)
    strings = {"ProductName": "NekoriEmojy", "FileDescription": description,
               "OriginalFilename": executable, "InternalName": executable[:-4],
               "FileVersion": version + ".0", "ProductVersion": version}
    entries = ",".join("StringStruct(%r, %r)" % pair for pair in strings.items())
    text = "VSVersionInfo(ffi=FixedFileInfo(filevers=%r,prodvers=%r,mask=0x3f,flags=0,OS=0x40004,fileType=1,subtype=0,date=(0,0)),kids=[StringFileInfo([StringTable('040904B0',[%s])]),VarFileInfo([VarStruct('Translation',[1033,1200])])])" % (numbers,numbers,entries)
    destination = Path(destination)
    destination.write_text(text,encoding="utf-8")
    return destination
