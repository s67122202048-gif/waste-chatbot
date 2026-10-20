"""หน้าเว็บแชทบอท (Streamlit) — รันด้วย: streamlit run app.py"""
import io
import re
import secrets
import time

import streamlit as st
from PIL import Image, ImageOps

import db
from rag import format_vision
from shared import (DAILY_GLOBAL_LIMIT, DAILY_IMAGE_LIMIT, DAILY_QUESTION_LIMIT, MAX_IMAGE_MB,
                    MAX_QUESTION_CHARS, RETENTION_DAYS, get_rag, llm_configured, peek_rag, snippet)
from places import load_places, types_for_text, with_distance
from style import bin_cards, hero, inject_css, place_card_html, split_bins, strip_partial_bin

st.set_page_config(page_title="น้องรีไซเคิล", page_icon="♻️", layout="centered",
                   initial_sidebar_state="expanded")
db.init_db()
db.purge_old(RETENTION_DAYS)
inject_css()


def get_user_id() -> str:
    """รหัสผู้ใช้แบบไม่ระบุตัวตน: สุ่มครั้งแรกแล้วเก็บไว้ในลิงก์ (?u=...) ผู้ใช้บุ๊กมาร์กลิงก์เพื่อกลับมาดูประวัติเดิม"""
    uid = st.query_params.get("u") or ""
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,64}", uid):
        uid = st.session_state.get("uid") or secrets.token_urlsafe(16)
    st.session_state.uid = uid  # กันหลุดเมื่อสลับไปหน้า Admin แล้วกลับมา
    if st.query_params.get("u") != uid:
        st.query_params["u"] = uid
    return uid


USER_ID = get_user_id()

CONF_TH = {"high": "สูง", "medium": "ปานกลาง", "low": "ต่ำ"}
DEFAULT_IMAGE_QUESTION = "ขยะในภาพนี้คืออะไร ควรทิ้งที่ไหนและเตรียมอย่างไรก่อนรีไซเคิล"
AVATARS = {"assistant": "♻️", "user": "🙂"}
EXAMPLES = [
    "ขวดน้ำพลาสติกทิ้งถังสีอะไร",
    "ถ่านไฟฉายและหลอดไฟทิ้งอย่างไร",
    "เตรียมกล่องนมก่อนรีไซเคิลอย่างไร",
    "ทำปุ๋ยหมักจากเศษอาหารยังไง",
    "กล่องพิซซ่าเปื้อนน้ำมันรีไซเคิลได้ไหม",
    "น้ำมันพืชใช้แล้วต้องทิ้งที่ไหน",
]


def prepare_image(file) -> bytes:
    """แก้การหมุนจาก EXIF, ย่อขนาดไม่เกิน 1024px และแปลงเป็น JPEG เพื่อลดขนาด/ค่าใช้จ่าย"""
    img = ImageOps.exif_transpose(Image.open(file)).convert("RGB")
    img.thumbnail((1024, 1024))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    return buf.getvalue()


# ---------- Callbacks ----------
def new_chat():
    st.session_state.session_id = None


def open_session(sid):
    st.session_state.session_id = sid


def delete_current():
    if st.session_state.session_id:
        db.delete_session(st.session_state.session_id, USER_ID)
    st.session_state.session_id = None


def save_rating(message_id, key):
    value = st.session_state.get(key)
    if value is not None:
        db.save_rating(message_id, value + 1, USER_ID)  # st.feedback ให้ค่า 0-4


# ---------- Render helpers ----------
def render_vision(vision):
    if not vision:
        return
    with st.expander("🔍 ผลระบุประเภทจากภาพ (เบื้องต้น)"):
        items = format_vision(vision)
        st.markdown(items or "ระบุขยะในภาพไม่ได้")
        st.caption(f"ความมั่นใจ: {CONF_TH.get(vision.get('confidence'), '-')} · "
                   "เป็นการประมาณเบื้องต้น อาจคลาดเคลื่อน")
        if vision.get("note"):
            st.caption(vision["note"])


