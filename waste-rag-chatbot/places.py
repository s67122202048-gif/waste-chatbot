"""จุดรับขยะ (ธนาคารขยะ / ขยะอันตราย / ขยะอิเล็กทรอนิกส์ / น้ำมันพืชใช้แล้ว)
อ่าน-เขียนไฟล์ locations/points.csv และสร้างลิงก์ Google Maps (ไม่ต้องใช้ API key)"""
import csv
import io
import math
from pathlib import Path
from urllib.parse import quote_plus

import storage

PLACES_FILE = storage.PLACES_FILE
FIELDS = ["name", "type", "address", "lat", "lng", "hours", "accepts", "phone", "source", "verified"]
TYPES = ["ขยะอันตราย", "ขยะอิเล็กทรอนิกส์", "ธนาคารขยะ/รีไซเคิล", "น้ำมันพืชใช้แล้ว", "อื่น ๆ"]

# คำในคำตอบของบอท -> ประเภทจุดรับที่ควรแสดง
_KEYWORDS = {
    "ขยะอันตราย": ["ขยะอันตราย", "ถ่านไฟฉาย", "ถ่านชาร์จ", "แบตเตอรี่", "หลอดไฟ", "หลอดฟลูออเรสเซนต์", "สเปรย์", "กระป๋องแก๊ส"],
    "ขยะอิเล็กทรอนิกส์": ["อิเล็กทรอนิกส์", "e-waste", "มือถือ", "สายชาร์จ"],
    "ธนาคารขยะ/รีไซเคิล": ["ธนาคารขยะ", "จุดรับรีไซเคิล", "จุดรับกล่องเครื่องดื่ม"],
    "น้ำมันพืชใช้แล้ว": ["น้ำมันพืชใช้แล้ว"],
}


def _s(v) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return ""
    return str(v).strip()


def _num(v):
    try:
        x = float(_s(v))
    except ValueError:
        return None
    return None if math.isnan(x) else x


def clean_rows(records):
    """ตรวจและจัดรูปแถวข้อมูล คืน (rows, problems) — แถวที่ไม่มีชื่อจะถูกข้าม"""
    rows, problems = [], []
    for i, r in enumerate(records, 1):
        name = _s(r.get("name"))
        if not name:
            continue
        row = {f: _s(r.get(f)) for f in FIELDS if f not in ("lat", "lng")}
        if row["type"] not in TYPES:
            problems.append(f"{name}: ประเภท '{row['type']}' ไม่อยู่ในรายการ จึงตั้งเป็น 'อื่น ๆ'")
            row["type"] = "อื่น ๆ"
        lat, lng = _num(r.get("lat")), _num(r.get("lng"))
        if (lat is None) != (lng is None):
            problems.append(f"{name}: ต้องกรอกทั้งละติจูดและลองจิจูด จึงไม่ใช้พิกัดของจุดนี้")
            lat = lng = None
        elif lat is not None and not (-90 <= lat <= 90 and -180 <= lng <= 180):
            problems.append(f"{name}: พิกัดไม่ถูกต้อง จึงไม่ใช้พิกัดของจุดนี้")
            lat = lng = None
        elif lat is not None and not (5 <= lat <= 21 and 97 <= lng <= 106):
            problems.append(f"{name}: พิกัดอยู่นอกประเทศไทย อาจสลับละติจูดกับลองจิจูด (บันทึกไว้แล้ว โปรดตรวจสอบ)")
        row["lat"], row["lng"] = lat, lng
        rows.append(row)
    return rows, problems


def load_places():
    if not PLACES_FILE.exists():
        return []
    with open(PLACES_FILE, encoding="utf-8-sig", newline="") as fh:
        rows, _ = clean_rows(list(csv.DictReader(fh)))
    return rows


def save_places(rows):
    PLACES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PLACES_FILE, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({f: ("" if r.get(f) is None else r[f]) for f in FIELDS})


def parse_csv(data: bytes):
    return list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))


def template_csv() -> str:
    return ",".join(FIELDS) + "\n"


def _target(p) -> str:
    if p.get("lat") is not None and p.get("lng") is not None:
        return f"{p['lat']},{p['lng']}"
    return quote_plus(f"{p['name']} {p.get('address', '')}".strip())


def maps_url(p) -> str:
    return f"https://www.google.com/maps/search/?api=1&query={_target(p)}"


def directions_url(p) -> str:
    return f"https://www.google.com/maps/dir/?api=1&destination={_target(p)}"


def types_for_text(text: str) -> set:
    t = text.lower()
    return {kind for kind, words in _KEYWORDS.items() if any(w in t for w in words)}


def place_chunk(p) -> str:
    """ข้อความของจุดรับ สำหรับให้บอทค้นและอ้างอิงได้"""
    lines = [f"# จุดรับ{p['type']}: {p['name']}"]
    for label, key in (("ที่อยู่", "address"), ("เวลาทำการ", "hours"), ("รับ", "accepts"), ("โทร", "phone")):
        if p.get(key):
            lines.append(f"{label}: {p[key]}")
    lines.append(f"แผนที่: {maps_url(p)}")
    meta = [f"{label}: {p[key]}" for label, key in (("ตรวจสอบเมื่อ", "verified"), ("แหล่งที่มา", "source")) if p.get(key)]
    if meta:
        lines.append(" ".join(meta))
    return "\n".join(lines)


def haversine_km(lat1, lng1, lat2, lng2) -> float:
    """ระยะทางเส้นตรงบนผิวโลก (กม.)"""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lng2 - lng1) / 2) ** 2
    return 2 * 6371.0088 * math.asin(math.sqrt(a))


def with_distance(points, lat, lng):
    """เฉพาะจุดที่มีพิกัด เรียงจากใกล้ไปไกล แต่ละจุดมีค่า _km"""
    near = [{**p, "_km": haversine_km(lat, lng, p["lat"], p["lng"])} for p in points if p.get("lat") is not None]
    return sorted(near, key=lambda p: p["_km"])


def format_km(km: float) -> str:
    return f"{int(round(km * 1000))} ม." if km < 1 else f"{km:.1f} กม."
