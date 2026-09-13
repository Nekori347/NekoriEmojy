import os
import sys
import sqlite3
from services.library import connect_existing
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

class FeatureDB:
    """
    表情包图像特征存储与 SQLite 数据库管理模块，支持从旧 JSON 数据平滑迁移。
    """

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            raise TypeError("FeatureDB requires an explicit library database path")
        self.db_path = os.path.abspath(db_path)
        self.data_dir = os.path.dirname(self.db_path)
        self.base_dir = os.path.dirname(self.data_dir)
        if not os.path.isfile(self.db_path):
            raise FileNotFoundError("Library feature database is missing")

    def _get_connection(self) -> sqlite3.Connection:
        """获取 SQLite 数据库连接，设置 row_factory 便于按字典形式读取列名"""
        conn = connect_existing(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """初始化数据库表 image_features"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS image_features (
                        image_path TEXT PRIMARY KEY,
                        md5 TEXT,
                        dhash TEXT,
                        phash TEXT,
                        quality_score REAL DEFAULT 0.0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.commit()
                logger.info(f"[FeatureDB] 数据库初始化成功: {self.db_path}")
        except Exception as e:
            logger.error(f"[FeatureDB] 数据库初始化失败: {e}")
            print(f"[ERROR] [FeatureDB] 数据库初始化失败: {e}")

    def save_feature(
        self,
        image_path: str,
        md5: str,
        dhash: Optional[str] = None,
        phash: Optional[str] = None,
        quality_score: float = 0.0
    ) -> bool:
        """
        新增或更新记录 (UPSERT)
        :param image_path: 图片相对路径或文件名 (主键)
        :param md5: 图片 MD5
        :param dhash: 64位 dHash 字符串（可留空）
        :param phash: 64位 pHash 字符串（可留空）
        :param quality_score: 画质得分 (默认 0.0)
        :return: bool 是否成功
        """
        sql = """
        INSERT INTO image_features (image_path, md5, dhash, phash, quality_score)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(image_path) DO UPDATE SET
            md5 = excluded.md5,
            dhash = COALESCE(excluded.dhash, image_features.dhash),
            phash = COALESCE(excluded.phash, image_features.phash),
            quality_score = CASE WHEN excluded.quality_score != 0.0 THEN excluded.quality_score ELSE image_features.quality_score END;
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, (image_path, md5, dhash, phash, quality_score))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"[FeatureDB] save_feature 失败 ({image_path}): {e}")
            print(f"[ERROR] [FeatureDB] save_feature 失败 ({image_path}): {e}")
            return False

    def get_feature(self, image_path: str) -> Optional[Dict[str, Any]]:
        """
        查询单张图的特征
        :param image_path: 图片相对路径或文件名
        :return: 包含字段信息的字典，若未找到则返回 None
        """
        sql = "SELECT image_path, md5, dhash, phash, quality_score, created_at FROM image_features WHERE image_path = ?"
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, (image_path,))
                row = cursor.fetchone()
                if row:
                    return dict(row)
                return None
        except Exception as e:
            logger.error(f"[FeatureDB] get_feature 失败 ({image_path}): {e}")
            print(f"[ERROR] [FeatureDB] get_feature 失败 ({image_path}): {e}")
            return None

    def get_all_features(self) -> List[Dict[str, Any]]:
        """
        获取数据库内所有图片的特征列表，供后续去重比对
        :return: 特征字典列表
        """
        sql = "SELECT image_path, md5, dhash, phash, quality_score, created_at FROM image_features"
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql)
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"[FeatureDB] get_all_features 失败: {e}")
            print(f"[ERROR] [FeatureDB] get_all_features 失败: {e}")
            return []

    def update_hashes(self, image_path: str, dhash: Optional[str], phash: Optional[str]) -> bool:
        """
        更新特定图片的 pHash/dHash
        :param image_path: 图片相对路径或文件名
        :param dhash: 64位 dHash 字符串
        :param phash: 64位 pHash 字符串
        :return: bool 是否操作成功
        """
        sql = """
        UPDATE image_features
        SET dhash = COALESCE(?, dhash),
            phash = COALESCE(?, phash)
        WHERE image_path = ?
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, (dhash, phash, image_path))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"[FeatureDB] update_hashes 失败 ({image_path}): {e}")
            print(f"[ERROR] [FeatureDB] update_hashes 失败 ({image_path}): {e}")
            return False

    def delete_feature(self, image_path: str) -> bool:
        """
        删除对应记录
        :param image_path: 图片相对路径或文件名
        :return: bool 是否成功删除
        """
        sql = "DELETE FROM image_features WHERE image_path = ?"
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, (image_path,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"[FeatureDB] delete_feature 失败 ({image_path}): {e}")
            print(f"[ERROR] [FeatureDB] delete_feature 失败 ({image_path}): {e}")
            return False