def render_sources(sources, answer):
    if not sources:
        return
    cited = {int(n) for n in re.findall(r"\[(\d+)\]", answer)}
    shown = [s for s in sources if s["ref"] in cited] or sources
    label = "📚 แหล่งอ้างอิง" if cited else "📚 ข้อมูลที่ค้นพบ"
    with st.expander(f"{label} ({len(shown)})"):
        for s in shown:
            title = f" — {s['title']}" if s.get("title") else ""
            st.markdown(f"**[{s['ref']}]** `{s['source']}`{title}  \nความเกี่ยวข้อง {s['score']:.2f}")
            snippet(s["text"])


def render_feedback(m):
    key = f"fb_{m['id']}"
    if key not in st.session_state and m["rating"]:
        st.session_state[key] = m["rating"] - 1
    col1, col2 = st.columns([3, 2])
    with col1:
        st.feedback("stars", key=key, on_change=save_rating, args=(m["id"], key))
    with col2:
        with st.popover("💬 ข้อเสนอแนะ"):
            text = st.text_area("บอกเราเพิ่มเติม", value=m["comment"] or "", key=f"cm_{m['id']}")
            if st.button("บันทึก", key=f"cmb_{m['id']}"):
                db.save_comment(m["id"], text.strip(), USER_ID)
                st.toast("บันทึกข้อเสนอแนะแล้ว ขอบคุณครับ")


def render_places(answer):
    """ถ้าคำตอบเกี่ยวกับขยะที่ต้องไปทิ้งที่จุดรับ แสดงจุดรับที่มีในระบบ (พร้อมลิงก์ Google Maps)"""
    kinds = types_for_text(answer)
    pts = [p for p in load_places() if p["type"] in kinds] if kinds else []
    pos = st.session_state.get("my_pos")
    if pos and pts:  # ผู้ใช้ระบุตำแหน่งไว้ที่หน้า Map -> เรียงจากใกล้ไปไกล
        pts = with_distance(pts, *pos) + [p for p in pts if p.get("lat") is None]
    pts = pts[:3]
    if pts:
        with st.expander(f"📍 จุดรับที่เกี่ยวข้อง ({len(pts)})", expanded=True):
            st.markdown("".join(place_card_html(p) for p in pts), unsafe_allow_html=True)
            st.caption("ตรวจสอบวันเวลาทำการก่อนเดินทาง ดูแผนที่และจุดรับทั้งหมดได้ที่เมนู Map ด้านซ้าย")


def render_message(m):
    with st.chat_message(m["role"], avatar=AVATARS[m["role"]]):
        if m["role"] == "user" and m["has_image"]:
            st.caption("📷 แนบภาพขยะ")
        body = m["content"]
        if m["role"] == "assistant":
            colors, body = split_bins(body)
            bin_cards(colors)
        st.markdown(body)
        if m["role"] == "assistant":
            render_vision(m["vision"])
            render_sources(m["sources"], m["content"])
            render_places(m["content"])
            render_feedback(m)


# ---------- แสดงคำตอบแบบทีละส่วน ----------
def stream_to_screen(events, first_event) -> str:
    """แสดงคำตอบทีละส่วนระหว่างที่ LLM เขียน แล้วคืนข้อความเต็ม"""
    if first_event["type"] == "full":
        return first_event["text"]
    card_ph, text_ph = st.empty(), st.empty()
    text_ph.caption("กำลังเขียนคำตอบ...")
    full, shown, last = "", None, 0.0
    for ev in events:
        full += ev["text"]
        if time.time() - last < 0.08:
            continue
        last = time.time()
        colors, body = split_bins(strip_partial_bin(full))
        if colors != shown:
            shown = colors
            with card_ph.container():
                bin_cards(colors)
        text_ph.markdown(body + " ▌")
    colors, body = split_bins(full)
    if colors != shown:
        with card_ph.container():
            bin_cards(colors)
    text_ph.markdown(body)
    return full


# ---------- Sidebar ----------
@st.fragment(run_every=None if peek_rag() else 2)
def model_status(was_loading=peek_rag() is None):
    r = peek_rag()
    if r is None:
        st.caption("⏳ กำลังเตรียมระบบค้นหา ครั้งแรกอาจใช้เวลาสักครู่ (ถามได้เลย ระบบจะรอให้)")
        return
    st.caption(f"🟢 พร้อมใช้งาน ({r.provider} {r.model})" if r.client else "🟢 พร้อมใช้งาน (ไม่มี LLM)")
    if was_loading:
        st.rerun()  # โหลดเสร็จแล้ว รีเฟรชทั้งหน้าครั้งเดียวเพื่อเลิกเช็คสถานะ


