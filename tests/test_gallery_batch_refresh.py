"""An import-end delta preserves resource records without re-querying new IDs."""
from PIL import Image
from test_management_mode import management
from services.resource_import import ImportTarget


def test_changed_batch_refresh_preserves_metadata_and_memberships(management,tmp_path,monkeypatch):
    view,storage,parent,dest,paths,sent=management
    before=storage.index.content(parent)
    new=[]
    for i in range(5):
        p=tmp_path/f'new-{i}.png';Image.new('RGB',(80+i,50),(200,20+i,90)).save(p)
        new.append(storage.save_file(str(p),target=ImportTarget(parent))[0])
    storage.apply_tags(new,['imported'],'add')
    storage.move_resources_to(new,dest,copy=True)
    view.entry_model.entries_of(dest)
    def redundant(*args):raise AssertionError('changed import record queried a second time by ID')
    monkeypatch.setattr(storage.index,'resource_by_id',redundant)
    view.refresh_content_incremental(reason='queued_import',paths=new,parents={parent,dest})
    shown={e['path']:e for e in view._entries if e['kind']=='resource'}
    assert all(p in shown and 'imported' in shown[p]['tags'] for p in new)
    assert all(p in shown for p in paths)
    assert storage.index.content(parent)[:len(before)]==before
    assert {e['path'] for e in view.entry_model.entries_of(dest) if e['kind']=='resource'}==set(new)
