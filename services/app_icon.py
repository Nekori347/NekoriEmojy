"""User-selected application icon.

The program keeps its shipped default icon; a user choice is converted into a
multi-size Windows .ico inside the application data directory and applied to the
main window, taskbar and tray. Nothing in the program directory is overwritten.
"""
import ctypes
import os
from pathlib import Path

from PIL import Image

ICON_NAME = "app_icon.ico"
ICO_SIZES = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (24, 24), (16, 16)]
APP_USER_MODEL_ID = "Nekori.NekoriEmojy"


def program_icon_path():
    return str(Path(__file__).resolve().parent.parent / "ico.ico")


def set_app_user_model_id():
    """Give Windows a stable AppUserModelID so the taskbar button is ours alone."""
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except (AttributeError, OSError):
        pass


class ApplicationIconService:
    def __init__(self, config):
        self.config = config
        base = getattr(config, "base_dir", None)
        self.data_dir = Path(base) if isinstance(base, str) and base else Path(".")

    @property
    def custom_path(self):
        return self.data_dir / ICON_NAME

    def current_path(self):
        return str(self.custom_path) if self.custom_path.is_file() else program_icon_path()

    def is_custom(self):
        return self.custom_path.is_file()

    def set_from_image(self, image_path):
        source = Path(image_path)
        if not source.is_file():
            raise FileNotFoundError(str(source))
        with Image.open(source) as image:
            # Animated sources use their first frame as the static icon.
            if getattr(image, "is_animated", False):
                image.seek(0)
            canvas = self._square(image.convert("RGBA"))
        self.data_dir.mkdir(parents=True, exist_ok=True)
        canvas.save(self.custom_path, format="ICO", sizes=ICO_SIZES)
        return str(self.custom_path)

    @staticmethod
    def _square(image):
        side = max(image.size)
        canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        canvas.paste(image, ((side - image.width) // 2, (side - image.height) // 2))
        return canvas.resize((256, 256), Image.LANCZOS)

    def reset(self):
        if self.custom_path.is_file():
            os.remove(self.custom_path)
        return program_icon_path()
