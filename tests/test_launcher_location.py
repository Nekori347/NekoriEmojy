"""Only runtime placement/reuse; no installer network or real Tk dialogs."""
import ast,os
from pathlib import Path
from unittest.mock import Mock
import pytest


@pytest.fixture
def launcher(tmp_path,monkeypatch):
    root=Path(__file__).resolve().parents[1]
    monkeypatch.setenv('NEKORI_APP_DATA',str(tmp_path/'user-app'))
    tree=ast.parse((root/'launcher.py').read_text('utf-8'))
    tree.body=[n for n in tree.body if not (isinstance(n,ast.If) and
        (isinstance(n.test,ast.Call) and isinstance(n.test.func,ast.Name) and n.test.func.id=='check_already_running'
         or isinstance(n.test,ast.Compare) and isinstance(n.test.left,ast.Name) and n.test.left.id=='__name__'))]
    program=tmp_path/'program';program.mkdir()
    ns={'__file__':str(program/'launcher.py'),'__name__':'isolated_launcher'}
    exec(compile(tree,'launcher.py','exec'),ns)
    return ns


def test_runtime_install_writes_user_cache_and_keeps_program_clean(launcher,monkeypatch):
    import zipfile
    ns=launcher;program=Path(ns['BASE_DIR']);requirements=Path(ns['REQUIREMENTS_FILE']);requirements.write_text('')
    before=set(program.iterdir());root=Path(ns['RUNTIME_DIR'])
    instance=ns['LauncherApp'].__new__(ns['LauncherApp'])
    instance.system_python=None;instance.root=Mock();instance.progress=Mock();instance.update_status=Mock()
    def download(url,destination,description):
        destination=Path(destination);assert destination.is_relative_to(root)
        if destination.suffix=='.zip':
            with zipfile.ZipFile(destination,'w') as archive:
                archive.writestr('python.exe',b'isolated fixture')
                archive.writestr('python311._pth','#import site\n')
        else:destination.write_text('# isolated installer boundary')
    instance.download_file=download
    def run(arguments,**kwargs):
        if str(arguments[1]).endswith('get-pip.py'):
            (root/'Scripts').mkdir();(root/'Scripts/pip.exe').touch()
        return Mock(returncode=0)
    monkeypatch.setattr(ns['subprocess'],'run',run)
    ns['check_dependencies']=lambda _:True;ns['launch_application']=Mock()
    instance.setup_environment()
    ns['launch_application'].assert_called_once_with(str(root/'python.exe'))
    assert root.is_relative_to(Path(ns['USER_DATA_DIR'])) and set(program.iterdir())==before


def test_existing_program_runtime_and_user_cache_are_reused(launcher):
    ns=launcher;legacy=Path(ns['LEGACY_RUNTIME_DIR']);cache=Path(ns['RUNTIME_DIR'])
    for path in (legacy,cache):path.mkdir(parents=True);(path/'python.exe').touch()
    ns['launch_application']=Mock();ns['check_dependencies']=lambda _:True
    ns['main']();ns['launch_application'].assert_called_once_with(str(legacy/'python.exe'))
    ns['launch_application'].reset_mock();ns['check_dependencies']=lambda path:Path(path).parent==cache
    ns['main']();ns['launch_application'].assert_called_once_with(str(cache/'python.exe'))
