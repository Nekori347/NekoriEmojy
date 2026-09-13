from PySide6.QtGui import QGuiApplication, QImage, QClipboard
from PySide6.QtCore import QObject, QMimeData, QUrl
import os
import re
import html
import hashlib
from PIL import Image

class ClipboardService(QObject):
    def __init__(self, config_service=None):
        super().__init__()
        # 获取系统的剪切板
        self.clipboard = QGuiApplication.clipboard()
        self.config_service = config_service
        
        if config_service is None:
            raise TypeError("ClipboardService requires library-bound preferences")
        self.cache_dir = str(config_service.context.data_dir / "cache/gif_output")
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
        except Exception as e:
            print(f"[WARNING] 创建 GIF 转换缓存目录失败: {e}")

    def _get_config_service(self):
        if self.config_service:
            return self.config_service
        return None

    def _convert_static_to_1frame_gif(self, image_path):
        """
        将静态图片（PNG/JPG/WEBP 等）转换为高质量的 1 帧 GIF 格式并缓存。
        妥善处理 RGBA 透明通道：
        - GIF 仅支持 1 位透明索引（全透/不透）
        - 透明度 < 128 的像素设为完全透明，>= 128 保持不透明
        - 使用自适应调色板量化保留图像色彩
        :param image_path: 原始图片绝对路径
        :return: 转换后的 GIF 文件路径；如果转换失败则返回 None
        """
        try:
            if not os.path.exists(image_path):
                return None

            # 基于文件路径和修改时间生成缓存文件名，避免重复转换
            mtime = os.path.getmtime(image_path)
            file_key = f"{os.path.abspath(image_path)}_{mtime}"
            cache_filename = hashlib.md5(file_key.encode('utf-8')).hexdigest() + ".gif"
            cache_path = os.path.join(self.cache_dir, cache_filename)

            # 命中有效缓存直接返回
            if os.path.exists(cache_path) and os.path.getsize(cache_path) > 0:
                return cache_path

            # 读取原始图像并进行转换
            with Image.open(image_path) as img:
                # 如果本身是动态图（如 animated WebP 或 多帧 GIF），无需转为静态 1 帧
                if getattr(img, "is_animated", False):
                    return None

                img_rgba = img.convert("RGBA")
                alpha = img_rgba.getchannel('A')

                # 对 RGB 部分做调色板量化（最多 255 色，留 1 个索引给透明色）
                rgb_img = img_rgba.convert('RGB')
                p_img = rgb_img.quantize(colors=255, method=Image.Quantize.MEDIANCUT)

                # 将二值化透明掩码（Alpha < 128 为透明）写入调色板图像的指定透明索引（255）
                # 创建透明掩码: alpha < 128 设为 255 (标记透明)，其余为 0
                mask = Image.eval(alpha, lambda a: 255 if a < 128 else 0)
                p_img.paste(255, mask)

                # 保存为 1 帧 GIF，指定 transparency 索引为 255
                p_img.save(
                    cache_path,
                    format="GIF",
                    transparency=255,
                    disposal=2
                )

            return cache_path

        except Exception as e:
            print(f"[ERROR] 静态图片转 1 帧 GIF 失败 ({image_path}): {e}")
            return None

    def get_import_inputs(self):
        from services.image_inputs import snapshot_inputs
        return snapshot_inputs(self.clipboard.mimeData())

    def get_data_from_clipboard(self):
        # Historical adapter for integrations; normal UI consumes all inputs.
        inputs = self.get_import_inputs()
        if not inputs:
            return None, None
        first = inputs[0]
        if first.kind == 'file':
            return 'file', [item.value for item in inputs]
        return ('network_url' if first.kind == 'url' else first.kind), first.value

    def copy_image_to_clipboard(self, image_path):
        """
        将本地图片复制到系统剪切板（以文件和图像双重形式，确保聊天软件能识别表情并自适应气泡大小）
        - 若已是 GIF 格式，直接按原文件复制
        - 若是 PNG/JPG/WEBP 等静态图且开启了设置，则转为 1 帧 GIF 路径放入剪贴板
        - 发生任何异常时自动回退至原图路径，确保复制操作绝对可靠
        :param image_path: 图片绝对路径
        :return: bool 是否复制成功
        """
        try:
            mime_data = QMimeData()
            final_path = image_path

            # 检查用户是否开启了“静态图转 GIF”设置（默认开启）
            cfg = self._get_config_service()
            convert_enabled = cfg.get("convert_static_to_gif", True) if cfg else True

            _, ext = os.path.splitext(image_path)
            is_gif = ext.lower() == '.gif'

            # 仅在非 GIF 且开关开启时执行转 1 帧 GIF
            if convert_enabled and not is_gif:
                converted_gif = self._convert_static_to_1frame_gif(image_path)
                if converted_gif and os.path.exists(converted_gif):
                    final_path = converted_gif

            # 1. 放入文件路径 (这是支持表情发送的关键，微信QQ等会优先读取路径按表情或图片发送)
            mime_data.setUrls([QUrl.fromLocalFile(final_path)])
            
            # 2. 放入图像数据 (这是兜底，某些只支持接收位图的场景)
            image = QImage(final_path if os.path.exists(final_path) else image_path)
            if not image.isNull():
                mime_data.setImageData(image)
                
            self.clipboard.setMimeData(mime_data)
            return True
        except Exception as e:
            print(f"复制图片到剪切板失败: {e}")
            # 最终兜底尝试复制原图路径
            try:
                fallback_mime = QMimeData()
                fallback_mime.setUrls([QUrl.fromLocalFile(image_path)])
                img = QImage(image_path)
                if not img.isNull():
                    fallback_mime.setImageData(img)
                self.clipboard.setMimeData(fallback_mime)
                return True
            except Exception as fallback_err:
                print(f"剪贴板兜底回退复制失败: {fallback_err}")
        return False
