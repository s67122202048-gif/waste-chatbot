"""ชุดทดสอบคุณภาพของแชทบอท
  python evaluate.py          ทดสอบการค้นหาอย่างเดียว (ไม่เสียค่า API)
  python evaluate.py --llm    ถามบอทจริง ตรวจสีถังและคำสำคัญในคำตอบ (เสียค่า API)
รูปแบบข้อใน eval/questions.json:
  q=คำถาม  ctx=ข้อความที่ต้องค้นเจอ  bin=สีถังที่ต้องได้ (ตรงชุดพอดี)
  has=คำที่ต้องมีในคำตอบทุกคำ  any=มีอย่างน้อยหนึ่งคำ  critical=ข้อสำคัญด้านความปลอดภัย"""
import argparse
import csv
import json
import sys
import time
from datetime import datetime
from pathlib import Path

QUESTIONS = Path(__file__).parent / "eval" / "questions.json"


def load_questions(path=QUESTIONS):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def run_eval(rag, items, k=4, use_llm=False, progress=None):
    from style import split_bins
    rows = []
    for i, it in enumerate(items, 1):
        q, fails, answer = it["q"], [], ""
        ctx = " ".join(h["text"] for h in rag.retrieve(q, k=k))
        for s in it.get("ctx", []):
            if s not in ctx:
                fails.append(f"ค้นไม่เจอ '{s}'")
        if use_llm:
            try:
                colors, answer = split_bins(rag.answer(q, k=k)["text"])
            except Exception as e:
                fails.append(f"error: {e}")
            else:
                exp = it.get("bin")
                if exp is not None and set(colors) != set(exp):
                    fails.append(f"สีถังได้ {colors or 'ไม่ระบุ'} ควรเป็น {exp}")
                fails += [f"คำตอบไม่มี '{s}'" for s in it.get("has", []) if s not in answer]
                if it.get("any") and not any(s in answer for s in it["any"]):
                    fails.append(f"คำตอบไม่มีคำใดใน {it['any']}")
            time.sleep(0.2)
        rows.append({"no": i, "question": q, "critical": bool(it.get("critical")), "pass": not fails,
                     "problems": "; ".join(fails), "answer": answer.replace("\n", " ")[:300]})
        if progress:
            progress(i / len(items))
    return rows


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", action="store_true")
    ap.add_argument("-k", type=int, default=4)
    ap.add_argument("--file", default=str(QUESTIONS))
    a = ap.parse_args()

    from rag import WasteRAG
    rag = WasteRAG()
    if a.llm and rag.client is None:
        sys.exit("ต้องตั้งค่า API key ใน .env ก่อนใช้ --llm")
    rows = run_eval(rag, load_questions(a.file), k=a.k, use_llm=a.llm)
    for r in rows:
        print(("PASS" if r["pass"] else "FAIL"), ("[สำคัญ]" if r["critical"] else "       "), r["question"],
              "" if r["pass"] else f"-> {r['problems']}")
    passed = sum(r["pass"] for r in rows)
    crit = [r for r in rows if r["critical"] and not r["pass"]]
    print(f"\nผ่าน {passed}/{len(rows)} ({passed / len(rows):.0%})  ข้อสำคัญที่ไม่ผ่าน {len(crit)}")
    out = Path(__file__).parent / "eval" / "results"
    out.mkdir(exist_ok=True)
    f = out / f"{'llm' if a.llm else 'retrieval'}_{datetime.now():%Y%m%d_%H%M%S}.csv"
    with open(f, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print("บันทึกผลที่", f)
    sys.exit(1 if crit else 0)


if __name__ == "__main__":
    main()
