"""Stage A only: render staged SVGs and isolated controls, without a Library.

Run from Source: .venv/Scripts/python.exe tools/render_icon_review.py
No runtime icon bindings, user configuration, or Demo data are changed.
"""
import os
import sys
from pathlib import Path

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QByteArray, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QLabel, QHBoxLayout, QVBoxLayout, QWidget, QSizePolicy
from qfluentwidgets import Theme, setTheme
from fluent_ui import visual
from fluent_ui.icons import Icon
from fluent_ui.components.controls import SplitPushButton, TransparentToolButton
from fluent_ui.components.navigation import SortCycleButton, CompactTitleLabel
from fluent_ui.presentation.glyphs import ClipboardImportIcon

OUT = ROOT / 'docs/assets/icon-review'
NEW = OUT / 'svg'
OLD = ROOT / 'fluent_ui/assets/icons'
ROWS = [
    ('分类树模式', 'list-tree', 'list-tree-stroke-2.25', '实际 14px；原版 2 → 候选 2.25 描边'),
    ('新建分类', 'plus', 'playlist-add-mirrored', '整体水平镜像；加号位于左下'),
    ('导入菜单', 'folder-input', 'mood-plus', '只改右侧菜单触发；剪贴板主按钮保留'),
    ('新建标签', 'plus', 'tag-plus', '同一按钮随标签停靠位置重新安置'),
    ('手动／自定义排序', 'sort-descending', 'menu-order', '分类、标签、资源三个入口统一图标'),
    ('名称 A → Z', 'sort-ascending-letters', 'sort-ascending-letters', '原有 SVG 原样保留；分类／标签状态'),
    ('名称 Z → A', 'sort-descending-letters', 'sort-descending-letters', '原有 SVG 原样保留；分类／标签状态'),
    ('最近添加优先', 'sort-descending-2', 'clock-down', '资源添加时间降序；不是名称排序'),
    ('最早添加优先', 'sort-ascending-2', 'clock-up', '资源添加时间升序；不是名称排序'),
]


def renderer(path, color):
    source = path.read_text(encoding='utf-8').replace('currentColor', color)
    result = QSvgRenderer(QByteArray(source.encode('utf-8')))
    assert result.isValid(), path
    assert result.viewBoxF() == QRectF(0, 0, 24, 24), path
    return result


def svg(p, path, x, y, size, color):
    renderer(path, color).render(p, QRectF(x, y, size, size))


def candidate_icon(name, color):
    # Match Icon.icon(): logical 24px, 2x pixmap; actual controls choose 14/16/18.
    pix = QPixmap(48, 48)
    pix.setDevicePixelRatio(2)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    svg(painter, NEW / f'{name}.svg', 0, 0, 24, color)
    painter.end()
    return QIcon(pix)


