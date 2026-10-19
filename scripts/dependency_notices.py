"""Preserve licenses from the distributions actually included by Nuitka."""
import importlib.metadata
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

def write_notices(destination,report,ffmpeg):
    names={n.attrib['name'] for n in ET.parse(report).iter('distribution-usage')}
    names.add('imageio-ffmpeg')  # Its FFmpeg executable is an explicit build input.
    sections=['NekoriEmojy standalone dependency notices\n\nApplication: GPL-3.0; see LICENSE and THIRD_PARTY_NOTICES.md.\nThe following are original installed-package notices, not new license grants.\nFor Qt/PySide the open-source license alternatives in the package metadata apply;\nno commercial Qt license or code-signing identity is asserted.\n']
    versions={}
    for name in sorted(names,key=str.casefold):
        dist=importlib.metadata.distribution(name);versions[name]=dist.version
        sections.append('\n=== '+name+' '+dist.version+' ===\n')
        sections.append('License metadata: '+str(dist.metadata.get('License-Expression') or dist.metadata.get('License') or 'See original notice')+'\n')
        sections.extend('Source/project: '+url+'\n' for url in dist.metadata.get_all('Project-URL',[]))
        for item in dist.files or []:
            path=Path(str(item));base=path.name.casefold()
            if '.dist-info' not in str(path):continue
            if not(base.startswith(('license','copying','notice')) and not base.endswith(('.py','.pyc'))):continue
            file=dist.locate_file(item)
            if file.is_file():sections.append('\n--- '+str(item)+' ---\n'+file.read_text('utf-8',errors='replace')+'\n')
    python_license=Path(sys.base_prefix)/'LICENSE.txt'
    if not python_license.is_file():raise FileNotFoundError(python_license)
    sections.append('\n=== Python '+sys.version+' ===\n'+python_license.read_text('utf-8'))
    for flag in ('-version','-L'):
        result=subprocess.run([str(ffmpeg),flag],capture_output=True,check=True)
        sections.append('\n=== Bundled FFmpeg '+flag+' ===\n'+(result.stdout+result.stderr).decode('utf-8',errors='replace'))
    Path(destination).write_text('\n'.join(sections),encoding='utf-8')
    return versions
