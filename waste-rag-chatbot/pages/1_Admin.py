"""หน้าผู้ดูแล: จัดการฐานความรู้ ทดสอบการค้นหา และดูผลประเมิน"""
import hmac
import os
from collections import Counter
from pathlib import Path

import pandas as pd
import streamlit as st

import db
from style import inject_css
from rag import DATA_DIR, SUPPORTED_EXT
from shared import DAILY_GLOBAL_LIMIT, get_rag, snippet  # import ก่อน getenv เพื่อให้โหลด .env แล้ว

st.set_page_config(page_title="จัดการความรู้", page_icon="🛠️")
db.init_db()
inject_css()
st.title("จัดการฐานความรู้")
st.caption("เพิ่ม ลบ และทดสอบความรู้ของบอท · ดูผลประเมินจากผู้ใช้")

MAX_MB = 20
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
if ADMIN_PASSWORD:
    if not st.session_state.get("admin_ok"):
        pw = st.text_input("รหัสผ่านผู้ดูแล", type="password")
        if pw:
            if hmac.compare_digest(pw.encode(), ADMIN_PASSWORD.encode()):
                st.session_state.admin_ok = True
                st.rerun()
            st.error("รหัสผ่านไม่ถูกต้อง")
        st.stop()
else:
    st.warning("ยังไม่ได้ตั้ง ADMIN_PASSWORD ใน .env — ใครเปิดแอปได้ก็แก้ความรู้ได้ "
               "(ไม่เป็นไรถ้าใช้ในเครื่องตัวเอง แต่ควรตั้งก่อนนำขึ้นเซิร์ฟเวอร์)")

with st.spinner("กำลังโหลดโมเดล (ครั้งแรกอาจใช้เวลาสักครู่)..."):
    rag = get_rag()
tab_files, tab_note, tab_test, tab_fb, tab_eval, tab_places = st.tabs(
    ["📄 ไฟล์ความรู้", "✍️ เพิ่มบันทึกสั้น", "🔎 ทดสอบการค้นหา", "⭐ ผลประเมิน", "🧪 ชุดทดสอบ", "📍 จุดรับขยะ"])

# ---------- ไฟล์ความรู้ ----------
with tab_files:
    uploads = st.file_uploader("อัปโหลดเอกสาร (.md .txt .pdf .docx)",
                               type=[e.lstrip(".") for e in sorted(SUPPORTED_EXT)],
                               accept_multiple_files=True)
    if uploads and st.button("💾 บันทึกและอัปเดตฐานความรู้", type="primary"):
        saved = []
        for f in uploads:
            name = Path(f.name).name  # กัน path traversal
            if f.size > MAX_MB * 1024 * 1024:
                st.error(f"{name}: ใหญ่เกิน {MAX_MB} MB")
                continue
            (DATA_DIR / name).write_bytes(f.getbuffer())
            saved.append(name)
        if saved:
            with st.spinner("กำลังสร้างดัชนีใหม่..."):
                rag.reload()
            counts = Counter(c["source"] for c in rag.chunks)
            for name in saved:
                if counts.get(name):
                    st.success(f"{name}: แบ่งเป็น {counts[name]} ชิ้นข้อมูล")
    for name, why in rag.skipped:
        st.warning(f"⚠️ {name}: {why}")

    st.subheader("ไฟล์ในฐานความรู้")
    counts = Counter(c["source"] for c in rag.chunks)
    st.caption(f"ทั้งหมด {len(rag.chunks)} ชิ้นข้อมูล")
    for path in sorted(DATA_DIR.glob("*")):
        if path.suffix.lower() not in SUPPORTED_EXT:
            continue
        c1, c2, c3, c4 = st.columns([5, 2, 2, 1])
        c1.write(path.name)
        c2.caption(f"{counts.get(path.name, 0)} ชิ้น")
        c3.caption(f"{path.stat().st_size / 1024:.1f} KB")
        if c4.button("🗑️", key=f"del_{path.name}", help="ลบไฟล์นี้"):
            path.unlink()
            rag.reload()
            st.rerun()

