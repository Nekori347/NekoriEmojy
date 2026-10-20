from pathlib import Path
import pytest
from scripts.release_layout import source_files,validate_layout,allowed_files

def test_runtime_allowlist_keeps_sources_and_assets_but_no_user_or_dev_data(tmp_path):
    names=source_files()
    assert {'main.py','LICENSE','THIRD_PARTY_NOTICES.md','translations/ja.json'}<=names
    assert any(n.startswith('services/') for n in names)
    assert any(n.startswith('fluent_ui/assets/fonts/') for n in names)
    assert not any(n.startswith(('tests/','assets/','config/','.git/','DevData/')) for n in names)
    (tmp_path/'main.py').write_text('pass')
    assert validate_layout(tmp_path,'lightweight')==['main.py']
    (tmp_path/'personal.sqlite3').write_bytes(b'private')
    with pytest.raises(ValueError,match='outside release allowlist'):validate_layout(tmp_path,'lightweight')

def test_standalone_requires_fresh_dependency_inventory(tmp_path):
    with pytest.raises(ValueError,match='compiler dependency inventory'):allowed_files('standalone')
    with pytest.raises(ValueError,match='dependency path'):allowed_files('standalone',['../Archive/old.exe'])
    (tmp_path/'bin').mkdir();(tmp_path/'bin/Qt6Core.dll').write_bytes(b'test')
    assert validate_layout(tmp_path,'standalone',['bin/Qt6Core.dll'])==['bin/Qt6Core.dll']
    (tmp_path/'bin/old.zip').write_bytes(b'test')
    with pytest.raises(ValueError,match='outside release allowlist'):validate_layout(tmp_path,'standalone',['bin/Qt6Core.dll'])
