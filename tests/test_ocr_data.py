"""Search and persistence contracts, without an optional OCR installation."""
import json
from pathlib import Path
import pytest
from services.library_index import LibraryIndex
from services.ocr_data import source_stamp, OCR_VERSION
from services.ocr_layout import normalize_blocks
from services.search_text import normalize_search, search_projection


@pytest.fixture
def resource(tmp_path):
    index=LibraryIndex(tmp_path/'library')
    path=index.root/'a.png'
    path.write_bytes(b'image')
    rid=index.register(path)
    return index,rid


def test_search_equivalence_preserves_original_and_short_words(resource):
    index,rid=resource
    index.edit_ocr_text(rid,'不要輕易放棄你的夢\n一')
    assert index.ocr_info(rid)['text']=='不要輕易放棄你的夢\n一'
    assert normalize_search('放弃') in index.search_texts()[rid]
    assert normalize_search('放棄') in index.search_texts()[rid]
    assert '一' in index.search_texts()[rid]
    assert 'Foo.GIF'.casefold() in search_projection('Foo.GIF')


def test_columns_and_separate_horizontal_characters():
    box=lambda x,y:[[x,y],[x+20,y],[x+20,y+20],[x,y+20]]
    # OCR's original row-first ordering interleaves three columns.
    text=normalize_blocks(['画','需','睡','师','要','觉'],
        [box(0,0),box(70,0),box(140,0),box(0,23),box(70,23),box(140,23)])
    assert text=='画师需要睡觉'
    assert normalize_blocks(['再','见'],[box(0,0),box(40,-2)])=='再见'
    assert normalize_blocks(['1'],[box(0,0)])=='1'


def test_late_result_never_overwrites_edit_or_rebind(resource):
    index,rid=resource
    stamp=source_stamp(index,index.resource_by_id(rid))
    index.edit_ocr_text(rid,'楽しい')
    assert not index.commit_ocr(rid,{'text':'wrong'},revision=0,source=stamp,version=OCR_VERSION,overwrite=True)
    revision=index.ocr_info(rid)['revision']
    other=index.root/'b.png';other.write_bytes(b'other')
    index.rebind(rid,other)
    assert index.ocr_info(rid)['text']=='楽しい'
    assert not index.commit_ocr(rid,{'text':'wrong'},revision=revision,source=stamp,version=OCR_VERSION,overwrite=True)


def test_empty_failed_and_manual_are_distinct_and_persist(resource):
    index,rid=resource
    stamp=source_stamp(index,index.resource_by_id(rid))
    assert index.ocr_info(rid)['status']=='unrecognized'
    assert index.commit_ocr(rid,{'text':''},revision=0,source=stamp,version=OCR_VERSION)
    assert index.ocr_info(rid)['status']=='empty'
    assert index.commit_ocr(rid,{},revision=1,source=stamp,version=OCR_VERSION,error='cannot decode')
    assert index.ocr_info(rid)['status']=='failed'
    index.edit_ocr_text(rid,'')
    restored=LibraryIndex(index.root)
    assert restored.ocr_info(rid)['manual'] and restored.ocr_info(rid)['text']==''
    assert not restored.commit_ocr(rid,{'text':'noise'},revision=3,source=stamp,version=OCR_VERSION)
    restored.forget_resource(rid)
    assert not restored.commit_ocr(rid,{},revision=3,source=stamp,version=OCR_VERSION)
