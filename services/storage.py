import os
from datetime import datetime
import hashlib
import io
from contextlib import closing, nullcontext
from functools import wraps
from services.library import LibraryContext, LibrarySession, LibraryError, read_db, connect_existing
from services.diagnostics import event
from PIL import Image


def library_operation(method):
    @wraps(method)
    def bound(self, *args, **kwargs):
        session = getattr(self, "session", None)
        with (session.task() if session else nullcontext()), self.lock:
            try:
                return method(self, *args, **kwargs)
            except Exception as exc:
                event("storage.operation_failed", level="error", stage=method.__name__, error=exc)
                raise
    return bound


class StorageService:
    SUPPORTED_FORMATS = ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.webm')

    def __init__(self, library):
        self.session = library if isinstance(library, LibrarySession) else None
        self.context = library.context if self.session else library
        if not isinstance(self.context, LibraryContext):
            raise TypeError("StorageService requires an explicit library context")
        self.lock = self.context.lock
        self.base_dir = str(self.context.root)
        self.data_dir = str(self.context.data_dir)
        self.images_dir = str(self.context.images_dir)
        self.inbox_dir = str(self.context.data_dir / "inbox")
        self.inbox_failed_dir = str(self.context.data_dir / "inbox/failed")
        for name in ("features", "metadata", "categories", "order", "recent"):
            setattr(self, name + "_db_path", str(self.context.db(name)))
        self._hashes_cache = self._load_hashes()
        self._images_cache = []
        self._images_dirty = True
        self._categories_cache = {}
        self._image_to_categories_cache = {}
        self._categories_dirty = True
        self._metadata_cache = {}
        self._metadata_dirty = True
        self._recent_cache = None
        self._sync_key_index = None
        self._import_number = 0
        # Opening never repairs, hashes or rewrites user state.


    def _get_sync_key_index(self):
        # Compatibility view over persistent values; never opens image bytes.
        with read_db(self.features_db_path) as conn:
            return {key: name for key, name in conn.execute(
                "SELECT sync_key, image_path FROM resource_identity WHERE state='ready' AND sync_key IS NOT NULL ORDER BY image_path DESC")}


    # ==========================
    # 哈希缓存 (Hashes)
    # ==========================

    def _load_hashes(self):
        with read_db(self.features_db_path) as conn:
            return {md5: path for path, md5 in conn.execute(
                "SELECT image_path, md5 FROM image_features WHERE md5 IS NOT NULL") if md5}


    def _save_hashes(self):
        with self.lock, closing(connect_existing(self.features_db_path)) as conn, conn:
            conn.executemany("""INSERT INTO image_features(image_path, md5) VALUES (?, ?)
                ON CONFLICT(image_path) DO UPDATE SET md5=excluded.md5""",
                [(self._to_filename(path), md5) for md5, path in self._hashes_cache.items()])


    def _repair_orphaned_resources(self):
        """自愈孤儿资源：检查本地图片文件是否缺失索引记录，缺失时自动补齐"""
        with self.lock:
            if not os.path.exists(self.images_dir):
                return
            actual_filenames = sorted(f for f in os.listdir(self.images_dir) if f.lower().endswith(self.SUPPORTED_FORMATS))
            if not actual_filenames:
                return

            all_saved = set(self.get_all_images())
            saved_hashes_filenames = set(os.path.basename(p) for p in self._hashes_cache.values())
            
            repaired = False
            for fname in actual_filenames:
                abspath = self._to_abspath(fname)
                if abspath not in all_saved or fname not in saved_hashes_filenames:
                    try:
                        with open(abspath, 'rb') as f:
                            data_bytes = f.read()
                        _, ext = os.path.splitext(fname)
                        # 计算哈希并补齐 _hashes_cache
                        file_hash = self._calculate_bytes_hash(data_bytes)
                        if file_hash:
                            self._hashes_cache[file_hash] = fname
                        repaired = True
                    except Exception as e:
                        print(f"[WARNING] 自愈孤儿文件 {fname} 失败: {e}")
            if repaired:
                try:
                    self._save_hashes()
                    self._images_dirty = True
                    # 重新生成并保存 order
                    all_imgs = self.get_all_images()
                    self.save_order(all_imgs)
                except Exception as e:
                    print(f"[WARNING] 保存自愈数据失败: {e}")

    def _calculate_pixel_hash(self, img):
        """计算图片纯像素数据的 MD5 哈希值，用于精准去重"""
        try:
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            return hashlib.md5(img.tobytes()).hexdigest()
        except Exception as e:
            print(f"[WARNING] 计算像素哈希失败: {e}")
            return None

    def _calculate_bytes_hash(self, data_bytes):
        """计算二进制数据的 MD5 哈希值"""
        return hashlib.md5(data_bytes).hexdigest()

    def _to_filename(self, filepath):
        """将绝对路径转换为单纯的文件名"""
        return os.path.basename(filepath)

    def _to_abspath(self, filename):
        path = os.path.realpath(os.path.join(self.images_dir, filename))
        root = os.path.realpath(self.images_dir)
        if os.path.commonpath([path, root]) != root:
            raise LibraryError("资源引用越出当前库。")
        return os.path.normcase(path)


    # ==========================
    # 所有图片与排序 (Order)
    # ==========================

    def get_all_images(self):
        """Only committed resources are visible; order is always read from SQLite."""
        if not self._images_dirty:
            return self._images_cache.copy()
        with read_db(self.order_db_path) as conn:
            names = [row[0] for row in conn.execute("SELECT image_path FROM item_orders ORDER BY sort_order")]
        with read_db(self.features_db_path) as conn:
            known = {row[0] for row in conn.execute("SELECT image_path FROM resource_identity WHERE state IN ('ready','unindexed','error')")}
            pending = {row[0] for row in conn.execute("SELECT image_path FROM resource_identity WHERE state='pending'")}
        ordered = sorted(known - set(names), reverse=True) + names
        self._images_cache = [self._to_abspath(name) for name in ordered if name not in pending and os.path.isfile(self._to_abspath(name))]
        self._images_dirty = False
        return self._images_cache.copy()

    @library_operation
    def move_image_to_front(self, filepath, target_category=None):
        """将指定图片在主排序（全部表情）及所有其存在的分类夹（以及目标分类）中提升到最前面"""
        abs_path = self._to_abspath(filepath)

        # 1. 提升在主排序（全部表情）中的位置
        all_images = list(self.get_all_images())
        if abs_path in all_images:
            all_images.remove(abs_path)
            all_images.insert(0, abs_path)
            self.save_order(all_images)

        # 2. 若指定了目标分类，确保包含该图片
        if target_category and target_category not in ("全部表情", "未分类"):
            self.add_image_to_category(abs_path, target_category)

        # 3. 提升在其关联的所有分类夹中的位置
        categories = self.get_all_categories()
        changed = False
        for cat_name, paths in categories.items():
            if abs_path in paths:
                if abs_path in paths:
                    paths.remove(abs_path)
                paths.insert(0, abs_path)
                changed = True
        if changed:
            self.save_categories(categories)

    @library_operation
    def save_order(self, filepaths):
        filenames = list(dict.fromkeys(self._to_filename(p) for p in filepaths))
        with closing(connect_existing(self.order_db_path)) as conn, conn:
            conn.execute("DELETE FROM item_orders")
            conn.executemany("INSERT INTO item_orders VALUES (?, ?)",
                             [(name, index) for index, name in enumerate(filenames)])
        self._images_dirty = True


    # ==========================
    # 分类 (Categories)
    # ==========================
    
    def get_all_categories(self):
        if self._categories_dirty:
            with read_db(self.categories_db_path) as conn:
                data = {row[0]: [] for row in conn.execute("SELECT name FROM categories ORDER BY sort_order, id")}
                reverse = {}
                for category, name in conn.execute("SELECT category_name, image_path FROM category_images"):
                    if category in data:
                        path = self._to_abspath(name)
                        data[category].append(path)
                        reverse.setdefault(path, []).append(category)
            self._categories_cache = data
            self._image_to_categories_cache = reverse
            self._categories_dirty = False
        return {name: paths.copy() for name, paths in self._categories_cache.items()}


    @library_operation
    def save_categories(self, categories_data):
        with closing(connect_existing(self.categories_db_path)) as conn, conn:
            existing = {row[0] for row in conn.execute("SELECT name FROM categories")}
            for name in existing - categories_data.keys():
                conn.execute("DELETE FROM category_images WHERE category_name=?", (name,))
                conn.execute("DELETE FROM categories WHERE name=?", (name,))
            for index, (name, paths) in enumerate(categories_data.items()):
                conn.execute("""INSERT INTO categories(name, sort_order) VALUES (?, ?)
                    ON CONFLICT(name) DO UPDATE SET sort_order=excluded.sort_order""", (name, index))
                members = {self._to_filename(path) for path in paths}
                previous = {row[0] for row in conn.execute("SELECT image_path FROM category_images WHERE category_name=?", (name,))}
                # Retained memberships must not fire removal triggers or erase subgroups.
                conn.executemany("DELETE FROM category_images WHERE category_name=? AND image_path=?",
                                 [(name, path) for path in previous - members])
                conn.executemany("INSERT OR IGNORE INTO category_images VALUES (?, ?)",
                                 [(name, self._to_filename(path)) for path in paths])
        self._categories_dirty = True


    def get_exportable_categories(self):
        """获取可导出的用户分类名称列表，保持当前分类排序"""
        categories = self.get_all_categories()
        return list(categories.keys())

    @library_operation
    def add_category(self, category_name):
        """新建一个分类"""
        categories = self.get_all_categories()
        if category_name not in categories:
            categories[category_name] = []
            self.save_categories(categories)
            return True
        return False

    @library_operation
    def rename_category(self, old_name, new_name):
        with closing(connect_existing(self.categories_db_path)) as conn, conn:
            names = {row[0] for row in conn.execute("SELECT name FROM categories")}
            if old_name not in names or new_name in names or not new_name.strip():
                return False
            conn.execute("UPDATE categories SET name=? WHERE name=?", (new_name, old_name))
            conn.execute("UPDATE category_images SET category_name=? WHERE category_name=?", (new_name, old_name))
        self._categories_dirty = True
        return True


    @library_operation
    def remove_category(self, category_name):
        with closing(connect_existing(self.categories_db_path)) as conn, conn:
            conn.execute("DELETE FROM category_images WHERE category_name=?", (category_name,))
            changed = conn.execute("DELETE FROM categories WHERE name=?", (category_name,)).rowcount > 0
        self._categories_dirty = True
        return changed


    @library_operation
    def add_images_to_category(self, filepaths, category_name):
        from services.importing import add_relations
        names = list(dict.fromkeys(self._to_filename(self._to_abspath(p)) for p in filepaths))
        for name in names:
            if not os.path.isfile(self._to_abspath(name)):
                raise LibraryError("分类操作中的资源已不存在。")
        with self.context.transaction() as conn:
            count = add_relations(conn, names, category_name)
        self._categories_dirty = True
        return count

    def add_image_to_category(self, filepath, category_name):
        return "success" if self.add_images_to_category([filepath], category_name) else "already_exists"

    @library_operation
    def remove_image_from_category(self, filepath, category_name):
        """将图片从指定分类移除"""
        categories = self.get_all_categories()
        abs_filepath = self._to_abspath(filepath)
        if category_name in categories and abs_filepath in categories[category_name]:
            categories[category_name].remove(abs_filepath)
            self.save_categories(categories)
            return True
        return False
        
    def get_images_by_category(self, category_name):
        """获取特定分类下的所有图片"""
        all_ordered = self.get_all_images()
        
        if category_name == "全部表情" or category_name is None:
            return all_ordered
            
        categories = self.get_all_categories()
        paths = categories.get(category_name, [])
        paths_set = set(paths)
        result = [p for p in all_ordered if p in paths_set]
        return result

    def get_categories_by_image(self, filepath):
        """反向查询：获取指定图片所属的所有分类名称列表"""
        self.get_all_categories()
        return self._image_to_categories_cache.get(filepath, [])

    def get_image_to_categories_map(self):
        """获取图片到分类的反向映射字典"""
        self.get_all_categories()
        return self._image_to_categories_cache

    def is_animated(self, filepath):
        """判断图片是否为动图格式"""
        ext = os.path.splitext(filepath)[1].lower()
        return ext in ['.gif', '.webp']

    # ==========================
    # 最近使用 (Recent)
    # ==========================
    
    def _get_recent_limit(self):
        if getattr(self, "context", None):
            from services.config import ConfigService
            return max(1, int(ConfigService(self.context).get("recent_limit", 30)))
        return 30


    def get_recent_images(self, limit=None):
        limit = self._get_recent_limit() if limit is None else max(1, int(limit))
        if self._recent_cache is None:
            with read_db(self.recent_db_path) as conn:
                self._recent_cache = [self._to_abspath(row[0]) for row in conn.execute(
                    "SELECT image_path FROM recent_history ORDER BY updated_at DESC, id DESC")]
        return [path for path in self._recent_cache if os.path.isfile(path)][:limit]


    @library_operation
    def add_recent_image(self, filepath, limit=None):
        limit = self._get_recent_limit() if limit is None else max(1, int(limit))
        name = self._to_filename(filepath)
        with closing(connect_existing(self.recent_db_path)) as conn, conn:
            conn.execute("DELETE FROM recent_history WHERE image_path=?", (name,))
            conn.execute("INSERT INTO recent_history(image_path) VALUES (?)", (name,))
            conn.execute("""DELETE FROM recent_history WHERE id NOT IN
                (SELECT id FROM recent_history ORDER BY updated_at DESC, id DESC LIMIT ?)""", (limit,))
        self._recent_cache = None


    # ==========================
    # 分类图标 (Category Icons)
    # ==========================
    
    def get_all_category_icons(self):
        with read_db(self.categories_db_path) as conn:
            return {name: self._to_abspath(icon) if icon.lower().endswith(self.SUPPORTED_FORMATS) else icon
                    for name, icon in conn.execute("SELECT name, icon_path FROM categories WHERE icon_path IS NOT NULL AND icon_path != ''")}

            
    @library_operation
    def save_category_icons(self, icons_data):
        with closing(connect_existing(self.categories_db_path)) as conn, conn:
            conn.execute("UPDATE categories SET icon_path=NULL")
            conn.executemany("UPDATE categories SET icon_path=? WHERE name=?",
                [(self._to_filename(value) if value.lower().endswith(self.SUPPORTED_FORMATS) else value, name)
                 for name, value in icons_data.items()])


    @library_operation
    def set_category_icon(self, category_name, filepath):
        icons = self.get_all_category_icons()
        icons[category_name] = filepath
        self.save_category_icons(icons)
        
    def get_category_icon(self, category_name):
        icons = self.get_all_category_icons()
        return icons.get(category_name, None)

    # ==========================
    # 关键词元数据 (Metadata)
    # ==========================
    
    @staticmethod
    def parse_tags(tags_str):
        if not tags_str: return []
        tags = []
        for t in tags_str.split(' '):
            if t and t not in tags:
                tags.append(t)
        return tags

    @staticmethod
    def serialize_tags(tags_list):
        return " ".join(tags_list)

    @staticmethod
    def merge_tags(existing_tags_str, new_tags_str):
        existing_list = StorageService.parse_tags(existing_tags_str)
        new_list = StorageService.parse_tags(new_tags_str)
        for tag in new_list:
            if tag not in existing_list:
                existing_list.append(tag)
        return StorageService.serialize_tags(existing_list)

    @staticmethod
    def remove_tags(existing_tags_str, remove_tags_str):
        existing_list = StorageService.parse_tags(existing_tags_str)
        remove_list = StorageService.parse_tags(remove_tags_str)
        final_list = [tag for tag in existing_list if tag not in remove_list]
        return StorageService.serialize_tags(final_list)

    def get_all_metadata(self):
        if self._metadata_dirty:
            with read_db(self.metadata_db_path) as conn:
                self._metadata_cache = {self._to_abspath(name): keywords or "" for name, keywords in
                                        conn.execute("SELECT image_path, keywords FROM image_metadata")}
            self._metadata_dirty = False
        return self._metadata_cache.copy()


    @library_operation
    def save_metadata(self, metadata):
        with closing(connect_existing(self.metadata_db_path)) as conn, conn:
            conn.executemany("""INSERT INTO image_metadata(image_path, keywords) VALUES (?, ?)
                ON CONFLICT(image_path) DO UPDATE SET keywords=excluded.keywords""",
                [(self._to_filename(name), str(value)) for name, value in metadata.items()])
        self._metadata_dirty = True


    def get_image_keywords(self, filepath):
        metadata = self.get_all_metadata()
        return metadata.get(self._to_abspath(filepath), "")

    @library_operation
    def set_image_keywords(self, filepath, keywords_str):
        metadata = self.get_all_metadata()
        metadata[self._to_abspath(filepath)] = keywords_str
        self.save_metadata(metadata)

    def search_images(self, keyword, category_name="全部表情"):
        images = self.get_images_by_category(category_name)
        if not keyword or not keyword.strip():
            return images
            
        keyword = keyword.strip().lower()
        metadata = self.get_all_metadata()
        result = []
        for img in images:
            img_kw = metadata.get(img, "").lower()
            if keyword in img_kw:
                result.append(img)
        return result

    def generate_new_filename(self, extension=".png"):
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        return f"{timestamp}{extension}"

    @staticmethod
    def detect_format_magic(data_bytes: bytes) -> str:
        """
        根据文件魔数识别真实格式
        返回值: 'webm', 'webp', 'gif', 'png', 'jpeg', 'apng', 'bmp', 'tiff', 或 'unknown'
        """
        if not data_bytes or len(data_bytes) < 4:
            return "unknown"

        # WebM / Matroska 魔数: 1A 45 DF A3
        if data_bytes.startswith(b"\x1a\x45\xdf\xa3"):
            return "webm"

        # RIFF 容器 (WebP): RIFF....WEBP
        if data_bytes.startswith(b"RIFF") and len(data_bytes) >= 12 and data_bytes[8:12] == b"WEBP":
            return "webp"

        # GIF 魔数: GIF87a / GIF89a
        if data_bytes.startswith(b"GIF87a") or data_bytes.startswith(b"GIF89a"):
            return "gif"

        # PNG 魔数: 89 50 4E 47 0D 0A 1A 0A
        if data_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            # 检查是否为 APNG
            if b"acTL" in data_bytes[:1024]:
                return "apng"
            return "png"

        # JPEG 魔数: FF D8 FF
        if data_bytes.startswith(b"\xff\xd8\xff"):
            return "jpeg"

        # BMP 魔数: BM
        if data_bytes.startswith(b"BM"):
            return "bmp"

        # TIFF 魔数: II*\x00 或 MM\x00*
        if data_bytes.startswith(b"II*\x00") or data_bytes.startswith(b"MM\x00*"):
            return "tiff"

        return "unknown"

    def _convert_source_to_standard_bytes(self, data_bytes: bytes, source_path=None) -> tuple[bytes, str, bool]:
        """
        魔数识别并对动态格式进行归一化转码
        返回: (standard_bytes, format_type, is_animated)
        若转码失败则抛出异常或返回 None
        """
        fmt = self.detect_format_magic(data_bytes)

        # 1. 动态 WebM 视频 -> 转为 GIF
        if fmt == "webm":
            from services.webm_converter import is_ffmpeg_available, convert_video_to_gif
            if not is_ffmpeg_available():
                raise RuntimeError("FFmpeg 缺失或不可用，无法转换 WebM 动态贴纸")

            import tempfile
            temp_in = None
            temp_out = None
            try:
                # 写入临时文件供 FFmpeg 读取（若已有 source_path 且格式相符则直接使用，否则写入临时文件）
                if source_path and os.path.exists(source_path):
                    temp_in = source_path
                    need_clean_in = False
                else:
                    fd_in, temp_in = tempfile.mkstemp(suffix=".webm")
                    with os.fdopen(fd_in, "wb") as f:
                        f.write(data_bytes)
                    need_clean_in = True

                fd_out, temp_out = tempfile.mkstemp(suffix=".gif")
                os.close(fd_out)

                convert_video_to_gif(temp_in, temp_out)

                if not os.path.exists(temp_out) or os.path.getsize(temp_out) == 0:
                    raise RuntimeError("FFmpeg 转换输出文件无效或为空")

                with open(temp_out, "rb") as f:
                    gif_bytes = f.read()

                # 校验转换后的 GIF
                with Image.open(io.BytesIO(gif_bytes)) as test_img:
                    n_frames = getattr(test_img, "n_frames", 1)
                    if n_frames < 1:
                        raise RuntimeError("转换后的 GIF 图像帧数无效")

                return gif_bytes, "gif", True
            finally:
                if temp_in and need_clean_in and os.path.exists(temp_in):
                    try:
                        os.remove(temp_in)
                    except Exception:
                        pass
                if temp_out and os.path.exists(temp_out):
                    try:
                        os.remove(temp_out)
                    except Exception:
                        pass

        # 2. WebP 格式：判断是动态还是静态
        if fmt == "webp":
            try:
                with Image.open(io.BytesIO(data_bytes)) as img:
                    is_animated = getattr(img, "is_animated", False) and getattr(img, "n_frames", 1) > 1
            except Exception as e:
                raise RuntimeError(f"解析 WebP 图像失败: {e}")

            if is_animated:
                # Preserve the original animation, timing, alpha and WebP quality.
                return data_bytes, "webp", True
            else:
                # 静态 WebP 不转为 GIF，保持现有静态处理方式
                return data_bytes, "webp", False

        # 3. APNG 格式 -> 转换为 GIF
        if fmt == "apng":
            try:
                from services.qq_extractor import QQExtractor
                import tempfile
                fd_in, temp_in = tempfile.mkstemp(suffix=".png")
                with os.fdopen(fd_in, "wb") as f:
                    f.write(data_bytes)
                temp_gif = None
                try:
                    temp_gif = QQExtractor.convert_apng_to_gif(temp_in)
                    if temp_gif and os.path.exists(temp_gif):
                        with open(temp_gif, "rb") as f:
                            gif_bytes = f.read()
                        return gif_bytes, "gif", True
                    else:
                        raise RuntimeError("APNG 转换 GIF 失败")
                finally:
                    if os.path.exists(temp_in):
                        try:
                            os.remove(temp_in)
                        except Exception:
                            pass
                    if temp_gif and os.path.exists(temp_gif):
                        try:
                            os.remove(temp_gif)
                        except Exception:
                            pass
            except Exception as e:
                raise RuntimeError(f"APNG 转 GIF 异常: {e}")

        # 4. 普通 GIF / PNG / JPEG / BMP / TIFF
        # GIF 不能仅依据文件格式判定为动图：剪贴板发送静态图片时，
        # services.clipboard 会将 PNG 转换为单帧 GIF。单帧 GIF 应先还原为
        # 静态 PNG，使其进入现有的 RGBA 清理与像素哈希去重流程。
        if fmt == "gif":
            try:
                with Image.open(io.BytesIO(data_bytes)) as img:
                    n_frames = getattr(img, "n_frames", 1)
                    if n_frames <= 1:
                        img.seek(0)
                        rgba_img = img.convert("RGBA").copy()
                        output_io = io.BytesIO()
                        rgba_img.save(output_io, format="PNG", optimize=True)
                        return output_io.getvalue(), "png", False
            except Exception as e:
                raise RuntimeError(f"解析单帧 GIF 失败: {e}")

            # 多帧 GIF 保留原始数据，继续走动态资源流程。
            return data_bytes, "gif", True

        return data_bytes, fmt, False

    def _standardize_and_save(self, data_bytes, original_ext, source_path=None, target_category=None):
        from services.importing import commit_image
        import time
        import threading
        started = time.perf_counter()
        self._import_number += 1
        event("import.started", count={"sequence": self._import_number, "ui_thread": int(threading.current_thread() is threading.main_thread())})
        norm_bytes, norm_fmt, animated = self._convert_source_to_standard_bytes(data_bytes, source_path)
        with Image.open(io.BytesIO(norm_bytes)) as img:
            animated = animated or getattr(img, "n_frames", 1) > 1
            if animated:
                final_bytes = norm_bytes
                extension = ".webp" if norm_fmt == "webp" else ".gif"
            else:
                clean = Image.new("RGBA", img.size)
                clean.paste(img.convert("RGBA"), (0, 0))
                output = io.BytesIO()
                clean.save(output, format="PNG", optimize=True)
                final_bytes, extension = output.getvalue(), ".png"
        event("import.normalized", elapsed_ms=round((time.perf_counter()-started)*1000, 2), count={"input_bytes": len(data_bytes)})
        result = commit_image(self.context, final_bytes, extension, target_category)
        self._images_dirty = True
        self._categories_dirty = True
        self._metadata_dirty = True
        return self._to_abspath(result[0]), result[1]

    @library_operation
    def save_image(self, qimage, target_category=None):
        from PySide6.QtCore import QByteArray, QBuffer, QIODevice
        byte_array = QByteArray()
        buffer = QBuffer(byte_array)
        buffer.open(QIODevice.WriteOnly)
        if not qimage.save(buffer, "PNG"):
            raise LibraryError("剪贴板图片编码失败。")
        return self._standardize_and_save(byte_array.data(), ".png", target_category=target_category)

    @library_operation
    def save_file(self, source_path, target_category=None):
        from services.importing import MAX_INPUT_BYTES
        try:
            before = os.stat(source_path)
            if before.st_size > MAX_INPUT_BYTES:
                raise LibraryError("图片超过 128 MiB 导入上限。")
            with open(source_path, 'rb') as source:
                data = source.read(MAX_INPUT_BYTES + 1)
            after = os.stat(source_path)
            if len(data) > MAX_INPUT_BYTES or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise LibraryError("源文件正在变化，请稍后重试。")
            return self._standardize_and_save(data, '', source_path=source_path, target_category=target_category)
        except Exception as exc:
            event("import.failed", level="warning", stage="file", error=exc)
            return None, False

    def force_reload(self):
        """Invalidate memory only; never backfill JSON or rewrite state."""
        self._images_dirty = True
        self._categories_dirty = True
        self._metadata_dirty = True
        self._recent_cache = None
        self._hashes_cache = self._load_hashes()
        self._sync_key_index = None


    def cleanup_dead_links(self):
        """清除不存在的文件在排序、分类、元数据、哈希、最近记录及数据库中的残留记录(死链自愈)"""
        with self.lock:
            # A. 扫描实际存在的文件
            if not os.path.exists(self.images_dir):
                return
            actual_filenames = set(f for f in os.listdir(self.images_dir) if f.lower().endswith(self.SUPPORTED_FORMATS))
            actual_paths = set(self._to_abspath(f) for f in actual_filenames)
            
            # B. 自愈 order
            all_images = self.get_all_images()
            cleaned_images = [p for p in all_images if p in actual_paths]
            if len(cleaned_images) != len(all_images):
                self.save_order(cleaned_images)
                
            # C. 自愈 categories
            categories = self.get_all_categories()
            changed_cats = False
            for cat, paths in categories.items():
                cleaned_paths = [p for p in paths if p in actual_paths]
                if len(cleaned_paths) != len(paths):
                    categories[cat] = cleaned_paths
                    changed_cats = True
            if changed_cats:
                self.save_categories(categories)
                
            # D. 自愈 metadata
            metadata = self.get_all_metadata()
            changed_meta = False
            keys_to_del = [p for p in metadata if p not in actual_paths]
            for k in keys_to_del:
                del metadata[k]
                changed_meta = True
            if changed_meta:
                self.save_metadata(metadata)
                
            # E. 自愈 recent
            recent = self.get_recent_images()
            cleaned_recent = [p for p in recent if p in actual_paths]
            if len(cleaned_recent) != len(recent):
                self._recent_cache = cleaned_recent
                pass  # SQLite state is authoritative.
                    
            # F. 自愈 hashes
            changed_hashes = False
            hash_keys_to_remove = []
            for h, f in self._hashes_cache.items():
                if f not in actual_filenames:
                    hash_keys_to_remove.append(h)
            for h in hash_keys_to_remove:
                del self._hashes_cache[h]
                changed_hashes = True
            if changed_hashes:
                self._save_hashes()
                
            # G. 自愈数据库中的记录
            try:
                db_paths = {
                    'features': self.features_db_path,
                    'metadata': self.metadata_db_path,
                    'categories': self.categories_db_path,
                    'order': self.order_db_path,
                    'recent': self.recent_db_path
                }
                for db_name, db_path in db_paths.items():
                    if os.path.exists(db_path):
                        with connect_existing(db_path) as conn:
                            cursor = conn.cursor()
                            table_name = {
                                'features': 'image_features',
                                'metadata': 'image_metadata',
                                'categories': 'category_images',
                                'order': 'item_orders',
                                'recent': 'recent_history'
                            }[db_name]
                            
                            cursor.execute(f"SELECT DISTINCT image_path FROM {table_name}")
                            rows = cursor.fetchall()
                            dead_in_db = []
                            for r in rows:
                                fname = self._to_filename(r[0])
                                if fname not in actual_filenames:
                                    dead_in_db.append((r[0],))
                                    
                            if dead_in_db:
                                cursor.executemany(f"DELETE FROM {table_name} WHERE image_path = ?", dead_in_db)
                                conn.commit()
            except Exception as e:
                print(f"[WARNING] 数据库死链清理提示: {e}")

    @library_operation
    def delete_images_batch(self, filepaths, progress_callback=None, cancel_check=None):
        from services.importing import delete_resources
        result = delete_resources(self.context, filepaths, progress_callback, cancel_check)
        self.force_reload()
        return result

    def delete_image(self, filepath):
        """从本地删除指定的图片文件，并同步清理分类、元数据、哈希、最近使用（数据库同步清理）"""
        result = self.delete_images_batch([filepath])
        return result.get('deleted', 0) > 0 or result.get('missing_cleaned', 0) > 0