# ---------- บันทึกสั้น ----------
with tab_note:
    st.caption("พิมพ์ความรู้สั้น ๆ เช่น จุดรับขยะในชุมชน ระบบจะเก็บใน data/admin_notes.md")
    with st.form("note_form", clear_on_submit=True):
        title = st.text_input("หัวข้อ", placeholder="จุดรับขยะอันตราย เทศบาล...")
        body = st.text_area("เนื้อหา", height=180)
        source = st.text_input("แหล่งที่มา (ถ้ามี)", placeholder="เว็บไซต์เทศบาล ตรวจสอบเมื่อ ต.ค. 2569")
        if st.form_submit_button("เพิ่มความรู้", type="primary"):
            if not title.strip() or not body.strip():
                st.error("กรุณากรอกหัวข้อและเนื้อหา")
            else:
                entry = f"\n\n# {' '.join(title.split())}\n{body.strip()}\n"
                if source.strip():
                    entry += f"แหล่งที่มา: {source.strip()}\n"
                with open(DATA_DIR / "admin_notes.md", "a", encoding="utf-8") as fh:
                    fh.write(entry)
                rag.reload()
                st.success("เพิ่มแล้ว บอทใช้ข้อมูลนี้ได้ทันที")

# ---------- ทดสอบการค้นหา ----------
with tab_test:
    st.caption("ดูว่าคำถามหนึ่ง ๆ ค้นเจอข้อมูลชิ้นไหนบ้าง (ไม่เรียก LLM ไม่เสียค่า API)")
    q = st.text_input("คำถามทดสอบ", placeholder="ถ่านไฟฉายทิ้งที่ไหน")
    k = st.slider("แสดงกี่ชิ้น", 1, 10, 5)
    if q:
        hits = rag.retrieve(q, k=k, min_score=0.0)
        if not hits:
            st.info("ฐานความรู้ว่างเปล่า")
        for h in hits:
            st.markdown(f"**[{h['ref']}]** `{h['source']}` {h.get('title', '')} — "
                        f"รวม **{h['score']:.2f}** (ความหมาย {h.get('semantic', 0):.2f}, คำตรง {h.get('keyword', 0):.2f})")
            snippet(h["text"])
        st.caption("ตอนตอบจริงจะใช้ข้อมูลชิ้นที่ความหมาย ≥ 0.25 หรือคำตรง ≥ 0.5 (ปรับที่ฟังก์ชัน retrieve ใน rag.py)")

# ---------- ผลประเมิน ----------
with tab_fb:
    stats = db.feedback_stats()
    c1, c2 = st.columns(2)
    c1.metric("คะแนนเฉลี่ย", f"{stats['avg']:.2f} / 5")
    c2.metric("จำนวนรีวิว", stats["count"])
    st.caption(f"คำถามทั้งระบบวันนี้: {db.global_questions_today()} จากเพดาน {DAILY_GLOBAL_LIMIT}")
    dist = db.rating_distribution()
    st.bar_chart(pd.DataFrame({"จำนวน": list(dist.values())}, index=[f"{i} ดาว" for i in dist]))

    st.subheader("คำตอบที่ได้คะแนนต่ำ / มีข้อเสนอแนะ")
    st.caption("ใช้ดูว่าควรเพิ่มความรู้เรื่องอะไร")
    rows = db.low_rated()
    if not rows:
        st.info("ยังไม่มีรายการ")
    for r in rows:
        stars = f"{'⭐' * r['rating']} " if r["rating"] else ""
        with st.expander(f"{stars}{(r['question'] or '-')[:70]}"):
            st.markdown(f"**คำถาม:** {r['question']}")
            if r["comment"]:
                st.markdown(f"**ความเห็นผู้ใช้:** {r['comment']}")
            st.markdown("**คำตอบของบอท:**")
            st.write(r["answer"])

# ---------- ชุดทดสอบคุณภาพ ----------
with tab_eval:
    from evaluate import load_questions, run_eval

    items = load_questions()
    st.caption(f"ชุดทดสอบ {len(items)} ข้อ (ไฟล์ eval/questions.json) รันทุกครั้งหลังเพิ่มข้อมูลหรือเปลี่ยนโมเดล "
               "เพื่อดูว่าค้นเจอและตอบถูกสีถังหรือไม่")
    use_llm = st.checkbox("ตรวจคำตอบจริงด้วย LLM (เสียค่า API ประมาณ 1 คำถามต่อ 1 ข้อ)", value=False)
    if use_llm and rag.client is None:
        st.warning("ยังไม่ได้ตั้งค่า API key จึงรันได้เฉพาะโหมดค้นหาข้อมูล")
        use_llm = False
    if st.button("▶ รันชุดทดสอบ", type="primary"):
        bar = st.progress(0.0)
        st.session_state.eval_rows = run_eval(rag, items, k=4, use_llm=use_llm, progress=bar.progress)
        bar.empty()
    rows = st.session_state.get("eval_rows")
    if rows:
        passed = sum(r["pass"] for r in rows)
        crit_fail = [r for r in rows if r["critical"] and not r["pass"]]
        c1, c2, c3 = st.columns(3)
        c1.metric("ผ่าน", f"{passed}/{len(rows)}")
        c2.metric("อัตราผ่าน", f"{passed / len(rows):.0%}")
        c3.metric("ข้อสำคัญที่ไม่ผ่าน", len(crit_fail), help="ขยะอันตราย/ความปลอดภัย ควรเป็น 0")
        df = pd.DataFrame(rows)
        df["ผล"] = df["pass"].map({True: "ผ่าน", False: "ไม่ผ่าน"})
        st.dataframe(df.sort_values("pass")[["ผล", "critical", "question", "problems"]],
                     use_container_width=True, hide_index=True)
        st.download_button("ดาวน์โหลดผล (CSV)", df.to_csv(index=False).encode("utf-8-sig"), "eval_results.csv")

