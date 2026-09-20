"""Deterministic, authored OCR fixtures. No user assets or bundled font files.

Ground truth and queries are fixed here before running any OCR candidate.
Usage: python scripts/p4/make_samples.py <new-output-directory>
"""
import hashlib
import json
from pathlib import Path
import random
import sys

from PIL import Image, ImageDraw, ImageFont, ImageFilter


FONTS = Path('C:/Windows/Fonts')
PHRASES = {
    'zh-Hans': [('你怎么睡得着的', ['睡得着']), ('今天也要开心呀', ['开心']),
                ('我先躺一会儿', ['躺一会']), ('终于下班了', ['下班'])],
    'zh-Hant': [('今天也要開心呀', ['開心']), ('這次真的後悔了', ['後悔']),
                ('謝謝你的陪伴', ['陪伴']), ('晚安，明天見', ['明天見'])],
    'en': [('NOT TODAY', ['today']), ('Keep calm and carry on', ['keep calm']),
           ('Sorry, I am busy!', ['busy']), ('GOOD NIGHT', ['good night'])],
    'ja': [('もうダメだ', ['ダメ']), ('おやすみなさい', ['おやすみ']),
           ('本当にありがとう', ['ありがとう']), ('猫と一緒に休もう', ['一緒'])],
    'mixed': [('草 www', ['草', 'www']), ('笨蛋 baka!', ['笨蛋', 'baka']),
              ('もうダメ了', ['ダメ', '了']), ('今日も HAPPY 開心', ['今日', 'happy', '開心'])],
}
STYLES = ['plain', 'outline', 'low_resolution', 'small_text', 'busy_background', 'tilted']