if "session_id" not in st.session_state:
    st.session_state.session_id = None

with st.sidebar:
    st.markdown('<div class="brand">♻️ น้องรีไซเคิล</div>', unsafe_allow_html=True)
    with st.container(key="newchat"):
        st.button("เริ่มแชทใหม่", on_click=new_chat, use_container_width=True)
    with st.expander("ตั้งค่าการค้นหา"):
        top_k = st.slider("จำนวนเอกสารอ้างอิง", 1, 8, 4,
                          help="ยิ่งมาก บอทยิ่งมีข้อมูลประกอบมาก แต่ตอบช้าและแพงขึ้น")

    st.subheader("ประวัติการสนทนา")
    sessions = db.list_sessions(USER_ID)
    if not sessions:
        st.caption("ยังไม่มีประวัติ")
    for s in sessions:
        active = s["id"] == st.session_state.session_id
        st.button(("▶ " if active else "") + s["title"], key=f"s{s['id']}",
                  on_click=open_session, args=(s["id"],), use_container_width=True,
                  type="primary" if active else "secondary")
    if st.session_state.session_id:
        st.button("🗑️ ลบแชทนี้", on_click=delete_current, use_container_width=True)

    used = db.usage_today(USER_ID)
    st.caption(f"วันนี้ถามได้อีก {max(DAILY_QUESTION_LIMIT - used['questions'], 0)} จาก {DAILY_QUESTION_LIMIT} คำถาม")
    with st.expander("ความเป็นส่วนตัว"):
        st.caption("ประวัติแชทผูกกับลิงก์ของหน้านี้ (มีรหัสสุ่มต่อท้าย) บุ๊กมาร์กไว้เพื่อกลับมาดู "
                   f"และอย่าส่งลิงก์ให้ผู้อื่น ระบบลบประวัติอัตโนมัติหลัง {RETENTION_DAYS} วัน")
        st.caption("ภาพที่แนบจะถูกส่งให้ผู้ให้บริการ AI เพื่อวิเคราะห์ ระบบไม่เก็บไฟล์ภาพและลบข้อมูลตำแหน่งในภาพ "
                   "โปรดเลี่ยงภาพที่มีใบหน้า ป้ายทะเบียน หรือข้อมูลส่วนตัว")
        if st.button("ลบประวัติทั้งหมดของฉัน", key="wipe", use_container_width=True):
            db.delete_user_data(USER_ID)
            st.session_state.session_id = None
            st.rerun()
    model_status()
    stats = db.feedback_stats()
    st.divider()
    st.caption(f"⭐ คะแนนเฉลี่ยรวม: {stats['avg']:.2f} / 5 ({stats['count']} รีวิว)")
    st.caption("คำตอบจาก AI อาจคลาดเคลื่อน ถ้าไม่แน่ใจ โดยเฉพาะขยะอันตราย ให้สอบถามเทศบาลหรือสำนักงานเขต")

# ---------- Main ----------

if not llm_configured():
    st.warning("ยังไม่ได้ตั้งค่า API key (OPENAI_API_KEY หรือ ANTHROPIC_API_KEY) ใน .env — จะแสดงเฉพาะข้อมูลที่ค้นเจอ และใช้ฟีเจอร์ภาพไม่ได้")

pending = st.session_state.pop("pending", None)  # คำถามจากปุ่มตัวอย่าง
sid = st.session_state.session_id
messages = db.get_messages(sid, USER_ID) if sid else []
hero(compact=bool(messages) or bool(pending))
if not messages and not pending:
    st.markdown('<div class="try-title">ลองถามได้เลย หรือกดคลิปหนีบที่ช่องพิมพ์เพื่อแนบภาพขยะ</div>',
                unsafe_allow_html=True)
    with st.container(key="examples"):
        cols = st.columns(2)
        for i, q in enumerate(EXAMPLES):
            if cols[i % 2].button(q, key=f"ex{i}", use_container_width=True):
                st.session_state.pending = q
                st.rerun()
    st.caption("ภาพที่แนบจะถูกส่งให้ผู้ให้บริการ AI เพื่อวิเคราะห์ โปรดเลี่ยงภาพที่มีใบหน้าหรือข้อมูลส่วนตัว")
