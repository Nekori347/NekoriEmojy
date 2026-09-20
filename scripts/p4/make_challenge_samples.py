"""Additional difficult strata, scored separately from the first fixed set.

The first set uses standard fonts. This set adds hollow/art fonts, handwriting,
colored/curved text and explicit resource-limit failures. Queries are fixed
before any candidate runs on this additional set; earlier cases are unchanged.
"""
import hashlib
import json
from pathlib import Path
import sys

from PIL import Image, ImageDraw, ImageFont, ImageFilter

from make_samples import FONTS, card


def main(root):
    root.mkdir(parents=True, exist_ok=False)
    records = []

    def save(name, image, text, queries, lang, strata, expected_error=False, **options):
        path = root/name
        image.save(path, **options)
        records.append(dict(id=path.stem, file=name, expected=text, queries=queries,
                            language=lang, strata=strata, expected_error=expected_error,
                            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                            bytes=path.stat().st_size))

    specs = [
        ('hollow', '怎么又是我', ['又是我'], 'zh-Hans', 'STCAIYUN.TTF'),
        ('art-bold', '開心最重要', ['開心'], 'zh-Hant', 'STHUPO.TTF'),
        ('calligraphy', '别急慢慢来', ['慢慢来'], 'zh-Hans', 'STXINGKA.TTF'),
        ('rainbow-en', 'NO PROBLEM', ['problem'], 'en', 'msyhbd.ttc'),
        ('rainbow-mixed', '草www 真的吗', ['真的吗', 'www'], 'mixed', 'msyhbd.ttc'),
        ('curved-ja', 'そんなバカな', ['バカ'], 'ja', 'YuGothM.ttc'),
        ('small-color-ja', 'まだ大丈夫', ['大丈夫'], 'ja', 'YuGothM.ttc'),
        ('low-contrast', '這樣也可以', ['這樣'], 'zh-Hant', 'msyh.ttc'),
        ('angled-en', 'TAKE A BREAK', ['break'], 'en', 'msyhbd.ttc'),
        ('soft-mixed', 'えっ？我不理解', ['理解', 'えっ'], 'mixed', 'msyhbd.ttc'),
    ]
    for name, text, queries, language, font_name in specs:
        image = card('', style='busy_background' if name == 'soft-mixed' else 'plain')
        layer = Image.new('RGBA', image.size)
        draw = ImageDraw.Draw(layer)
        size = 22 if name == 'small-color-ja' else (48 if language != 'en' else 39)
        font = ImageFont.truetype(str(FONTS/font_name), size)
        length = draw.textlength(text, font=font)
        x = (640-length)/2
        colors = ('#aa2468', '#107bad', '#b86500', '#168451')
        for index, char in enumerate(text):
            y = 260 + ([0, -9, -15, -9, 0, 8, 12][index % 7] if name == 'curved-ja' else 0)
            color = '#d4d0c8' if name == 'low-contrast' else colors[index % len(colors)]
            draw.text((x, y), char, font=font, fill=color)
            x += draw.textlength(char, font=font)
        if name == 'angled-en':
            layer = layer.rotate(25, Image.Resampling.BICUBIC)
        image = Image.alpha_composite(image.convert('RGBA'), layer).convert('RGB')
        if name == 'soft-mixed':
            image = image.resize((220, 124)).filter(ImageFilter.GaussianBlur(.6))
        save(name+'.png', image, text, queries, language, ['challenge', name])

    moving = []
    for index in range(18):
        # Whole-background animation competes with a short-lived text change.
        image = card('别眨眼' if 7 <= index <= 8 else '', style='busy_background', seed=index)
        moving.append(image)
    save('gif-moving.gif', moving[0], '别眨眼', ['眨眼'], 'zh-Hans', ['gif', 'challenge', 'moving_background'],
         save_all=True, append_images=moving[1:], duration=100, loop=0, disposal=2)
    long_frames = []
    for index in range(100):
        image = card('最后才出现' if index >= 90 else '').resize((1600, 900)).convert('P', palette=Image.Palette.ADAPTIVE)
        ImageDraw.Draw(image).rectangle((index*7, 2, index*7+4, 9), fill=0)
        long_frames.append(image)
    save('gif-after-bound.gif', long_frames[0], '最后才出现', ['最后'], 'zh-Hans',
         ['gif', 'challenge', 'late_beyond_scan_budget'], save_all=True,
         append_images=long_frames[1:], duration=100, loop=0, disposal=2)
    save('oversized.png', Image.new('RGB', (5100, 3400), 'white'), '', [], 'none',
         ['challenge', 'over_pixel_limit'], expected_error=True)
    manifest = dict(source='Additional authored challenge fixtures; standard set and its queries unchanged.',
                    fonts=[dict(name=name, sha256=hashlib.sha256((FONTS/name).read_bytes()).hexdigest())
                           for name in sorted({s[4] for s in specs})],
                    font_distribution='Rendered output only; no redistribution of font files.', records=records)
    (root/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(len(records), 'challenge fixtures;', sum(len(r['queries']) for r in records), 'queries')


if __name__ == '__main__':
    main(Path(sys.argv[1]).resolve())
