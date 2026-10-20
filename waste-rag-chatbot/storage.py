"""ที่เก็บข้อมูลของแอป (ประวัติแชท ความรู้ จุดรับขยะ แคช)
ค่าเริ่มต้นอยู่ในโฟลเดอร์โปรเจกต์ ถ้าขึ้นเซิร์ฟเวอร์ให้ตั้ง APP_STORAGE ชี้ไปที่ดิสก์ถาวร (เช่น /data)
ครั้งแรกระบบจะคัดลอก data/ และ locations/ จากโปรเจกต์ไปไว้ให้เอง"""
import os
import shutil
from pathlib import Path

CODE_DIR = Path(__file__).parent
ROOT = Path(os.getenv("APP_STORAGE") or CODE_DIR)

DB_PATH = ROOT / "chat_history.db"
DATA_DIR = ROOT / "data"
CACHE_DIR = ROOT / ".cache"
PLACES_FILE = ROOT / "locations" / "points.csv"


def seed():
    if ROOT.resolve() == CODE_DIR.resolve():
        return
    ROOT.mkdir(parents=True, exist_ok=True)
    for name in ("data", "locations"):
        if not (ROOT / name).exists() and (CODE_DIR / name).exists():
            shutil.copytree(CODE_DIR / name, ROOT / name)


seed()
