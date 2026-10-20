"""ธีมและองค์ประกอบหน้าตาของเว็บ — แก้สีได้ที่ตัวแปรใน :root"""
import base64
import re

import streamlit as st

# ถังขยะ 4 สีของไทย: (สี, ประเภท, ตัวอย่าง, สีพื้น, สีตัวอักษร)
BINS = [
    ("เขียว", "ขยะเปียก", "เศษอาหาร เปลือกผลไม้", "#2F8F5B", "#FFFFFF"),
    ("เหลือง", "รีไซเคิล", "ขวด กระดาษ แก้ว กระป๋อง", "#E8B923", "#2B2200"),
    ("น้ำเงิน", "ขยะทั่วไป", "ซองขนม โฟมเปื้อน", "#2E6DB4", "#FFFFFF"),
    ("แดง", "ขยะอันตราย", "ถ่านไฟฉาย หลอดไฟ สเปรย์", "#CC4B3C", "#FFFFFF"),
]

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Thai:wght@400;500;600&family=Prompt:wght@500;600;700&display=swap');
:root{--ink:#14281E;--forest:#12372A;--leaf:#2E7D4F;--paper:#F3F6F4;--line:#D5DED8;--soft:#E6EEE9;}
html,body,.stApp,.stMarkdown,p,label,button,input,textarea,li{font-family:'Noto Sans Thai',sans-serif;}
h1,h2,h3,.hero-title,.brand{font-family:'Prompt','Noto Sans Thai',sans-serif;letter-spacing:0;}
.block-container{max-width:820px;padding-top:1.6rem;padding-bottom:7rem;}
footer,[data-testid="stDecoration"]{display:none;}
[data-testid="stHeader"]{background:transparent;}

/* ---------- หัวเว็บ: บล็อกสีเขียวเข้ม + แถบถัง 4 สี ---------- */
.hero{background:var(--forest);color:#fff;border-radius:14px 14px 0 0;padding:1.7rem 1.8rem 1.5rem;}
.hero-title{font-size:clamp(1.9rem,5vw,2.7rem);font-weight:700;line-height:1.15;}
.hero-sub{margin-top:.5rem;max-width:34rem;font-size:1.02rem;line-height:1.6;color:#CFE5D8;}
.bins{display:grid;grid-template-columns:repeat(4,1fr);border-radius:0 0 14px 14px;overflow:hidden;margin-bottom:1.2rem;}
.bin{background:var(--c);color:var(--t);padding:.75rem .9rem .85rem;}
.bin b{display:block;font-family:'Prompt',sans-serif;font-weight:600;font-size:.98rem;}
.bin span{display:block;font-size:.8rem;line-height:1.35;margin-top:.1rem;opacity:.92;}
.hero.compact{border-radius:14px;padding:.8rem 1.2rem;margin-bottom:1rem;}
.hero.compact .hero-title{font-size:1.35rem;}
.hero.compact .hero-sub,.hero.compact + .bins{display:none;}
@media(max-width:640px){.bins{grid-template-columns:repeat(2,1fr);}.hero{padding:1.3rem 1.2rem;}}

/* ---------- การ์ดสีถังในคำตอบ ---------- */
.bincards{display:flex;flex-wrap:wrap;gap:.6rem;margin:.1rem 0 .9rem;}
.bincard{display:flex;align-items:center;gap:.85rem;background:var(--c);color:var(--t);
  border-radius:12px;padding:.6rem 1.1rem .6rem .8rem;flex:1 1 15rem;}
.bincard img{width:46px;height:auto;flex:none;}
.bincard-title{font-family:'Prompt',sans-serif;font-weight:600;font-size:1.15rem;line-height:1.2;}
.bincard-sub{font-size:.85rem;line-height:1.35;margin-top:.15rem;opacity:.95;}

.try-title{font-family:'Prompt',sans-serif;font-weight:600;font-size:1.05rem;margin:.2rem 0 .6rem;color:var(--forest);}

/* ---------- ปุ่มคำถามตัวอย่าง ---------- */
.st-key-examples button{min-height:3.1rem;height:auto;justify-content:flex-start;text-align:left;
  background:#fff;border:1.5px solid var(--line);border-radius:10px;padding:.65rem .9rem;color:var(--ink);}
.st-key-examples button p{text-align:left;font-size:.95rem;}
.st-key-examples button:hover{border-color:var(--leaf);color:var(--forest);background:#F7FBF8;}

/* ---------- แชท ---------- */
[data-testid="stChatMessage"]{background:#fff;border:1px solid var(--line);border-left:4px solid var(--leaf);
  border-radius:4px 14px 14px 14px;padding:1rem 1.15rem;margin-bottom:.55rem;line-height:1.75;}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]){background:var(--soft);
  border-color:var(--soft);border-left-color:var(--forest);}
[data-testid="stChatInput"]{border-radius:14px;border:1.5px solid var(--leaf);background:#fff;}
[data-testid="stExpander"]{background:#fff;border:1px solid var(--line);border-radius:10px;}
[data-testid="stExpander"] summary{font-weight:500;}

/* ---------- การ์ดจุดรับขยะ ---------- */
.place{background:#fff;border:1px solid var(--line);border-left:4px solid var(--leaf);
  border-radius:4px 12px 12px 4px;padding:.8rem 1rem;margin-bottom:.6rem;line-height:1.65;font-size:.95rem;}
.place-name{font-family:'Prompt',sans-serif;font-weight:600;font-size:1.05rem;display:inline;margin-right:.5rem;}
.tag{display:inline-block;background:var(--soft);color:var(--forest);border-radius:6px;padding:.05rem .5rem;font-size:.8rem;}
.tag-dist{background:var(--forest);color:#fff;margin-left:.35rem;}
.place-links{margin-top:.35rem;}
.place-links a{margin-right:1.2rem;font-weight:500;color:var(--leaf);}
.place-meta{margin-top:.3rem;font-size:.8rem;color:#5B6B61;}

/* ---------- แถบด้านข้าง ---------- */
[data-testid="stSidebar"]{border-right:1px solid var(--line);}
.brand{font-size:1.45rem;font-weight:700;color:var(--forest);margin:.1rem 0 .8rem;}
[data-testid="stSidebar"] .stButton button{justify-content:flex-start;text-align:left;border-radius:8px;
  border:1px solid transparent;background:transparent;color:var(--ink);padding:.45rem .7rem;}
[data-testid="stSidebar"] .stButton button:hover{background:#fff;border-color:var(--line);}
[data-testid="stSidebar"] .stButton button[kind="primary"]{background:#fff;border-color:var(--leaf);
  border-left:4px solid var(--leaf);font-weight:600;}
.st-key-newchat button{justify-content:center!important;background:var(--forest)!important;
  color:#fff!important;font-weight:600;border-color:var(--forest)!important;}
.st-key-newchat button p{color:#fff;}
.st-key-newchat button:hover{background:var(--leaf)!important;}

/* ---------- หน้า Admin ---------- */
button[data-baseweb="tab"]{font-weight:500;}
[data-testid="stMetric"]{background:#fff;border:1px solid var(--line);border-radius:10px;padding:.8rem 1rem;}
:focus-visible{outline:2px solid var(--leaf);outline-offset:2px;}
"""


def inject_css():
    st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)


def hero(compact: bool = False):
    bins = "".join(
        f'<div class="bin" style="--c:{c};--t:{t}"><b>ถัง{name}</b><span>{kind} {ex}</span></div>'
        for name, kind, ex, c, t in BINS
    )
    st.markdown(
        f'<div class="hero{" compact" if compact else ""}">'
        '<div class="hero-title">น้องรีไซเคิล</div>'
        '<div class="hero-sub">ถามวิธีคัดแยกขยะ หรือแนบภาพขยะให้ช่วยดูว่าควรทิ้งถังไหน '
        'ทุกคำตอบมีแหล่งอ้างอิงให้ตรวจสอบ</div></div>'
        f'<div class="bins">{bins}</div>',
        unsafe_allow_html=True,
    )


_BIN_BY_NAME = {b[0]: b for b in BINS}


def _darken(hex_color: str, k: float = 0.72) -> str:
    h = hex_color.lstrip("#")
    r, g, b = (int(int(h[i:i + 2], 16) * k) for i in (0, 2, 4))
    return f"#{r:02x}{g:02x}{b:02x}"


def bin_image(color: str) -> str:
    """ภาพถังขยะ SVG (ฝังเป็น data URI) ตามสีที่ระบุ"""
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 78">'
        f'<rect x="21" y="3" width="22" height="7" rx="3.5" fill="{_darken(color, .6)}"/>'
        f'<rect x="5" y="9" width="54" height="12" rx="4" fill="{_darken(color)}"/>'
        f'<path d="M10 24H54L50.5 71Q50.3 75 46.5 75H17.5Q13.7 75 13.5 71Z" fill="{color}"/>'
        '<rect x="23" y="31" width="3.5" height="37" rx="1.7" fill="#fff" opacity=".4"/>'
        '<rect x="30.2" y="31" width="3.5" height="37" rx="1.7" fill="#fff" opacity=".4"/>'
        '<rect x="37.5" y="31" width="3.5" height="37" rx="1.7" fill="#fff" opacity=".4"/>'
        '</svg>'
    )
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


_BIN_LINE = re.compile(r"^[ \t>*_`#\[\-]*BIN[ \t]*[:：][ \t]*(.*?)[ \t*_`\]]*$", re.I | re.M)
_PARTIAL_BIN = re.compile(r"^[ \t>*_`#\[\-]*(?:B(?:I(?:N(?:[ \t]*[:：].*)?)?)?)?$", re.I)
_ALIASES = {"yellow": "เหลือง", "red": "แดง", "green": "เขียว", "blue": "น้ำเงิน"}


def split_bins(text: str):
    """แยกบรรทัด 'BIN: สี' ที่ LLM ใส่ไว้ -> (รายชื่อสี, ข้อความที่เหลือ)
    รองรับหลายสี (เหลือง, แดง / สีเหลือง และ แดง) ตัวหนา/ตัวพิมพ์เล็ก และบรรทัดที่ไม่ได้อยู่บรรทัดแรก
    ถ้าไม่มีบรรทัดนี้ (เช่นแชทเก่า) และคำตอบพูดถึงถังสีเดียวอย่างชัดเจน จะใช้สีนั้นแทน"""
    matches = list(_BIN_LINE.finditer(text))
    if matches:
        spec = " ".join(m.group(1) for m in matches).lower()
        for en, th in _ALIASES.items():
            spec = spec.replace(en, th)
        names = sorted((n for n in _BIN_BY_NAME if n in spec), key=spec.index)
        rest = _BIN_LINE.sub("", text)
        return names, re.sub(r"\n{3,}", "\n\n", rest).strip()
    found = set(re.findall(r"ถัง(?:สี)?(เขียว|เหลือง|น้ำเงิน|แดง)", text))
    return (list(found) if len(found) == 1 else []), text


def strip_partial_bin(text: str) -> str:
    """ระหว่างสตรีม: ซ่อนบรรทัดท้ายสุดที่ยังพิมพ์ไม่จบและอาจเป็นบรรทัด BIN (กันเห็นข้อความดิบกะพริบ)"""
    head, _, last = text.rpartition("\n")
    if last.strip() and _PARTIAL_BIN.match(last):
        return head
    return text


def bin_cards(names):
    if not names:
        return
    cards = "".join(
        f'<div class="bincard" style="--c:{c};--t:{t}">'
        f'<img src="{bin_image(c)}" alt="ถังขยะสี{name}">'
        f'<div><div class="bincard-title">ทิ้งถังสี{name}</div>'
        f'<div class="bincard-sub">{kind}: {ex}</div></div></div>'
        for name, kind, ex, c, t in (_BIN_BY_NAME[n] for n in names)
    )
    st.markdown(f'<div class="bincards">{cards}</div>', unsafe_allow_html=True)


def place_card_html(p) -> str:
    """การ์ด HTML ของจุดรับขยะหนึ่งแห่ง พร้อมลิงก์ Google Maps และนำทาง"""
    import html

    from places import directions_url, format_km, maps_url
    e = html.escape
    rows = "".join(
        f"<div><b>{label}:</b> {e(p[key])}</div>"
        for label, key in (("ที่อยู่", "address"), ("เวลาทำการ", "hours"), ("รับ", "accepts"), ("โทร", "phone"))
        if p.get(key)
    )
    meta = " ".join(x for x in (
        f"ตรวจสอบเมื่อ {e(p['verified'])}" if p.get("verified") else "",
        f"แหล่งที่มา {e(p['source'])}" if p.get("source") else "") if x)
    return (
        '<div class="place">'
        f'<span class="place-name">{e(p["name"])}</span><span class="tag">{e(p["type"])}</span>'
        + (f'<span class="tag tag-dist">ห่างประมาณ {format_km(p["_km"])}</span>' if p.get("_km") is not None else "")
        + f'{rows}'
        f'<div class="place-links"><a href="{maps_url(p)}" target="_blank" rel="noopener">เปิดใน Google Maps</a>'
        f'<a href="{directions_url(p)}" target="_blank" rel="noopener">นำทาง</a></div>'
        + (f'<div class="place-meta">{meta}</div>' if meta else "")
        + '</div>'
    )
