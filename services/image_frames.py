"""Frame access for animated images, behind one interface.

Qt's QImageReader reports an imageCount for GIF, but in this build its handler
cannot actually step to a frame: `jumpToImage()` returns False and
`jumpToNextImage()` does not advance, so every "frame" decoded through it was
really frame 0. That is why the thumbnail frame picker showed no change and
saving a frame had no visible effect.

Pillow is already a project dependency and reads the frames correctly, so it is
the decoder for animated formats. Everything that needs a specific frame goes
through `frame_count()` / `frame_at()` so the picker, the thumbnail cache and
any future caller cannot drift apart.
"""
from pathlib import Path

ANIMATED_SUFFIXES = ('.gif', '.webp', '.png', '.apng', '.tiff')


def _pillow():
    from PIL import Image, ImageSequence
    return Image, ImageSequence


def is_animated(path):
    if Path(path).suffix.lower() not in ANIMATED_SUFFIXES:
        return False
    return frame_count(path) > 1


def frame_count(path):
    """Number of frames, 1 for a still image or an unreadable file."""
    try:
        Image, _ = _pillow()
        with Image.open(path) as image:
            return max(1, int(getattr(image, 'n_frames', 1) or 1))
    except Exception:
        return 1


def frame_at(path, index):
    """One frame as a detached QImage, or None when it cannot be decoded."""
    from PySide6.QtGui import QImage
    try:
        Image, ImageSequence = _pillow()
        with Image.open(path) as image:
            total = max(1, int(getattr(image, 'n_frames', 1) or 1))
            wanted = max(0, min(int(index or 0), total - 1))
            if wanted == 0:
                frame = image.convert('RGBA')
            else:
                frame = None
                for position, candidate in enumerate(ImageSequence.Iterator(image)):
                    if position == wanted:
                        frame = candidate.convert('RGBA')
                        break
                if frame is None:
                    frame = image.convert('RGBA')
            buffer = frame.tobytes('raw', 'RGBA')
            qt_image = QImage(buffer, frame.width, frame.height, QImage.Format_RGBA8888)
            # copy() detaches the QImage from the Python buffer.
            return qt_image.copy()
    except Exception as exc:
        print(f'[WARNING] 无法解码第 {index} 帧 {path}: {exc}')
        return None