# ---------- จุดรับขยะ ----------
with tab_places:
    import places

    st.caption("เพิ่มเฉพาะจุดที่ตรวจสอบแล้ว บอทจะใช้ข้อมูลนี้ตอบคำถามและแสดงลิงก์ Google Maps "
               "หาพิกัดได้โดยคลิกขวาที่ตำแหน่งใน Google Maps แล้วคัดลอกตัวเลขสองค่า (ละติจูด, ลองจิจูด)")
    base = pd.DataFrame(places.load_places(), columns=places.FIELDS).astype({"lat": "float64", "lng": "float64"})
    edited = st.data_editor(
        base, num_rows="dynamic", use_container_width=True, hide_index=True, key="places_editor",
        column_config={
            "name": st.column_config.TextColumn("ชื่อสถานที่", required=True),
            "type": st.column_config.SelectboxColumn("ประเภท", options=places.TYPES, required=True),
            "address": st.column_config.TextColumn("ที่อยู่"),
            "lat": st.column_config.NumberColumn("ละติจูด", format="%.6f"),
            "lng": st.column_config.NumberColumn("ลองจิจูด", format="%.6f"),
            "hours": st.column_config.TextColumn("วันเวลาทำการ"),
            "accepts": st.column_config.TextColumn("รับอะไรบ้าง"),
            "phone": st.column_config.TextColumn("โทรศัพท์"),
            "source": st.column_config.TextColumn("แหล่งที่มา"),
            "verified": st.column_config.TextColumn("ตรวจสอบเมื่อ", help="เช่น ต.ค. 2569"),
        })
    if st.button("💾 บันทึกจุดรับขยะ", type="primary", key="save_places"):
        rows, problems = places.clean_rows(edited.to_dict("records"))
        places.save_places(rows)
        with st.spinner("กำลังอัปเดตฐานความรู้..."):
            rag.reload()
        st.success(f"บันทึกแล้ว {len(rows)} จุด บอทใช้ข้อมูลนี้ได้ทันที")
        for pr in problems:
            st.warning(pr)

    st.divider()
    up = st.file_uploader("นำเข้าจากไฟล์ CSV (เพิ่มต่อท้ายรายการเดิม)", type="csv", key="places_csv")
    if up and st.button("นำเข้า", key="import_places"):
        new_rows, problems = places.clean_rows(places.parse_csv(up.getvalue()))
        places.save_places(places.load_places() + new_rows)
        rag.reload()
        st.success(f"นำเข้า {len(new_rows)} จุดแล้ว")
        for pr in problems:
            st.warning(pr)
    st.download_button("ดาวน์โหลดไฟล์ตัวอย่าง (CSV)", places.template_csv().encode("utf-8-sig"), "points_template.csv")

with tab_places:
    with st.expander("หาพิกัดโดยคลิกบนแผนที่"):
        try:
            import folium
            from streamlit_folium import st_folium
        except ImportError:
            st.info("ติดตั้ง streamlit-folium ก่อน (pip install -r requirements.txt)")
        else:
            known = [p for p in places.load_places() if p["lat"] is not None]
            ctr = ([sum(p["lat"] for p in known) / len(known), sum(p["lng"] for p in known) / len(known)]
                   if known else [15.0, 101.0])
            fmap = folium.Map(location=ctr, zoom_start=13 if known else 6)
            for p in known:
                folium.Marker([p["lat"], p["lng"]], tooltip=p["name"]).add_to(fmap)
            res = st_folium(fmap, height=360, use_container_width=True,
                            returned_objects=["last_clicked"], key="coord_picker") or {}
            if res.get("last_clicked"):
                st.code(f'{res["last_clicked"]["lat"]:.6f}, {res["last_clicked"]["lng"]:.6f}')
                st.caption("คัดลอกเลขสองค่านี้ไปใส่ช่องละติจูดและลองจิจูดในตารางด้านบน")
