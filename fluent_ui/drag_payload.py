"""Internal drag payload bound to the originating library session."""
import json
from PySide6.QtCore import QMimeData
from services.library import LibraryError

SELECTION_MIME='application/x-nekori-selection'
REORDER_MIME='application/x-emojy-reorder'


def make_payload(context, paths, anchor):
    mime=QMimeData()
    names=list(dict.fromkeys(context.resource(path).name for path in paths))
    mime.setData(SELECTION_MIME,json.dumps({'library_id':context.library_id,'session_id':context.session_id,'paths':names}).encode())
    mime.setData(REORDER_MIME,str(context.resource(anchor)).encode('utf-8'))
    return mime


def paths_from_mime(mime, context):
    if mime.hasFormat(SELECTION_MIME):
        raw=bytes(mime.data(SELECTION_MIME))
        if len(raw)>2*1024*1024:raise LibraryError('拖放内容过大。')
        value=json.loads(raw)
        if value.get('library_id')!=context.library_id or value.get('session_id')!=context.session_id:
            raise LibraryError('拖放来源资源库已改变，请重新选择图片。')
        paths=value.get('paths')
        if not isinstance(paths,list) or any(not isinstance(p,str) for p in paths):
            raise LibraryError('拖放内容无效。')
        return list(dict.fromkeys(str(context.resource(p)) for p in paths))
    if mime.hasFormat(REORDER_MIME):
        return [str(context.resource(bytes(mime.data(REORDER_MIME)).decode('utf-8')))]
    return []
