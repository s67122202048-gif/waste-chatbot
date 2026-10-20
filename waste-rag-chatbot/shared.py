"""ตัวโหลด RAG ที่ใช้ร่วมกันทุกหน้า — โหลดโมเดลเบื้องหลัง เพื่อให้หน้าเว็บขึ้นทันที"""
import html
import os
import threading

import streamlit as st
from rag import WasteRAG

def _env_int(name, default):
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


# ค่าจำกัดการใช้งาน (ตั้งใน .env ได้) — ใช้ควบคุมค่า API
DAILY_QUESTION_LIMIT = _env_int("DAILY_QUESTION_LIMIT", 30)   # คำถามต่อคนต่อวัน
DAILY_IMAGE_LIMIT = _env_int("DAILY_IMAGE_LIMIT", 10)         # ภาพต่อคนต่อวัน
DAILY_GLOBAL_LIMIT = _env_int("DAILY_GLOBAL_LIMIT", 500)      # คำถามรวมทั้งระบบต่อวัน
MAX_IMAGE_MB = _env_int("MAX_IMAGE_MB", 5)
MAX_QUESTION_CHARS = _env_int("MAX_QUESTION_CHARS", 500)
RETENTION_DAYS = _env_int("RETENTION_DAYS", 90)               # 0 = ไม่ลบประวัติอัตโนมัติ

_lock = threading.Lock()
_rag = None


def get_rag():
    """คืน RAG (ถ้ายังโหลดไม่เสร็จ จะรอจนเสร็จ)"""
    global _rag
    with _lock:
        if _rag is None:
            _rag = WasteRAG()
    return _rag


def peek_rag():
    """ดูว่าโหลดเสร็จหรือยัง โดยไม่รอ (ยังไม่เสร็จ = None)"""
    return _rag


def _safe_load():
    try:
        get_rag()
    except Exception as e:  # แจ้งใน terminal; ตอนผู้ใช้ถามจะลองโหลดใหม่และแสดงข้อผิดพลาด
        print("โหลดโมเดลเบื้องหลังไม่สำเร็จ:", e)


def preload():
    """เริ่มโหลดโมเดลเบื้องหลังทันทีที่เซิร์ฟเวอร์เริ่ม (ทำครั้งเดียวต่อโปรเซส)"""
    if _rag is None and not any(t.name == "rag-preload" for t in threading.enumerate()):
        threading.Thread(target=_safe_load, name="rag-preload", daemon=True).start()


def llm_configured() -> bool:
    return bool(os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY"))


preload()


def snippet(text: str):
    """แสดงข้อความอ้างอิงด้วยฟอนต์ปกติ (ไม่ใช่ monospace) เพื่อให้สระ/วรรณยุกต์ไทยไม่ลอย"""
    st.markdown(
        f'<div style="white-space:pre-wrap;line-height:1.8;font-size:0.9rem;'
        f'max-height:260px;overflow:auto;">{html.escape(text)}</div>',
        unsafe_allow_html=True)