def toolbar(kind, proposed, dark):
    """Real project controls, original extents/spacing, illustrative data only."""
    setTheme(Theme.DARK if dark else Theme.LIGHT)
    c = visual.colors(dark)
    host = QWidget()
    host.setFont(visual.font())
    host.resize(460, 92)
    host.setStyleSheet(f'QWidget#preview {{ background: {c["navigation"] if kind == 0 else c["surface"]}; }}')
    host.setObjectName('preview')

    def button(icon, extent, size, x, y=16):
        b = TransparentToolButton(icon, host)
        b.setFixedSize(extent, extent)
        b.setIconSize(QSize(size, size))
        b.move(x, y)
        return b

    def icon(old, new):
        return candidate_icon(new, c['text']) if proposed else old

    if kind == 0:
        # sidebar.py: header margins(2,0,2,2), spacing2, root expands.
        header = QWidget(host)
        header.setGeometry(10, 10, 220, 38)
        row = QHBoxLayout(header)
        row.setContentsMargins(2, 0, 2, 2)
        row.setSpacing(2)
        mode = TransparentToolButton(icon(Icon.MENU, 'list-tree-stroke-2.25'), header)
        mode.setFixedSize(24, 24)
        row.addWidget(mode)
        root = TransparentToolButton(header)
        root.setFixedHeight(36)
        root.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        labels = QVBoxLayout(root)
        labels.setContentsMargins(6, 2, 2, 2)
        labels.setSpacing(0)
        for title, role in [('全部表情', 'body'), ('120', 'data_small')]:
            label = CompactTitleLabel(title, root) if role == 'body' else QLabel(title, root)
            label.setFont(visual.font(role))
            label.setStyleSheet(f'color:{c["text"]}; background:transparent;')
            labels.addWidget(label)
        row.addWidget(root, 1)
        new = TransparentToolButton(icon(Icon.ADD, 'playlist-add-mirrored'), header)
        new.setFixedSize(24, 24)
        row.addWidget(new)
        sort = SortCycleButton('分类显示排序', header)
        if proposed:
            sort.setIcon(candidate_icon('menu-order', c['text']))
        row.addWidget(sort)
    elif kind == 1:
        header = QWidget(host)
        header.setGeometry(10, 12, 440, 32)
        row = QHBoxLayout(header)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        row.addStretch()
        paste = SplitPushButton(ClipboardImportIcon(), '', header)
        paste.button.ghost = True
        paste.button.setFixedSize(32, 32)
        paste.button.setIconSize(QSize(18, 18))
        paste.dropButton.setIcon(icon(Icon.IMPORT, 'mood-plus'))
        paste.dropButton.setFixedSize(32, 32)
        paste.dropButton.setIconSize(QSize(18, 18))
        paste.layout().setSpacing(4)
        row.addWidget(paste)
        for old, new in [(Icon.MANAGE, None), (Icon.SORT, 'menu-order')]:
            b = TransparentToolButton(icon(old, new) if new else old, header)
            b.setFixedSize(32, 32)
            b.setIconSize(QSize(18, 18))
            row.addWidget(b)
    else:
        # Tag sort stays in header; new lives in the axis strip, not beside sort.
        title = QLabel('标签', host)
        title.setFont(visual.font())
        title.setStyleSheet(f'color:{c["text"]}; background:transparent;')
        title.move(12, 16)
        sort = SortCycleButton('标签显示排序', host)
        sort.move(422, 10)
        if proposed:
            sort.setIcon(candidate_icon('menu-order', c['text']))
        tag = QLabel('示例标签', host)
        tag.setFont(visual.font())
        tag.setStyleSheet(f'color:{c["text_secondary"]}; background:transparent;')
        tag.move(12, 52)
        button(icon(Icon.ADD, 'tag-plus'), 20, 14, 426, 48)
    host.ensurePolished()
    for layout in host.findChildren(QHBoxLayout) + host.findChildren(QVBoxLayout):
        layout.activate()
    host.show()
    QApplication.processEvents()
    for child in host.findChildren(QWidget):
        child.clearFocus()
    pix = host.grab()
    host.hide()
    assert pix.width() == 460 and pix.height() == 92
    return pix


