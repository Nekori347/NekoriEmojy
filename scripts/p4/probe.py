"""Isolated, offline OCR prototype and Windows measurement entry point.

This is an experiment, not a production OCR service or persistence layer.
"""
import argparse
from bisect import bisect_left
from contextlib import contextmanager
import ctypes
from ctypes import wintypes
import hashlib
import json
from itertools import accumulate
from pathlib import Path
import socket
import statistics
import sys
import threading
import time
import unicodedata


def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFKC', text).casefold()
                   if not c.isspace() and not unicodedata.category(c).startswith('P'))


def memory():
    class Counters(ctypes.Structure):
        _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)]+[
            (name, ctypes.c_size_t) for name in ('PeakWorkingSetSize', 'WorkingSetSize',
                'QuotaPeakPagedPoolUsage', 'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage',
                'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage', 'PrivateUsage')]
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    psapi = ctypes.WinDLL('psapi', use_last_error=True)
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    if not psapi.GetProcessMemoryInfo(wintypes.HANDLE(-1), ctypes.byref(counters), counters.cb):
        raise ctypes.WinError(ctypes.get_last_error())
    return {'working_set_bytes': counters.WorkingSetSize,
            'peak_working_set_bytes': counters.PeakWorkingSetSize,
            'private_bytes': counters.PrivateUsage}


def load_engine(candidate, model_root, manifest):
    config = manifest[candidate]
    for item in config['files'].values():
        path = model_root/item['file']
        if not path.is_file():
            raise FileNotFoundError('Bundled OCR component missing: '+item['file'])
        if hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
            raise ValueError('Bundled OCR component checksum mismatch: '+item['file'])
    if config['engine'] == 'tesserocr':
        from tesserocr import OEM, PSM, PyTessBaseAPI
        return PyTessBaseAPI(path=str(model_root), lang=config['languages'],
                             psm=PSM.SPARSE_TEXT, oem=OEM.LSTM_ONLY)
    from rapidocr import EngineType, ModelType, OCRVersion, RapidOCR
    params = {'Global.log_level': 'critical', 'Global.max_side_len': 1280,
              'EngineConfig.onnxruntime.intra_op_num_threads': 2,
              'EngineConfig.onnxruntime.inter_op_num_threads': 1}
    for role, item in config['files'].items():
        path = model_root/item['file']
        if role == 'dict':
            params['Rec.rec_keys_path'] = str(path)
        else:
            name = role.capitalize()
            params[name+'.model_path'] = str(path)
            params[name+'.engine_type'] = EngineType(config['engine'])
            if role != 'cls':
                params[name+'.ocr_version'] = OCRVersion(config['version'])
                params[name+'.model_type'] = ModelType(config['kind'])
    return RapidOCR(params=params)


