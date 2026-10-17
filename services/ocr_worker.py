"""Entry shipped INSIDE the optional component; never imported by the GUI."""
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
sys.path.insert(0,str(Path(__file__).resolve().parent))
import contextlib
import json


def offline(event,args):
    if event in {'socket.connect','socket.getaddrinfo','socket.sendto','socket.sendmsg'}:
        raise RuntimeError('OCR inference is offline')


sys.addaudithook(offline)


def main():
    import ctypes
    if sys.platform=='win32':
        from ctypes import wintypes
        kernel=ctypes.WinDLL('kernel32')
        kernel.GetCurrentProcess.restype=wintypes.HANDLE
        kernel.SetPriorityClass.argtypes=[wintypes.HANDLE,wintypes.DWORD]
        kernel.SetPriorityClass(kernel.GetCurrentProcess(),0x4000)
    with contextlib.redirect_stdout(sys.stderr):
        import cv2
        cv2.setNumThreads(1)
        from rapidocr import RapidOCR
        from ocr_layout import normalize_blocks,merge_frames
        from image_frames import sampled_frames
        engine=RapidOCR(params={'EngineConfig.onnxruntime.intra_op_num_threads':2,
            'EngineConfig.onnxruntime.inter_op_num_threads':1,'Global.log_level':'error'})
        engine._load_det_model();engine._load_cls_model();engine._load_rec_model()
    print(json.dumps({'ready':True,'protocol':1}),flush=True)
    if '--check' in sys.argv:return
    for line in sys.stdin:
        try:
            request=json.loads(line)
            normalized=[];raw=[];indices=[]
            with contextlib.redirect_stdout(sys.stderr):
                for index,image in sampled_frames(request['path'],request.get('thumbnail',0)):
                    result=engine(image)
                    texts=list(result.txts) if result.txts is not None else []
                    boxes=result.boxes.tolist() if result.boxes is not None else []
                    normalized.append(normalize_blocks(texts,boxes))
                    raw.append('\n'.join(texts));indices.append(index)
            response=dict(text=merge_frames(normalized),raw_text=merge_frames(raw),frames=indices)
        except Exception as exc:
            response={'error':str(exc)}
        print(json.dumps(response,ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