for m in messages:
    render_message(m)

prompt = st.chat_input("พิมพ์คำถาม หรือแนบภาพขยะ...", accept_file=True,
                       file_type=["jpg", "jpeg", "png", "webp"])

text, files = "", []
if prompt:
    text = (prompt["text"] or "").strip()
    files = prompt["files"] or []
elif pending:
    text = pending

if text or files:
    image_file = files[0] if files else None
    used = db.usage_today(USER_ID)
    problem = None
    if len(text) > MAX_QUESTION_CHARS:
        problem = f"คำถามยาวเกิน {MAX_QUESTION_CHARS} ตัวอักษร (ตอนนี้ {len(text)}) ช่วยย่อให้สั้นลงนะ"
    elif image_file is not None and image_file.size > MAX_IMAGE_MB * 1024 * 1024:
        problem = f"ภาพใหญ่เกิน {MAX_IMAGE_MB} MB ลองลดขนาดหรือถ่ายใหม่"
    elif used["questions"] >= DAILY_QUESTION_LIMIT:
        problem = f"วันนี้คุณถามครบ {DAILY_QUESTION_LIMIT} คำถามแล้ว กลับมาถามใหม่ได้พรุ่งนี้"
    elif image_file is not None and used["images"] >= DAILY_IMAGE_LIMIT:
        problem = f"วันนี้ส่งภาพครบ {DAILY_IMAGE_LIMIT} ภาพแล้ว พิมพ์ถามเป็นข้อความได้ หรือส่งภาพใหม่พรุ่งนี้"
    elif db.global_questions_today() >= DAILY_GLOBAL_LIMIT:
        problem = "วันนี้ระบบมีผู้ใช้งานเต็มโควตาแล้ว กรุณากลับมาใหม่พรุ่งนี้"
    if problem:
        st.warning(problem)
        st.stop()
    try:
        image_bytes = prepare_image(image_file) if image_file else None
    except Exception:
        st.warning("เปิดไฟล์ภาพนี้ไม่ได้ ลองใช้ไฟล์ JPG หรือ PNG อื่น")
        st.stop()
    db.add_usage(USER_ID, images=1 if image_bytes else 0)
    question = text or DEFAULT_IMAGE_QUESTION
    shown_text = text or "(ส่งภาพขยะเพื่อให้ช่วยระบุประเภท)"

    if sid is None:
        sid = st.session_state.session_id = db.create_session(USER_ID)
        db.set_title(sid, shown_text)

    history = [{"role": m["role"], "content": m["content"]} for m in messages]
    db.add_message(sid, "user", shown_text, has_image=bool(image_bytes))

    with st.chat_message("user", avatar=AVATARS["user"]):
        if image_bytes:
            st.image(image_bytes, width=240)
        st.markdown(shown_text)

    with st.chat_message("assistant", avatar=AVATARS["assistant"]):
        try:
            first = peek_rag() is None
            with st.spinner("กำลังเตรียมระบบค้นหา (ครั้งแรกอาจใช้เวลาสักครู่)..." if first
                            else "กำลังค้นหาข้อมูล..."):
                rag = get_rag()
                events = rag.answer_stream(question, history=history, image_bytes=image_bytes, k=top_k)
                first_ev = next(events)  # ค้นหา (+วิเคราะห์ภาพ) เสร็จแล้วจึงเริ่มเขียนคำตอบ
            full = stream_to_screen(events, first_ev).strip() or "ขออภัย ไม่ได้รับคำตอบจากระบบ ลองถามอีกครั้งนะ"
            db.add_message(sid, "assistant", full, sources=first_ev["sources"], vision=first_ev["vision"])
        except Exception as e:
            st.error(f"เกิดข้อผิดพลาด: {e}")
            st.stop()
    st.rerun()  # โหลดใหม่จาก DB เพื่อให้มีปุ่มให้คะแนนของข้อความล่าสุด
