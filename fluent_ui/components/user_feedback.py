"""Explicit user actions only: open the public form or copy a small environment summary."""
import json
import math
import platform
import sys

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication

from services.i18n import i18n_engine, t
from services.update_service import current_version, install_root
from services.version_info import version_info
from fluent_ui.components.feedback import feedback_for


FEEDBACK_URL = 'https://github.com/Nekori347/NekoriEmojy/issues/new/choose'


def open_feedback(owner):
    if QDesktopServices.openUrl(QUrl(FEEDBACK_URL)):
        return True
    QApplication.clipboard().setText(FEEDBACK_URL)
    feedback_for(owner.window()).notice(
        t('反馈与建议'), t('无法打开浏览器，已复制反馈链接'), warning=True)
    return False


def environment_text(owner):
    root = install_root()
    version = current_version(root)
    lines = ['NekoriEmojy: '+version] if version != 'unknown' else []
    try:
        metadata = json.loads((root/'version.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        metadata = {}
    # version_info supplies a development fallback for other UI callers.
    # Copy only a channel actually declared in the release metadata.
    channel = metadata.get('channel')
    if channel:
        lines.append('Channel: '+str(channel))
    if sys.platform == 'win32':
        lines.append('Windows: '+platform.release()+' ('+platform.version()+')')
    lines.append('UI language: '+i18n_engine.current_lang)
    scale = owner.window().devicePixelRatioF()
    if math.isfinite(scale) and scale > 0:
        lines.append(f'Display scale: {scale*100:g}%')
    if not (getattr(sys, 'frozen', False) or globals().get('__compiled__')) and (root/'.git').exists():
        try:
            commit = version_info().get('commit')
        except (OSError, ValueError):
            commit = ''
        if commit:
            lines.append('Development commit: '+commit)
    return '\n'.join(lines)


def copy_environment_info(owner):
    QApplication.clipboard().setText(environment_text(owner))
    feedback_for(owner.window()).toast(t('已复制环境信息'), kind='success')
