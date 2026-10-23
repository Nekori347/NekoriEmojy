import os
import json

class ConfigService:
    def __init__(self, app_dir=None, *, defer_create=False):
        from services.app_paths import app_data_dir
        self.base_dir = str(app_dir or app_data_dir())
        self.config_path = os.path.join(self.base_dir, "config.json")
        self.defer_create=defer_create
        self.config_existed=os.path.exists(self.config_path)
        self.load_error=None
        
        self.default_config = {
            "light_theme_key": "nekori",
            "dark_theme_key": "nekori",
            "appearance_mode": "system",
            "accent_color": "#FFF500",
            "language": "zh",
            "always_on_top": True,   # 默认置顶
            "hide_main_after_paste": False, # 点击发送后自动隐藏主面板
            "preview_delay": 500,    # 悬停预览延迟 (ms)
            "preview_size": 320,     # 悬停预览浮窗大小 (px)
            "preview_position": "floating", # 资源预览位置：fixed 内容面板右下角 overlay / floating 跟随鼠标
            "use_system_font": False, # 是否使用系统默认字体
            "convert_static_to_gif": True, # 发送时将静态图转为1帧GIF以适配聊天软件表情尺寸
            "show_setting_button": True, # 在主面板显示设置按钮
            "show_multi_select_button": True, # 在主面板显示管理模式按钮
            "gallery_click_action": "select", # 主图库单击资源：select 选择 / send 快速发送
            # 托盘手势 → 动作；三个手势共用同一套动作，右键固定打开菜单
            "tray_left_click": "toggle_main",
            "tray_left_double_click": "toggle_main",
            "tray_middle_click": "none",
            "show_taskbar_icon": True,  # 在任务栏显示应用图标（关闭后仍驻留托盘）
            "settings_preview": True, # 视觉设置实时预览
            "ocr_auto": False, # 安装 OCR 后启用；已有表情仍需主动补识别
            "tooltip_delay": 120,     # 全局 Tooltip 延迟 (ms)
            "thumbnail_size": 120,
            "render_batch_size": 50,
            "recent_limit": 30,
            "quick_panel_width": 360,
            "quick_panel_height": 480,
            "quick_panel_thumbnail_size": 72,
            "sidebar_icon_size": 20,
            "gallery_node_icon_size": 22,
            "sidebar_width_list": 220,
            "sidebar_mode": "tree",
            "sidebar_show_labels": True,
            "tag_panel_placement": "bottom",
            "tag_panel_expanded": True,
            "tag_panel_horizontal_extent": 116,
            "tag_panel_vertical_extent": 220,
            "tag_sort": "manual",
            "sidebar_sort": "manual",
            "resource_sort": "manual",
            "global_hotkey": "ctrl+shift+e",
            "quick_panel_hotkey": "alt+2",
            "esc_hide_main": False,
            "esc_hide_quick": False,
        }
        self.config = self._load_config()
        self.preview_values = {}  # In-memory visual preview never joins a persisted config write.

    def _load_config(self):
        if not os.path.exists(self.config_path):
            if not self.defer_create:self._save_config(self.default_config)
            return self.default_config.copy()
            
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                if not isinstance(loaded,dict):raise ValueError('Configuration must be an object')
                # 合并默认配置，防止新增字段时报错
                config = self.default_config.copy()
                config.update(loaded)
                if 'tag_panel_horizontal_extent' not in loaded and 'tag_panel_height' in loaded:
                    config['tag_panel_horizontal_extent'] = loaded['tag_panel_height']
                return config
        except Exception as e:
            self.load_error=e
            print(f"读取配置失败，使用默认配置: {e}")
            return self.default_config.copy()

    def _save_config(self, config_data):
        temporary = self.config_path + '.tmp'
        try:
            # 确保 data 目录存在
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(temporary, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)
            os.replace(temporary, self.config_path)
        except Exception as e:
            try:os.remove(temporary)
            except OSError:pass
            raise RuntimeError(f"保存配置失败: {e}") from e

    def get_actual_theme_is_dark(self):
        """获取当前软件应该采用的真实明暗状态"""
        import darkdetect
        theme_mode = self.get("theme_mode", "system")
        if theme_mode == "dark":
            return True
        elif theme_mode == "light":
            return False
        else:
            return darkdetect.isDark()

    def get(self, key, default=None):
        return getattr(self, "preview_values", {}).get(key, self.config.get(key, default))

    def set(self, key, value):
        self.config[key] = value
        self._save_config(self.config)

    def update(self, values):
        """Write several keys with one file write; returns whether anything changed."""
        changed = False
        for key, value in values.items():
            if self.config.get(key) != value:
                self.config[key] = value
                changed = True
        if changed:
            self._save_config(self.config)
        return changed

    def discard(self, key):
        """Drop a key that is no longer part of the config."""
        if key not in self.config:
            return False
        self.config.pop(key, None)
        self._save_config(self.config)
        return True
