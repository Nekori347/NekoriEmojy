"""Actual exchange ZIP scope, shared relations and stage counts on isolated storage."""
import json,zipfile
from pathlib import Path
import pytest
from PIL import Image
from services.config import ConfigService
from services.storage import StorageService
from services.resource_import import ImportTarget
from services.exchange_export import ExchangeExportService


@pytest.fixture
def export_library(tmp_path,monkeypatch):
    monkeypatch.setenv('NEKORI_APP_DATA',str(tmp_path/'app'))
    monkeypatch.setenv('NEKORI_LIBRARY',str(tmp_path/'library'))
    storage=StorageService(config=ConfigService())
    parent=storage.create_node('Parent');child=storage.create_node('Child',parent);other=storage.create_node('Other')
    paths=[]
    for i,target in enumerate((parent,parent,child,other)):
        p=tmp_path/f'{i}.png';Image.new('RGBA',(24+i,30),(20+i*40,90,180,255)).save(p)
        paths.append(storage.save_file(str(p),target=ImportTarget(target))[0])
    storage.move_resources_to(paths[:1],child,copy=True)
    storage.apply_tags(paths,['tag'],'add')
    return storage,parent,child,other,paths


@pytest.mark.parametrize('selection,expected_names,expected_resources,relations',[
    (['Parent'],['Parent'],2,2),
    (['Parent','Parent / Child'],['Parent','Parent / Child'],3,4),
    (None,['Parent','Parent / Child','Other'],4,5),
])
def test_exchange_zip_exact_scope_and_relations(export_library,tmp_path,selection,expected_names,expected_resources,relations,monkeypatch):
    storage,parent,child,other,paths=export_library
    service=ExchangeExportService(storage=storage);inspected=[];inspect=service._inspect_and_pack_asset
    def observed(path):inspected.append(path);return inspect(path)
    monkeypatch.setattr(service,'_inspect_and_pack_asset',observed)
    target=tmp_path/'result.zip';progress=[]
    before={p:Path(p).read_bytes() for p in paths}
    manifest=service.export_zip(str(target),selection,lambda *args:progress.append(args))
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        catalog=json.loads(archive.read('catalog.json'))
        assets=[n for n in archive.namelist() if n.startswith('assets/')]
    assert [c['name'] for c in catalog['categories']]==expected_names
    assert len(catalog['resources'])==len(assets)==len(inspected)==expected_resources
    assert manifest['counts']['relations']==relations
    assert all(('keywords' in resource)==(selection is None) for resource in catalog['resources'])
    assert all(total<=expected_resources for current,total,message in progress)
    assert progress[-1]==(expected_resources,expected_resources,'导出完成')
    assert all(Path(p).read_bytes()==data for p,data in before.items())
    if len(expected_names)>1 and 'Parent / Child' in expected_names:
        shared=next(r for r in catalog['resources'] if r['display_name']=='0.png')
        assert len(shared['category_refs'])==2
