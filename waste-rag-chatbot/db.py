"""ฐานข้อมูล SQLite: ประวัติแชท (แยกตามผู้ใช้), คะแนนความพึงพอใจ และโควตาการใช้งานรายวัน"""
import json
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

import storage

DB_PATH = storage.DB_PATH


def _execute(sql, params=()):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        cur = conn.execute(sql, params)
        rows = cur.fetchall()
        conn.commit()
        return rows, cur.lastrowid
    finally:
        conn.close()


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _today():
    return date.today().isoformat()


def init_db():
    _execute("""CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        title TEXT NOT NULL DEFAULT 'การสนทนาใหม่',
        created_at TEXT NOT NULL)""")
    _execute("""CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        sources TEXT,
        vision TEXT,
        has_image INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL)""")
    _execute("""CREATE TABLE IF NOT EXISTS feedback (
        message_id INTEGER PRIMARY KEY REFERENCES messages(id) ON DELETE CASCADE,
        rating INTEGER,
        comment TEXT,
        created_at TEXT NOT NULL)""")
    _execute("""CREATE TABLE IF NOT EXISTS usage (
        user_id TEXT NOT NULL, day TEXT NOT NULL,
        questions INTEGER NOT NULL DEFAULT 0, images INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (user_id, day))""")
    # ย้ายฐานข้อมูลเวอร์ชันเก่า (ยังไม่มี user_id) — แชทเก่าจะไม่แสดงให้ผู้ใช้คนใดเห็น
    cols = [r["name"] for r in _execute("PRAGMA table_info(sessions)")[0]]
    if "user_id" not in cols:
        _execute("ALTER TABLE sessions ADD COLUMN user_id TEXT")
    _execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)")


# ---------- เซสชัน/ข้อความ (ทุกฟังก์ชันตรวจเจ้าของด้วย user_id) ----------
def create_session(user_id, title="การสนทนาใหม่"):
    _, sid = _execute("INSERT INTO sessions (user_id, title, created_at) VALUES (?, ?, ?)",
                      (user_id, title, _now()))
    return sid


def set_title(session_id, title):
    _execute("UPDATE sessions SET title=? WHERE id=?", (title[:40], session_id))


def list_sessions(user_id, limit=30):
    rows, _ = _execute(
        """SELECT id, title, created_at FROM sessions s
           WHERE s.user_id = ? AND EXISTS (SELECT 1 FROM messages m WHERE m.session_id = s.id)
           ORDER BY id DESC LIMIT ?""", (user_id, limit))
    return [dict(r) for r in rows]


def delete_session(session_id, user_id):
    _execute("DELETE FROM sessions WHERE id=? AND user_id=?", (session_id, user_id))


def delete_user_data(user_id):
    _execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
    _execute("DELETE FROM usage WHERE user_id=?", (user_id,))


def add_message(session_id, role, content, sources=None, vision=None, has_image=False):
    _, mid = _execute(
        """INSERT INTO messages (session_id, role, content, sources, vision, has_image, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (session_id, role, content,
         json.dumps(sources, ensure_ascii=False) if sources else None,
         json.dumps(vision, ensure_ascii=False) if vision else None,
         int(has_image), _now()))
    return mid


def get_messages(session_id, user_id):
    rows, _ = _execute(
        """SELECT m.*, f.rating, f.comment FROM messages m
           JOIN sessions s ON s.id = m.session_id
           LEFT JOIN feedback f ON f.message_id = m.id
           WHERE m.session_id = ? AND s.user_id = ? ORDER BY m.id""", (session_id, user_id))
    out = []
    for r in rows:
        d = dict(r)
        d["sources"] = json.loads(d["sources"]) if d["sources"] else []
        d["vision"] = json.loads(d["vision"]) if d["vision"] else None
        out.append(d)
    return out


def _owns_message(message_id, user_id):
    rows, _ = _execute("SELECT 1 FROM messages m JOIN sessions s ON s.id = m.session_id "
                       "WHERE m.id = ? AND s.user_id = ?", (message_id, user_id))
    return bool(rows)


def save_rating(message_id, rating, user_id):
    if not _owns_message(message_id, user_id):
        return False
    _execute("""INSERT INTO feedback (message_id, rating, created_at) VALUES (?, ?, ?)
                ON CONFLICT(message_id) DO UPDATE SET rating=excluded.rating""",
             (message_id, rating, _now()))
    return True


def save_comment(message_id, comment, user_id):
    if not _owns_message(message_id, user_id):
        return False
    _execute("""INSERT INTO feedback (message_id, comment, created_at) VALUES (?, ?, ?)
                ON CONFLICT(message_id) DO UPDATE SET comment=excluded.comment""",
             (message_id, comment, _now()))
    return True


# ---------- สถิติรวม (สำหรับหน้า Admin) ----------
def feedback_stats():
    rows, _ = _execute("SELECT COUNT(rating) AS n, AVG(rating) AS avg FROM feedback WHERE rating IS NOT NULL")
    r = rows[0]
    return {"count": r["n"] or 0, "avg": r["avg"] or 0.0}


def rating_distribution():
    rows, _ = _execute("SELECT rating, COUNT(*) AS n FROM feedback WHERE rating IS NOT NULL GROUP BY rating")
    dist = {i: 0 for i in range(1, 6)}
    for r in rows:
        dist[r["rating"]] = r["n"]
    return dist


def low_rated(max_rating=2, limit=30):
    """คำตอบที่ได้คะแนนต่ำหรือมีข้อเสนอแนะ พร้อมคำถามที่ผู้ใช้ถาม"""
    rows, _ = _execute(
        """SELECT m.id, m.content AS answer, f.rating, f.comment, f.created_at,
             (SELECT u.content FROM messages u
               WHERE u.session_id = m.session_id AND u.id < m.id AND u.role = 'user'
               ORDER BY u.id DESC LIMIT 1) AS question
           FROM messages m JOIN feedback f ON f.message_id = m.id
           WHERE (f.rating IS NOT NULL AND f.rating <= ?)
              OR (f.comment IS NOT NULL AND f.comment != '')
           ORDER BY f.created_at DESC LIMIT ?""", (max_rating, limit))
    return [dict(r) for r in rows]


# ---------- โควตาการใช้งาน (ควบคุมค่า API) ----------
def usage_today(user_id):
    rows, _ = _execute("SELECT questions, images FROM usage WHERE user_id=? AND day=?", (user_id, _today()))
    return {"questions": rows[0]["questions"], "images": rows[0]["images"]} if rows else {"questions": 0, "images": 0}


def add_usage(user_id, images=0):
    _execute("""INSERT INTO usage (user_id, day, questions, images) VALUES (?, ?, 1, ?)
                ON CONFLICT(user_id, day) DO UPDATE SET
                  questions = questions + 1, images = images + excluded.images""",
             (user_id, _today(), images))


def global_questions_today():
    rows, _ = _execute("SELECT COALESCE(SUM(questions), 0) AS n FROM usage WHERE day=?", (_today(),))
    return rows[0]["n"]


def purge_old(days):
    """ลบประวัติที่เก่ากว่า N วัน (ความเป็นส่วนตัว) — days <= 0 = ไม่ลบ"""
    if days and days > 0:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
        _execute("DELETE FROM sessions WHERE created_at < ?", (cutoff,))
    _execute("DELETE FROM usage WHERE day < ?", ((date.today() - timedelta(days=30)).isoformat(),))
