"""Turns guide/md/*.md into guide/data/lessons.js (+ lessons.json for audio).

Run from anywhere:  python guide/build.py

Markdown dialect (small on purpose):
  front matter     title / station / role / minutes   (between --- lines)
  ## heading       section
  > [!eli5] text   callout. kinds: eli5, path, why, watch, honest
  {{widget:name}}  interactive widget (implemented in assets/widgets.js)
  ```quiz          quiz block (Q: / - wrong / * right / ? explanation)
  ```py title="x"  code block
  | a | b |        table
Every paragraph, list item, callout and heading gets a narration id ("n") so
the page can read it aloud and highlight it, and make_audio.py can render the
same text with a local TTS model.
"""

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
MD_DIR = HERE / "md"
OUT_JS = HERE / "data" / "lessons.js"
OUT_JSON = HERE / "data" / "lessons.json"
AUDIO_DIR = HERE / "audio"

HEBREW_RUN = re.compile(r"[֐-׿][֐-׿\s\"'.,!?()\-:;0-9A-Za-z]*[֐-׿]|[֐-׿]")


def say_text(md: str) -> str:
    """Markdown -> what a voice should read."""
    t = md
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)          # links
    t = re.sub(r"\*\*([^*]+)\*\*", r"\1", t)                 # bold
    t = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"\1", t)        # italics
    t = re.sub(r"`([^`]+)`", lambda m: m.group(1).replace("_", " "), t)
    t = HEBREW_RUN.sub("a Hebrew phrase", t)
    t = t.replace("->", "to").replace("→", "to").replace("≤", "at most").replace("≥", "at least")
    t = t.replace("&", "and").replace("/", " or ")
    t = re.sub(r"\bLLM\b", "L L M", t)
    t = re.sub(r"\bSQLite\b", "S Q Lite", t)
    t = re.sub(r"\bPOL-(\d+)", r"policy \1", t)
    t = re.sub(r"\bORD-(\d+)", r"order \1", t)
    t = re.sub(r"\bSR-(\d+)", r"request \1", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def parse_front(lines):
    meta = {}
    if lines and lines[0].strip() == "---":
        i = 1
        while i < len(lines) and lines[i].strip() != "---":
            k, _, v = lines[i].partition(":")
            meta[k.strip()] = v.strip()
            i += 1
        return meta, lines[i + 1:]
    return meta, lines


def parse_quiz(body):
    questions, cur = [], None
    for raw in body:
        line = raw.rstrip()
        if line.startswith("Q:"):
            cur = {"q": line[2:].strip(), "options": [], "answer": None, "why": ""}
            questions.append(cur)
        elif cur and line.startswith("- "):
            cur["options"].append(line[2:].strip())
        elif cur and line.startswith("* "):
            cur["answer"] = len(cur["options"])
            cur["options"].append(line[2:].strip())
        elif cur and line.startswith("?"):
            cur["why"] = line[1:].strip()
    return questions


def parse_blocks(lines):
    blocks, i, n = [], 0, 0

    def nid():
        nonlocal n
        n += 1
        return n - 1

    para = []

    def flush():
        if para:
            text = " ".join(s.strip() for s in para)
            blocks.append({"t": "p", "md": text, "say": say_text(text), "n": nid()})
            para.clear()

    while i < len(lines):
        line = lines[i].rstrip("\n")
        s = line.strip()
        if s.startswith("```"):
            flush()
            info = s[3:].strip()
            body = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                body.append(lines[i].rstrip("\n"))
                i += 1
            lang = info.split()[0] if info else ""
            if lang == "quiz":
                blocks.append({"t": "quiz", "questions": parse_quiz(body)})
            else:
                m = re.search(r'title="([^"]*)"', info)
                blocks.append({"t": "code", "lang": lang, "title": m.group(1) if m else "", "text": "\n".join(body)})
        elif not s:
            flush()
        elif s.startswith("{{widget:"):
            flush()
            blocks.append({"t": "widget", "name": s[9:-2].strip()})
        elif s.startswith("## "):
            flush()
            txt = s[3:]
            blocks.append({"t": "h2", "md": txt, "say": say_text(txt), "n": nid()})
        elif s.startswith("> [!"):
            flush()
            m = re.match(r">\s*\[!(\w+)\]\s*(.*)", s)
            body = m.group(2)
            while i + 1 < len(lines) and lines[i + 1].strip().startswith(">") and not lines[i + 1].strip().startswith("> [!"):
                i += 1
                body += " " + lines[i].strip().lstrip(">").strip()
            spoken = {"eli5": "Like you're five. ", "path": "The path we took. ", "why": "Why we chose this. ", "honest": "An honest note. ", "watch": "Watch out. "}
            blocks.append({"t": "callout", "kind": m.group(1), "md": body, "say": spoken.get(m.group(1), "") + say_text(body), "n": nid()})
        elif s.startswith("|"):
            flush()
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                row = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in row):
                    rows.append(row)
                i += 1
            i -= 1
            blocks.append({"t": "table", "rows": rows})
        elif re.match(r"(-|\d+\.)\s", s):
            flush()
            ordered = bool(re.match(r"\d+\.", s))
            items = []
            while i < len(lines) and re.match(r"(-|\d+\.)\s", lines[i].strip()):
                txt = re.sub(r"^(-|\d+\.)\s+", "", lines[i].strip())
                items.append({"md": txt, "say": say_text(txt), "n": nid()})
                i += 1
            i -= 1
            blocks.append({"t": "ol" if ordered else "ul", "items": items})
        else:
            para.append(s)
        i += 1
    flush()
    return blocks


def main():
    lessons = []
    for path in sorted(MD_DIR.glob("*.md")):
        meta, body = parse_front(path.read_text(encoding="utf-8").splitlines())
        lesson_id = path.stem
        blocks = parse_blocks(body)
        narr = [b for b in blocks if "n" in b] + [it for b in blocks if b["t"] in ("ul", "ol") for it in b["items"]]
        count = max((x["n"] for x in narr), default=-1) + 1
        has_audio = (AUDIO_DIR / lesson_id / "0.wav").exists() or (AUDIO_DIR / lesson_id / "0.mp3").exists()
        ext = "mp3" if (AUDIO_DIR / lesson_id / "0.mp3").exists() else "wav"
        lessons.append({
            "id": lesson_id,
            "title": meta.get("title", lesson_id),
            "station": meta.get("station", ""),
            "role": meta.get("role", "none"),
            "minutes": int(meta.get("minutes", "5")),
            "blocks": blocks,
            "narrationCount": count,
            "audio": ext if has_audio else None,
        })
    OUT_JS.write_text("window.LESSONS = " + json.dumps(lessons, ensure_ascii=False, indent=1) + ";\n", encoding="utf-8")
    OUT_JSON.write_text(json.dumps(lessons, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"built {len(lessons)} lessons -> {OUT_JS.relative_to(HERE.parent)}")


if __name__ == "__main__":
    main()