def main():
    app = QApplication.instance() or QApplication([])
    visual.load_fonts()
    image = QImage(1560, 1840, QImage.Format_ARGB32_Premultiplied)
    image.fill(QColor('#f2f2ec'))
    p = QPainter(image)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.TextAntialiasing)
    light = visual.colors(False)
    dark = visual.colors(True)

    def text(x, y, value, size=14, color=None, bold=False):
        font = visual.font()
        font.setPixelSize(size)
        font.setBold(bold)
        p.setFont(font)
        p.setPen(QColor(color or light['text']))
        p.drawText(x, y, value)

    def line(y):
        p.setPen(QPen(QColor(light['border_soft']), 1))
        p.drawLine(32, y, 1528, y)

    text(32, 42, 'Nekori  /  图标视觉确认', 26, bold=True)
    text(32, 70, '阶段 A · 真实 SVG / 未修改程序绑定 · 基线 48254b1 · 浅色实际色板 + 深色透明描边', 14)
    text(32, 95, 'Tabler Outline；树图标 2.25 为线宽候选，其余目标 2。图形按标注像素原尺寸绘制，无固定宽度上限或底色遮盖。', 13)
    columns = [44, 300, 505, 620, 735, 850, 960]
    for x, label in zip(columns, ['功能', '当前 24px', '候选 24px', '20px', '16px', '深底 20px', '绑定 / 尺寸说明']):
        text(x, 132, label, 14, bold=True)
    line(146)
    for i, (label, old, new, note) in enumerate(ROWS):
        y = 148 + i * 63
        text(44, y + 26, label, 15, bold=True)
        text(44, y + 47, new, 11, light['text_muted'])
        svg(p, OLD / f'{old}.svg', 327, y + 18, 24, light['text'])
        for x, size in [(525, 24), (635, 20), (747, 16)]:
            svg(p, NEW / f'{new}.svg', x, y + (60 - size) / 2, size, light['text'])
        p.fillRect(QRectF(846, y + 5, 90, 50), QColor(dark['surface']))
        svg(p, NEW / f'{new}.svg', 881, y + 20, 20, dark['text'])
        text(960, y + 26, note, 13)
        text(960, y + 47, f'当前：{old}', 11, light['text_muted'])
        line(y + 62)

    text(32, 754, '放大核对 · 几何与方向', 20, bold=True)
    details = [
        ('分类树：原资源与上游路径相同；仅比较描边', [(OLD/'list-tree.svg', '当前 2'), (NEW/'list-tree.svg', 'Tabler 原始 2'), (NEW/'list-tree-stroke-2.25.svg', '候选 2.25')]),
        ('新建分类：整组水平镜像，左下加号', [(NEW/'playlist-add.svg', '原始 playlist-add'), (NEW/'playlist-add-mirrored.svg', '完整水平镜像')]),
        ('手动排序：旧单向箭头 → 双向调整', [(OLD/'sort-descending.svg', '当前'), (NEW/'menu-order.svg', 'menu-order')]),
        ('时间状态：最近 / 最早，不更改排序语义', [(NEW/'clock-down.svg', 'clock-down · 最近'), (NEW/'clock-up.svg', 'clock-up · 最早')]),
    ]
    for i, (title, icons) in enumerate(details):
        x = 32 + (i % 2) * 764
        y = 778 + (i // 2) * 156
        text(x, y + 12, title, 14, bold=True)
        for j, (path, label) in enumerate(icons):
            xx = x + 25 + j * 220
            svg(p, path, xx, y + 29, 64, light['text'])
            if i == 0:
                svg(p, path, xx + 82, y + 54, 14, light['text'])
            text(xx, y + 116, label, 12)
        if i == 0:
            text(x, y + 139, '大图 64px；右侧小图 14px = 当前树模式按钮实际渲染尺寸', 12, light['text_muted'])

    line(1095)
    text(32, 1127, '原布局工具栏模拟 · 使用项目真实 Qt 控件 / 不连接 Library', 20, bold=True)
    text(32, 1150, '下方均为 1:1 逻辑像素；未改按钮大小、图标框或间距。宽度为对照画布，非新界面布局。', 13)
    names = ['左侧分类栏 · 24px 按钮 / 14、16px 图标', '右上资源栏 · 32px 按钮 / 18px 图标', '底部标签区 · 排序 24/16px、新建 20/14px']
    for kind, title in enumerate(names):
        x = 44 + kind * 500
        text(x, 1186, title, 13, bold=True)
        for j, (proposed, is_dark, label) in enumerate([(False, False, '当前 · 浅色'), (True, False, '候选 · 浅色'), (True, True, '候选 · 深色')]):
            y = 1214 + j * 128
            text(x, y, label, 12, light['text_muted'])
            p.drawPixmap(x, y + 10, toolbar(kind, proposed, is_dark))
    line(1610)
    text(32, 1645, '尺寸核查与待确认项', 19, bold=True)
    for i, label in enumerate([
        '树模式当前仅 14px：2 → 2.25 描边约从 1.17px 变为 1.31px；候选只作用于该控件，不全局修改 MENU。',
        '16px：clock 箭头及 tag-plus 角标较密；20px 更易辨认。工具栏仍保留现有 14 / 16 / 18px，不擅自放大按钮。',
        '分类 / 标签排序共用 SortCycleButton；资源按钮独立映射。A→Z、Z→A 直接复用本地原 SVG。',
        '剪贴板主按钮、管理按钮、图标模式 layout-grid、所有无图标右键项均保留；本图不代表已实装或已验收。',
        '确认后才进入阶段 B：引入已选 SVG 与局部语义绑定，不改变排序、导入、停靠及分类创建逻辑。',
    ]):
        text(32, 1677 + i * 29, label, 14)
    p.end()
    output = OUT / 'icon-comparison.png'
    assert image.save(str(output)), output
    # Ensure every staged file is a valid transparent stroked SVG.
    for path in NEW.glob('*.svg'):
        renderer(path, '#222720')
        source = path.read_text(encoding='utf-8')
        assert 'fill="none"' in source and 'currentColor' in source
    assert (NEW/'sort-ascending-letters.svg').read_bytes() == (OLD/'sort-ascending-letters.svg').read_bytes()
    assert (NEW/'sort-descending-letters.svg').read_bytes() == (OLD/'sort-descending-letters.svg').read_bytes()
    print(f'{output}\n1560x1840; 11 valid SVGs; unchanged AZ/ZA; offscreen controls only')


if __name__ == '__main__':
    main()
