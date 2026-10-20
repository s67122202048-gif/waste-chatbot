"""หน้าแผนที่จุดรับขยะ: คลิกหมุดดูรายละเอียด และดูจุดที่ใกล้ที่สุดจากตำแหน่งของคุณ"""
import html

import pandas as pd
import streamlit as st

import places
from style import inject_css, place_card_html

try:
    import folium
    from streamlit_folium import st_folium
except ImportError:  # ยังไม่ได้ติดตั้ง -> ใช้แผนที่แบบเรียบแทน
    folium = None
try:
    from streamlit_geolocation import streamlit_geolocation
except ImportError:
    streamlit_geolocation = None

ICON_COLORS = {"ขยะอันตราย": "red", "ขยะอิเล็กทรอนิกส์": "purple", "ธนาคารขยะ/รีไซเคิล": "green",
               "น้ำมันพืชใช้แล้ว": "orange", "อื่น ๆ": "gray"}

st.set_page_config(page_title="แผนที่จุดรับขยะ", page_icon="📍")
inject_css()
st.title("แผนที่จุดรับขยะ")
st.caption("คลิกหมุดบนแผนที่เพื่อดูรายละเอียด และระบุตำแหน่งของคุณเพื่อดูจุดที่ใกล้ที่สุด "
           "ตรวจสอบวันเวลาทำการอีกครั้งก่อนเดินทาง")


def popup_html(p):
    e = html.escape
    km = (f'<div style="color:#2E7D4F"><b>ห่างจากคุณประมาณ {places.format_km(p["_km"])}</b></div>'
          if p.get("_km") is not None else "")
    lines = "".join(f"<div><b>{label}:</b> {e(p[key])}</div>"
                    for label, key in (("ที่อยู่", "address"), ("เวลาทำการ", "hours"), ("รับ", "accepts"), ("โทร", "phone"))
                    if p.get(key))
    return ('<div style="font-family:sans-serif;font-size:13px;line-height:1.5;min-width:210px">'
            f'<div style="font-size:15px;font-weight:600">{e(p["name"])}</div>'
            f'<div style="color:#555">{e(p["type"])}</div>{km}{lines}'
            f'<div style="margin-top:6px"><a href="{places.maps_url(p)}" target="_blank">เปิดใน Google Maps</a>'
            f' &nbsp; <a href="{places.directions_url(p)}" target="_blank">นำทาง</a></div></div>')


pts = places.load_places()
if not pts:
    st.info("ยังไม่มีข้อมูลจุดรับขยะ ผู้ดูแลเพิ่มได้ที่หน้า Admin แท็บ \"จุดรับขยะ\"")
    st.stop()

# ---------- ตัวกรอง ----------
c1, c2 = st.columns([2, 3])
kinds = c1.multiselect("ประเภท", places.TYPES, placeholder="ทุกประเภท")
query = c2.text_input("ค้นหาชื่อหรือที่อยู่").strip().lower()
shown = [p for p in pts
         if (not kinds or p["type"] in kinds) and (not query or query in f"{p['name']} {p['address']}".lower())]
located = [p for p in shown if p["lat"] is not None]
unlocated = [p for p in shown if p["lat"] is None]

# ---------- ตำแหน่งของฉัน ----------
st.session_state.setdefault("my_pos", None)
with st.container(border=True):
    st.markdown("**ตำแหน่งของคุณ** (ใช้หาจุดที่ใกล้ที่สุด)")
    gcol, tcol = st.columns([1, 2])
    with gcol:
        if streamlit_geolocation:
            loc = streamlit_geolocation() or {}
            if loc.get("latitude") is not None and loc.get("longitude") is not None:
                here = (loc["latitude"], loc["longitude"])
                if st.session_state.get("_geo_last") != here:  # เพิ่งกดปุ่ม/ตำแหน่งเปลี่ยน
                    st.session_state._geo_last = here
                    st.session_state.my_pos = here
        else:
            st.caption("ติดตั้ง streamlit-geolocation เพื่อใช้ตำแหน่งปัจจุบัน")
    with tcol:
        pick = st.toggle("คลิกบนแผนที่เพื่อกำหนดตำแหน่งของฉัน",
                         help="ใช้เมื่อไม่อนุญาตตำแหน่งในเบราว์เซอร์ หรืออยากดูจุดใกล้สถานที่อื่น")
        if st.session_state.my_pos and st.button("ล้างตำแหน่งของฉัน"):
            st.session_state.my_pos = None
            st.rerun()
    st.caption("ตำแหน่งปัจจุบันต้องกดอนุญาตในเบราว์เซอร์ และใช้ได้เมื่อเปิดผ่าน localhost หรือ https "
               "ระบบใช้ตำแหน่งเพื่อคำนวณระยะทางเท่านั้น ไม่บันทึกลงฐานข้อมูล")

