from pathlib import Path
import threading
import zipfile
from PIL import Image
import pytest
from services.image_frames import sampled_frames
from services.ocr_component import OcrComponent
from services.library_index import LibraryIndex


@pytest.mark.parametrize('suffix,format',[('.gif','GIF'),('.webp','WEBP'),('.png','PNG')])
def test_duration_sampling_is_distinct_and_thumbnail_first(tmp_path,suffix,format):
    colors=['red','green','blue','yellow','magenta','cyan','orange']
    frames=[Image.new('RGBA',(32,24),color) for color in colors]
    path=tmp_path/('animation'+suffix)
    frames[0].save(path,format=format,save_all=True,append_images=frames[1:],
        duration=[40,40,100,700,80,80,60],loop=0)
    samples=sampled_frames(path,3)
    indices=[i for i,_ in samples]
    assert len(indices)==len(set(indices))==5
    assert indices[0]==3 and 0 in indices and 6 in indices
    assert all(image.size==(32,24) for _,image in samples)
    assert samples[0][1].getpixel((0,0))[0]>180 # selected frame is yellow
    still=tmp_path/'still.png';frames[0].save(still)
    assert [i for i,_ in sampled_frames(still,99)]==[0]


def test_failed_local_install_and_no_release_keep_library_data(tmp_path,monkeypatch):
    index=LibraryIndex(tmp_path/'library')
    path=index.root/'image.png';Image.new('RGB',(8,8),'red').save(path)
    rid=index.register(path);index.edit_ocr_text(rid,'人工文字')
    component=OcrComponent(tmp_path/'app')
    package=tmp_path/'bad.zip'
    with zipfile.ZipFile(package,'w') as z:z.writestr('../escaped.txt','invalid')
    with pytest.raises(ValueError):component.install(package)
    assert not component.installed
    assert not (component.base/'escaped.txt').exists()
    monkeypatch.setattr(component,'release',lambda:dict(url='',sha256=''))
    with pytest.raises(ValueError,match='尚未发布'):component.install()
    component.uninstall()
    assert index.ocr_info(rid)['text']=='人工文字'
