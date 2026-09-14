"""Validated library-owned preferences and a reversible settings preview."""
from contextlib import nullcontext
import json
from pathlib import Path
from services.library import LibraryContext, LibrarySession, LibraryError, read_db, atomic_json


class ConfigService:
    DEFAULTS = {
        'always_on_top': True, 'preview_delay': 500, 'preview_size': 320,
        'use_system_font': False, 'convert_static_to_gif': True,
        'quick_panel_width': 360, 'quick_panel_height': 480,
        'appearance_mode': 'system', 'language': 'zh',
        'light_theme_key': 'white', 'dark_theme_key': 'white',
        'sidebar_icon_size': 20, 'sidebar_is_grid_mode': False,
        'category_grid_icon_size': 64, 'show_category_names': True,
        'show_setting_button': True, 'show_sidebar_tooltip': True,
        'render_batch_size': 50, 'recent_limit': 30, 'thumbnail_size': 120,
        'global_hotkey': 'ctrl+shift+e', 'quick_panel_hotkey': 'alt+2',
        'left_multiselect': False, 'left_filter': False, 'left_search': False,
        'runtime_icon': '', 'start_with_windows': False,
    }
    RANGES = {'preview_delay': (100,3000), 'preview_size': (100,800),
              'quick_panel_width': (250,800), 'quick_panel_height': (150,1000),
              'sidebar_icon_size': (16,64), 'category_grid_icon_size': (24,160),
              'render_batch_size': (1,200), 'recent_limit': (1,999), 'thumbnail_size': (60,300)}
    OPTIONS = {'appearance_mode': ('system','light','dark'), 'language': ('zh','zh_TW','en','ja'),
               'light_theme_key': ('white','black','rouge','sky','lavender','sage','apricot'),
               'dark_theme_key': ('white','black','rouge','sky','lavender','sage','apricot')}

    def __init__(self, library):
        self.session = library if isinstance(library, LibrarySession) else None
        self.context = library.context if self.session else library
        if not isinstance(self.context, LibraryContext):
            raise TypeError('ConfigService requires an explicit library context')
        self.base_dir = str(self.context.root)
        self.default_config = self.DEFAULTS.copy()
        self._draft = None
        self._stored = self._load_config()
        self.config = self._stored.copy()

    def _load_config(self):
        config = self.default_config.copy()
        with read_db(self.context.db('library')) as conn:
            saved = {key: json.loads(value) for key,value in conn.execute('SELECT key,value FROM preferences')}
        if 'appearance_mode' not in saved and 'theme_mode' in saved:
            saved['appearance_mode'] = saved['theme_mode']
        if 'theme_color' in saved:
            saved.setdefault('light_theme_key', saved['theme_color'])
            saved.setdefault('dark_theme_key', saved['theme_color'])
        config.update(saved)
        return config

    def _publish(self):
        self.config = {**self._stored, **(self._draft or {})}

    def _save_config(self, config_data):
        values = [(key, json.dumps(value, ensure_ascii=False)) for key,value in config_data.items()]
        with (self.session.task() if self.session else nullcontext()), self.context.transaction() as conn:
            conn.execute('DELETE FROM preferences')
            conn.executemany('INSERT INTO preferences VALUES (?,?)', values)
        self._stored = dict(config_data)
        self._publish()

    def get_actual_theme_is_dark(self):
        import darkdetect
        mode = self.get('appearance_mode','system')
        return mode == 'dark' if mode != 'system' else darkdetect.isDark()

    def get(self, key, default=None):
        return self.config.get(key, default)

    def saved(self, key):
        return self._stored.get(key, self.DEFAULTS.get(key))

    def set(self, key, value):
        if key in self.DEFAULTS:
            self.validate({**{k:self.get(k,d) for k,d in self.DEFAULTS.items()},key:value})
        if self.get(key) == value:
            return
        if self._draft is not None and key in self.DEFAULTS:
            self._draft[key] = value
            self._publish()
        else:
            self._save_config({**self._stored, key:value})

    @classmethod
    def validate(cls, values):
        if not isinstance(values, dict) or not set(values).issubset(cls.DEFAULTS):
            raise LibraryError('设置文件包含未知项目或资源库路径；未更改当前设置。')
        for key,value in values.items():
            default=cls.DEFAULTS[key]
            if type(value) is not type(default):
                raise LibraryError(f'设置项 {key} 类型不正确。')
            if key in cls.RANGES and not cls.RANGES[key][0] <= value <= cls.RANGES[key][1]:
                raise LibraryError(f'设置项 {key} 超出允许范围。')
            if key in cls.OPTIONS and value not in cls.OPTIONS[key]:
                raise LibraryError(f'设置项 {key} 的选项无效。')
            if isinstance(value,str) and (len(value)>200 or '\x00' in value):
                raise LibraryError('设置文本过长或含无效字符。')
            if key=='runtime_icon' and value and ('/' in value or '\\' in value or ':' in value or value in ('.','..')):
                raise LibraryError('运行时图标只能引用当前图库中的图片。')
        combined={**cls.DEFAULTS,**values}
        if combined['global_hotkey'] and combined['global_hotkey']==combined['quick_panel_hotkey']:
            raise LibraryError('两个全局快捷键不能相同。')
        return dict(values)

    @property
    def preview_active(self):
        return self._draft is not None

    @property
    def preview_dirty(self):
        return self._draft is not None and any(self._stored.get(k)!=v for k,v in self._draft.items())

    def begin_preview(self):
        if self._draft is None:
            self._draft={key:self.get(key,default) for key,default in self.DEFAULTS.items()}
            self._publish()

    def cancel_preview(self):
        self._draft=None
        self._publish()

    def save_preview(self):
        if self._draft is None:
            return
        self.validate(self._draft)
        self._save_config({**self._stored,**self._draft})
        # Leave the window open with a new saved baseline.
        self._draft={key:self._stored[key] for key in self.DEFAULTS}
        self._publish()

    def restore_defaults_preview(self):
        self.begin_preview()
        self._draft=self.DEFAULTS.copy()
        self._publish()

    def export_preferences(self, destination):
        # Credentials, machine/library paths, geometry and assets are excluded.
        values={key:self.get(key,default) for key,default in self.DEFAULTS.items()}
        values['runtime_icon']=''  # A local asset reference is not portable to another library.
        document={'format':'NekoriEmojy-preferences','version':1,'preferences':values}
        target = Path(destination).resolve()
        if target.is_relative_to(self.context.data_dir.resolve()) or target == self.context.root / 'nekori-library.json':
            raise LibraryError('请将设置导出到资源库数据文件夹之外。')
        if target.suffix.lower() != '.json':
            raise LibraryError('设置导出文件须使用 .json 扩展名。')
        atomic_json(target, document)

    def import_preferences_preview(self, source):
        path=Path(source)
        if path.stat().st_size>256*1024:
            raise LibraryError('设置文件过大，请选择导出的偏好文件。')
        try:
            value=json.loads(path.read_text(encoding='utf-8-sig'))
            if set(value)!= {'format','version','preferences'} or value['format']!='NekoriEmojy-preferences' or type(value['version']) is not int or value['version']!=1:
                raise ValueError('format')
            candidate=self.validate(value['preferences'])
        except (ValueError,TypeError,KeyError) as exc:
            raise LibraryError('设置文件格式无效，未更改当前预览或已保存设置。') from exc
        self.begin_preview()
        merged={**self._draft,**candidate}
        self.validate(merged)
        self._draft=merged
        self._publish()