pos = st.session_state.my_pos
located = places.with_distance(located, *pos) if pos else located

# ---------- แผนที่ ----------
selected = None
if not located:
    st.info("จุดรับที่เลือกยังไม่มีพิกัด จึงแสดงบนแผนที่ไม่ได้ ดูรายละเอียดในรายการด้านล่าง")
elif folium is None:
    st.warning("ยังไม่ได้ติดตั้ง streamlit-folium จึงแสดงแผนที่แบบคลิกหมุดไม่ได้ (รัน pip install -r requirements.txt)")
    st.map(pd.DataFrame([{"lat": p["lat"], "lon": p["lng"]} for p in located]), size=60)
else:
    lats, lngs = [p["lat"] for p in located], [p["lng"] for p in located]
    center = list(pos) if pos else [sum(lats) / len(lats), sum(lngs) / len(lngs)]
    m = folium.Map(location=center, zoom_start=15 if (pos or len(located) == 1) else 13, control_scale=True)
    for p in located:
        folium.Marker([p["lat"], p["lng"]], tooltip=p["name"], popup=folium.Popup(popup_html(p), max_width=320),
                      icon=folium.Icon(color=ICON_COLORS.get(p["type"], "gray"), icon="trash")).add_to(m)
    if pos:
        folium.Marker(list(pos), tooltip="ตำแหน่งของคุณ",
                      icon=folium.Icon(color="darkblue", icon="user", prefix="fa")).add_to(m)
    elif len(located) > 1:
        m.fit_bounds([[min(lats), min(lngs)], [max(lats), max(lngs)]], padding=(30, 30))
    out = st_folium(m, height=440, use_container_width=True,
                    returned_objects=["last_object_clicked", "last_clicked"], key="dropmap") or {}
    if pick and out.get("last_clicked"):
        c = out["last_clicked"]
        new = (c["lat"], c["lng"])
        if st.session_state.get("_map_click_last") != new:
            st.session_state._map_click_last = new
            st.session_state.my_pos = new
            st.rerun()
    clk = out.get("last_object_clicked")
    if clk:
        best = min(located, key=lambda p: abs(p["lat"] - clk["lat"]) + abs(p["lng"] - clk["lng"]))
        if abs(best["lat"] - clk["lat"]) + abs(best["lng"] - clk["lng"]) < 1e-3:
            selected = best
    st.caption("สีหมุด: แดง = ขยะอันตราย, ม่วง = ขยะอิเล็กทรอนิกส์, เขียว = ธนาคารขยะ/รีไซเคิล, ส้ม = น้ำมันพืชใช้แล้ว")

# ---------- จุดที่เลือก / จุดใกล้คุณ ----------
if selected:
    st.subheader("จุดที่เลือก")
    st.markdown(place_card_html(selected), unsafe_allow_html=True)
if pos and located:
    st.subheader("จุดทิ้งที่ใกล้คุณที่สุด")
    st.caption("ระยะทางเป็นเส้นตรง ระยะเดินทางจริงอาจมากกว่า กดนำทางเพื่อดูเส้นทางใน Google Maps")
    st.markdown("".join(place_card_html(p) for p in located[:5]), unsafe_allow_html=True)
else:
    st.subheader(f"จุดรับทั้งหมด ({len(shown)} แห่ง)")
    if located:
        st.caption("ระบุตำแหน่งของคุณด้านบนเพื่อเรียงจากใกล้ไปไกล")
    st.markdown("".join(place_card_html(p) for p in sorted(shown, key=lambda p: (p["type"], p["name"]))),
                unsafe_allow_html=True)
if pos and unlocated:
    st.subheader("ยังไม่มีพิกัด")
    st.markdown("".join(place_card_html(p) for p in unlocated), unsafe_allow_html=True)
if not shown:
    st.info("ไม่พบจุดรับตามเงื่อนไขที่เลือก")