def card(text, language='zh-Hans', style='plain', seed=0):
    rng = random.Random(seed)
    size = (640, 360)
    font_size = 43 if language != 'en' else 35
    if style == 'low_resolution':
        size, font_size = (200, 120), 14 if language != 'en' else 11
    elif style == 'small_text':
        size, font_size = (960, 600), 19
    bg = (240, 228, 255) if style in ('outline', 'tilted') else (250, 247, 239)
    image = Image.new('RGB', size, bg)
    draw = ImageDraw.Draw(image)
    width, height = size
    if style == 'busy_background':
        for _ in range(100):
            x, y = rng.randrange(width), rng.randrange(height)
            r = rng.randrange(4, 65)
            color = tuple(rng.randrange(85, 245) for _ in range(3))
            draw.ellipse((x-r, y-r, x+r, y+r), fill=color)
    # Original geometric cat illustration, kept clear of the text row.
    cx, cy, r = width//2, height//2, height//5
    draw.polygon([(cx-r, cy), (cx-r, cy-r*1.4), (cx-r//2, cy-r//2)], fill='#f4ad85')
    draw.polygon([(cx+r, cy), (cx+r, cy-r*1.4), (cx+r//2, cy-r//2)], fill='#f4ad85')
    draw.ellipse((cx-r, cy-r, cx+r, cy+r), fill='#f4ad85', outline='#56433d', width=2)
    for eye in (-1, 1):
        x = cx+eye*r//3
        draw.ellipse((x-3, cy-5, x+3, cy+2), fill='#453630')
    draw.arc((cx-12, cy-1, cx+12, cy+16), 0, 180, fill='#453630', width=2)
    if not text:
        return image
    font_name = 'YuGothM.ttc' if language == 'ja' else 'msyh.ttc'
    if style == 'outline' and language != 'ja':
        font_name = 'msyhbd.ttc'
    font = ImageFont.truetype(str(FONTS/font_name), font_size)
    layer = Image.new('RGBA', size)
    layer_draw = ImageDraw.Draw(layer)
    bbox = layer_draw.textbbox((0, 0), text, font=font)
    x = max(2, (width-(bbox[2]-bbox[0]))//2)
    y = height-font_size*2-bbox[1]
    outlined = style in ('outline', 'busy_background')
    layer_draw.text((x, y), text, font=font,
                    fill='#ffffff' if outlined else '#181522',
                    stroke_width=max(1, font_size//15) if outlined else 0,
                    stroke_fill='#673587')
    if style == 'tilted':
        layer = layer.rotate(13, Image.Resampling.BICUBIC, expand=False)
    image = Image.alpha_composite(image.convert('RGBA'), layer).convert('RGB')
    if style == 'low_resolution':
        image = image.filter(ImageFilter.GaussianBlur(0.35))
    return image


def generate(root):
    root.mkdir(parents=True, exist_ok=False)
    records = []

    def register(name, image, text, queries, language, strata, **save):
        path = root/name
        image.save(path, **save)
        records.append(dict(id=path.stem, file=name, language=language, strata=strata,
                            expected=text, queries=queries,
                            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                            bytes=path.stat().st_size))

    for language, phrases in PHRASES.items():
        for index, style in enumerate(STYLES):
            text, queries = phrases[index % len(phrases)]
            name = f'{language}-{style}.jpg' if style == 'low_resolution' else f'{language}-{style}.png'
            register(name, card(text, language, style, index), text, queries, language, [style],
                     **({'quality': 35} if style == 'low_resolution' else {}))
    for language, text, query in [('zh-Hans', '你先冷静一下', '冷静'),
                                  ('zh-Hant', '開心最重要', '開心'),
                                  ('ja', '今日も元気', '元気')]:
        image = Image.new('RGB', (260, 480), '#f4eaff')
        font = ImageFont.truetype(str(FONTS/('YuGothM.ttc' if language == 'ja' else 'simsun.ttc')), 42)
        draw = ImageDraw.Draw(image)
        for i, char in enumerate(text):
            draw.text((105, 26+i*58), char, font=font, fill='#20202f')
        register(f'{language}-vertical.png', image, text, [query], language, ['vertical', 'serif'])
    for index, (language, text, queries) in enumerate([
            ('ja', 'わくわく ドキドキ', ['わくわく', 'ドキドキ']),
            ('zh-Hans', '哈哈哈哈 救命啊', ['哈哈', '救命']),
            ('mixed', 'OK！收到啦 ありがとう', ['ok', '收到', 'ありがとう'])]):
        register(f'onomatopoeia-{index}.png', card(text, language, 'outline'), text,
                 queries, language, ['onomatopoeia', 'outline'])
    for style in ('plain', 'busy_background', 'outline'):
        register(f'no-text-{style}.png', card('', style=style), '', [], 'none', ['no_text', style])
    register('large-static.png', card('晚安，明天見', 'zh-Hant').resize((3600, 2025)),
             '晚安，明天見', ['明天見'], 'zh-Hant', ['large'])

    animations = [
        ('gif-late', ['', '', '', '', '', '', '终于下班了', '终于下班了', '终于下班了', '终于下班了', '终于下班了', '终于下班了'],
         ['下班'], 'zh-Hans', (640, 360), 180),
        ('gif-changing', ['在吗']*4+['等一下']*4+['收到']*4,
         ['在吗', '等一下', '收到'], 'zh-Hans', (640, 360), 160),
        ('gif-japanese', ['']*4+['おやすみなさい']*4+['ありがとう']*4,
         ['おやすみ', 'ありがとう'], 'ja', (640, 360), 160),
        ('gif-brief', ['']*5+['救命啊']+['']*6,
         ['救命'], 'zh-Hans', (640, 360), 100),
        ('gif-large', ['']*40+['终于下班了']*40,
         ['下班'], 'zh-Hans', (1600, 900), 100),
    ]
    for name, texts, queries, language, size, duration in animations:
        frames = []
        for index, text in enumerate(texts):
            frame = card(text, language).resize(size)
            # Motion prevents the GIF encoder coalescing equal adjacent frames.
            ImageDraw.Draw(frame).rectangle((index*7 % size[0], 5, index*7 % size[0]+4, 12), fill='red')
            frames.append(frame)
        expected = '\n'.join(dict.fromkeys(text for text in texts if text))
        register(name+'.gif', frames[0], expected, queries, language, ['gif', name],
                 save_all=True, append_images=frames[1:], duration=duration, loop=0, disposal=2)
    bad = root/'damaged.gif'
    bad.write_bytes(b'GIF89a\x80\x02\x68\x01broken-fixture')
    records.append(dict(id='damaged', file=bad.name, language='none', strata=['damaged'],
                        expected='', queries=[], expected_error=True,
                        sha256=hashlib.sha256(bad.read_bytes()).hexdigest(), bytes=bad.stat().st_size))
    manifest = dict(source='Deterministic original geometric illustrations and authored text; no user assets.',
                    fonts=[dict(name=name, sha256=hashlib.sha256((FONTS/name).read_bytes()).hexdigest())
                           for name in ('msyh.ttc', 'msyhbd.ttc', 'YuGothM.ttc', 'simsun.ttc')],
                    font_distribution='Only rendered fixtures; font files are not redistributed.',
                    records=records)
    (root/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'samples': len(records), 'queries': sum(len(r['queries']) for r in records),
                      'bytes': sum(r['bytes'] for r in records)}, ensure_ascii=False))


if __name__ == '__main__':
    generate(Path(sys.argv[1]).resolve())
