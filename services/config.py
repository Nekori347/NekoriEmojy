"""Library-owned preferences; JSON compatibility belongs to migration."""
from contextlib import nullcontext
import json
from services.library import LibraryContext, LibrarySession, read_db


class ConfigService:
    DEFAULTS = {"always_on_top": True, "preview_delay": 500, "preview_size": 320,
                "use_system_font": False, "convert_static_to_gif": True}

    def __init__(self, library):
        self.session = library if isinstance(library, LibrarySession) else None
        self.context = library.context if self.session else library
        if not isinstance(self.context, LibraryContext):
            raise TypeError("ConfigService requires an explicit library context")
        self.base_dir = str(self.context.root)
        self.default_config = self.DEFAULTS.copy()
        self.config = self._load_config()

    def _load_config(self):
        config = self.default_config.copy()
        with read_db(self.context.db("library")) as conn:
            config.update({key: json.loads(value) for key, value in conn.execute("SELECT key, value FROM preferences")})
        return config

    def _save_config(self, config_data):
        values = [(key, json.dumps(value, ensure_ascii=False)) for key, value in config_data.items()]
        with (self.session.task() if self.session else nullcontext()), self.context.transaction() as conn:
            conn.execute("DELETE FROM preferences")
            conn.executemany("INSERT INTO preferences VALUES (?, ?)", values)
        self.config = dict(config_data)

    def get_actual_theme_is_dark(self):
        import darkdetect
        mode = self.get("appearance_mode", self.get("theme_mode", "system"))
        return mode == "dark" if mode != "system" else darkdetect.isDark()

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        if self.config.get(key) != value:
            self._save_config({**self.config, key: value})