def frames(path, strategy):
    """Bounded prototype: <=120 frames/96M source pixels scanned; <=6 OCR frames.

    At most two sequential decoder passes; <=16M pixels per source canvas.
    Selected RGB frames are scaled to <=1280 before inference. The time cap is
    checked between decoder operations, not a hard native-call timeout.
    """
    from PIL import Image, ImageChops, ImageOps, ImageStat
    started = time.perf_counter()
    thumbs, durations = [], []
    capped = False
    with Image.open(path) as image:
        pixels = image.width*image.height
        if pixels > 16_000_000:
            raise ValueError('Source canvas exceeds the prototype pixel limit')
        if not getattr(image, 'is_animated', False) or strategy == 'first':
            frame = ImageOps.exif_transpose(image).convert('RGB')
            frame.thumbnail((1280, 1280), Image.Resampling.LANCZOS)
            return [frame], {'scanned_frames': 1, 'selected_indices': [0], 'capped': False,
                             'decode_ms': (time.perf_counter()-started)*1000}
        limit = min(120, max(1, 96_000_000//pixels))
        for index in range(limit):
            try:
                image.seek(index)
            except EOFError:
                break
            durations.append(max(20, min(10_000, int(image.info.get('duration', 100)))))
            if strategy == 'changes':
                small = image.convert('RGB').resize((128, 72)).convert('L')
                thumbs.append(small)
            if time.perf_counter()-started > 3:
                capped = True
                break
        else:
            capped = True  # A boundary hit is disclosed, even if exactly EOF.
    if strategy == 'uniform':
        cumulative = list(accumulate(durations))
        total = cumulative[-1]
        selected = sorted({min(len(durations)-1, bisect_left(cumulative, total*f))
                           for f in (0, .2, .4, .6, .8, .999)})
    elif strategy == 'changes':
        selected = [0]
        while len(selected) < min(6, len(thumbs)):
            distances = [min(ImageStat.Stat(ImageChops.difference(t, thumbs[s])).mean[0]
                             for s in selected) for t in thumbs]
            index = max(range(len(distances)), key=distances.__getitem__)
            if distances[index] < .7:
                break
            selected.append(index)
        selected.sort()
    else:
        raise ValueError(strategy)
    result = []
    with Image.open(path) as image:
        for index in selected:
            image.seek(index)
            frame = image.convert('RGB')
            frame.thumbnail((1280, 1280), Image.Resampling.LANCZOS)
            result.append(frame)
    return result, {'scanned_frames': len(durations), 'selected_indices': selected, 'capped': capped,
                    'decode_ms': (time.perf_counter()-started)*1000}


def recognize(engine, path, strategy='changes'):
    started, cpu = time.perf_counter(), time.process_time()
    images, detail = frames(path, strategy)
    texts, seen = [], set()
    for image in images:
        if hasattr(engine, 'SetImage'):
            engine.SetImage(image)
            lines = engine.GetUTF8Text().splitlines()
        else:
            import numpy as np
            # ndarray inputs use BGR in RapidOCR; PIL fixtures are RGB.
            result = engine(np.ascontiguousarray(np.asarray(image)[:, :, ::-1]))
            lines = result.txts or []
        for text in lines:
            key = normalized(text)
            if key and key not in seen:
                seen.add(key)
                texts.append(text)
    return {'text': '\n'.join(texts), 'elapsed_ms': (time.perf_counter()-started)*1000,
            'cpu_ms': (time.process_time()-cpu)*1000, 'frames': detail}


def evaluate(args):
    import requests
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    sample_manifest = json.loads((args.samples/'manifest.json').read_text(encoding='utf-8'))
    report = {'candidate': args.candidate, 'versions': {}, 'network_attempts': 0,
              'cold_definition': 'Fresh process, existing local models; OS disk cache is not flushed.',
              'before': memory()}

    def forbidden(*a, **kw):
        report['network_attempts'] += 1
        raise RuntimeError('Network is disabled in this evaluation')

    @contextmanager
    def offline():
        original_connect, original_request = socket.socket.connect, requests.Session.request
        socket.socket.connect, requests.Session.request = forbidden, forbidden
        try:
            yield
        finally:
            socket.socket.connect, requests.Session.request = original_connect, original_request

    with offline():
        import importlib.metadata
        runtime = manifest[args.candidate]['engine']
        packages = (('tesserocr', 'Pillow') if runtime == 'tesserocr' else
                    ('rapidocr', 'MNN' if runtime == 'mnn' else 'onnxruntime', 'numpy', 'opencv-python', 'Pillow'))
        for name in packages:
            try:
                report['versions'][name] = importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                pass
        started, cpu = time.perf_counter(), time.process_time()
        engine = load_engine(args.candidate, args.models, manifest)
        report.update(load_ms=(time.perf_counter()-started)*1000,
                      load_cpu_ms=(time.process_time()-cpu)*1000, after_load=memory())
        warm_path = args.samples/sample_manifest['records'][0]['file']
        report['warm_sample'] = warm_path.name
        report['first_inference'] = recognize(engine, warm_path)
        report['warm_inferences'] = [recognize(engine, warm_path) for _ in range(3)]
        report['samples'] = []
        for record in sample_manifest['records']:
            output = {key: record[key] for key in ('id', 'language', 'strata', 'queries', 'expected')}
            try:
                output.update(recognize(engine, args.samples/record['file']))
                prediction = normalized(output['text'])
                output['hits'] = [query for query in record['queries'] if normalized(query) in prediction]
                output['exact_after_search_normalization'] = prediction == normalized(record['expected'])
            except Exception as exc:
                output.update(error=type(exc).__name__, error_message=str(exc),
                              expected_error=record.get('expected_error', False), hits=[])
            report['samples'].append(output)
        report['gif_comparison'] = []
        for record in sample_manifest['records']:
            if 'gif' not in record['strata']:
                continue
            for strategy in ('first', 'uniform', 'changes'):
                output = recognize(engine, args.samples/record['file'], strategy)
                output.update(id=record['id'], strategy=strategy, queries=record['queries'],
                              hits=[q for q in record['queries'] if normalized(q) in normalized(output['text'])])
                report['gif_comparison'].append(output)
        report['after_batch'] = memory()
        if hasattr(engine, 'End'):
            engine.End()
    return report


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--candidate', required=True)
    parser.add_argument('--models', type=Path, required=True)
    parser.add_argument('--samples', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, default=Path(__file__).with_name('models.json'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    from PySide6.QtCore import QCoreApplication, QTimer
    app = QCoreApplication.instance() or QCoreApplication([])
    done = threading.Event()
    result = {}
    ticks = []
    last = time.perf_counter()

    def worker():
        try:
            result.update(evaluate(args))
        except Exception:
            import traceback
            result['fatal_error'] = traceback.format_exc()
        finally:
            done.set()

    def tick():
        nonlocal last
        now = time.perf_counter()
        ticks.append((now-last)*1000)
        last = now
        if done.is_set():
            app.quit()

    timer = QTimer()
    timer.timeout.connect(tick)
    timer.start(10)
    started = time.perf_counter()
    thread = threading.Thread(target=worker)
    thread.start()
    app.exec()
    thread.join()
    result['total_wall_ms'] = (time.perf_counter()-started)*1000
    result['qt_heartbeat_10ms'] = {'count': len(ticks), 'max_ms': max(ticks),
                                   'p99_ms': sorted(ticks)[int((len(ticks)-1)*.99)],
                                   'median_ms': statistics.median(ticks)}
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k: result[k] for k in ('candidate', 'load_ms', 'after_batch', 'qt_heartbeat_10ms', 'fatal_error') if k in result}))
    return 1 if 'fatal_error' in result else 0


if __name__ == '__main__':
    raise SystemExit(main())
