"""Small geometry-aware joins for meme search, not document layout recovery."""
import unicodedata


def _cjk(ch):
    return bool(ch) and (0x2E80 <= ord(ch) <= 0x9FFF or 0xF900 <= ord(ch) <= 0xFAFF)


def _join(a, b):
    if not a:
        return b
    return a + ('' if _cjk(a[-1]) and _cjk(b[0]) else ' ') + b


def normalize_blocks(texts, boxes):
    """Group aligned character columns first, then horizontal rows. Keep short text."""
    units = []
    for text, box in zip(texts, boxes):
        text = str(text).strip()
        if not text:
            continue
        xs, ys = zip(*box)
        units.append(dict(text=text, x=min(xs), y=min(ys), r=max(xs), b=max(ys)))
    def width(u):return max(1., u['r']-u['x'])
    def height(u):return max(1., u['b']-u['y'])
    singles = [i for i,u in enumerate(units) if len(u['text']) == 1]
    parents = {i:i for i in singles}
    def find(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i
    for n,i in enumerate(singles):
        a=units[i]
        for j in singles[n+1:]:
            b=units[j]
            overlap=max(0., min(a['r'],b['r'])-max(a['x'],b['x']))
            gap=max(a['y'],b['y'])-min(a['b'],b['b'])
            dy=abs((a['y']+a['b']-b['y']-b['b'])/2)
            if (overlap/min(width(a),width(b)) >= .55
                    and .65 <= width(a)/width(b) <= 1.55
                    and .65 <= height(a)/height(b) <= 1.55
                    and dy >= .55*min(height(a),height(b))
                    and gap <= 1.4*max(height(a),height(b))):
                parents[find(j)]=find(i)
    groups={}
    for i in singles:groups.setdefault(find(i),[]).append(i)
    consumed=set()
    combined=[]
    for members in groups.values():
        if len(members)<2:continue
        consumed.update(members)
        col=sorted((units[i] for i in members),key=lambda u:u['y'])
        combined.append(dict(text=''.join(u['text'] for u in col),x=min(u['x'] for u in col),
            y=min(u['y'] for u in col),r=max(u['r'] for u in col),b=max(u['b'] for u in col),column=True))
    combined.extend(u for i,u in enumerate(units) if i not in consumed)
    rows=[]
    for u in sorted(combined,key=lambda u:(u['y'],u['x'])):
        row=next((row for row in rows if abs(row[0]['y']-u['y']) <= .55*min(height(row[0]),height(u))
            or any(v.get('column') and max(0,min(v['b'],u['b'])-max(v['y'],u['y'])) >= .65*min(height(v),height(u)) for v in row)),None)
        if row is None:rows.append([u])
        else:row.append(u)
    result=[]
    for row in rows:
        text=''
        previous=None
        for u in sorted(row,key=lambda u:u['x']):
            # Separate unrelated regions instead of blindly concatenating every box.
            if previous and u['x']-previous['r'] > 2.8*max(height(previous),height(u)):
                result.append(text);text=''
            text=_join(text,u['text'])
            previous=u
        if text:result.append(text)
    return '\n'.join(result)


def merge_frames(texts):
    lines=[];seen=set()
    for text in texts:
        for line in text.splitlines():
            line=line.strip()
            key=''.join(unicodedata.normalize('NFKC',line).split()).casefold()
            if key and key not in seen:
                seen.add(key);lines.append(line)
    return '\n'.join(lines)
