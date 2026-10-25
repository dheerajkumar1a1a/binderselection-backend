"""Build the presentation deck for the Binder Selection Agent production UI."""
import os
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE

NAVY = RGBColor(0x0F, 0x17, 0x2A)
NAVY2 = RGBColor(0x1E, 0x29, 0x3B)
ACCENT = RGBColor(0x25, 0x63, 0xEB)
MUT = RGBColor(0x64, 0x74, 0x8B)
INK = RGBColor(0x0F, 0x17, 0x2A)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)

BLANK = prs.slide_layouts[6]


def add_title_bar(slide, title, subtitle=None):
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0),
                                 Inches(13.333), Inches(1.1))
    bar.fill.solid()
    bar.fill.fore_color.rgb = NAVY
    bar.line.fill.background()
    tf = bar.text_frame
    p = tf.paragraphs[0]
    p.text = title
    p.font.size = Pt(24)
    p.font.bold = True
    p.font.color.rgb = WHITE
    p.alignment = PP_ALIGN.LEFT
    tf.margin_left = Inches(0.4)
    if subtitle:
        p2 = tf.add_paragraph()
        p2.text = subtitle
        p2.font.size = Pt(12)
        p2.font.color.rgb = RGBColor(0x94, 0xA3, 0xB8)


def add_bullets(slide, items, left=0.6, top=1.4, width=12.0, size=18, bold_first=False):
    tb = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(5.6))
    tf = tb.text_frame
    tf.word_wrap = True
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = item
        p.font.size = Pt(size)
        p.font.color.rgb = INK
        p.space_after = Pt(8)
        if bold_first and ":" in item:
            run = p.runs[0]
            run.font.bold = True


def add_notes(slide, text):
    slide.notes_slide.notes_text_frame.text = text


def new_slide(title, subtitle=None):
    s = prs.slides.add_slide(BLANK)
    add_title_bar(s, title, subtitle)
    return s


# ---------- Slide 1: Title ----------
s = new_slide("Binder Selection Agent", "Production system of record for marine cargo placement")
tb = s.shapes.add_textbox(Inches(0.6), Inches(1.6), Inches(12), Inches(2.5))
tf = tb.text_frame
p = tf.paragraphs[0]
p.text = "From one-shot demo to a 6-phase production build"
p.font.size = Pt(28)
p.font.bold = True
p.font.color.rgb = NAVY
p2 = tf.add_paragraph()
p2.text = "AI never decides. A named human always does — with full provenance."
p2.font.size = Pt(18)
p2.font.color.rgb = MUT
p2.space_before = Pt(12)
p3 = tf.add_paragraph()
p3.text = "Local-first · FastAPI + HTMX · SQLite → Postgres · 188 tests green"
p3.font.size = Pt(13)
p3.font.color.rgb = MUT
p3.space_before = Pt(24)
add_notes(s, """Timing: 0:00–0:30
Open with the one-liner. Point at the screen: "this is not a demo anymore — it's a system of record."
Then transition to slide 2.""")


# ---------- Slide 2: The problem ----------
s = new_slide("The problem", "A one-shot demo is not a system of record")
add_bullets(s, [
    "The leadership demo ran the engine once and forgot everything.",
    "No persistence, no audit trail, no broker-facing surface.",
    "Underwriters had no way to ask for missing data and re-evaluate.",
    "Capacity was a static JSON file — reservations never happened.",
    "Provenance existed in the engine but never reached the viewer.",
])
add_notes(s, """Timing: 0:30–1:00
Frame the gap: the engine was always good; the product around it wasn't.
Ask the room: "how do we trust a recommendation we can't trace?" """)


# ---------- Slide 3: Architecture ----------
s = new_slide("Architecture", "Production wraps the engine — nothing duplicated")
# Draw boxes
boxes = [("Browser", 0.6, 1.6, 2.4, 1.0, ACCENT),
         ("FastAPI + Jinja", 3.4, 1.6, 3.0, 1.0, NAVY2),
         ("ui.app / nodes", 6.8, 1.6, 3.0, 1.0, NAVY2),
         ("SQLite / Postgres", 10.2, 1.6, 2.5, 1.0, NAVY2)]
for name, x, y, w, h, c in boxes:
    sh = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y),
                            Inches(w), Inches(h))
    sh.fill.solid()
    sh.fill.fore_color.rgb = c
    sh.line.fill.background()
    tf = sh.text_frame
    p = tf.paragraphs[0]
    p.text = name
    p.font.size = Pt(14)
    p.font.bold = True
    p.font.color.rgb = WHITE
    p.alignment = PP_ALIGN.CENTER
# arrows
for (x1, x2) in [(3.0, 3.4), (6.4, 6.8), (9.8, 10.2)]:
    arr = s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(x1), Inches(1.95),
                             Inches(x2 - x1), Inches(0.3))
    arr.fill.solid()
    arr.fill.fore_color.rgb = MUT
    arr.line.fill.background()
# data stores row
stores = [("Documents on disk\ndata/cases/<id>/", 0.6, 3.0, 3.0, 0.9),
          ("Capacity ledger\nJSON / Postgres", 4.0, 3.0, 3.0, 0.9),
          ("Rulesets\nversioned files", 7.4, 3.0, 2.6, 0.9),
          ("Outbox / SMTP\nnotifications", 10.4, 3.0, 2.3, 0.9)]
for name, x, y, w, h in stores:
    sh = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y),
                            Inches(w), Inches(h))
    sh.fill.solid()
    sh.fill.fore_color.rgb = RGBColor(0xE2, 0xE8, 0xF0)
    sh.line.color.rgb = MUT
    tf = sh.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = name
    p.font.size = Pt(11)
    p.font.color.rgb = INK
    p.alignment = PP_ALIGN.CENTER
add_bullets(s, [
    "Engine (ui.app / nodes) is imported, never re-implemented.",
    "One DATABASE_URL swaps SQLite for Postgres. No build step — server-rendered HTMX.",
], top=4.2, size=14)
add_notes(s, """Timing: 1:00–1:30
Emphasise: production is a thin wrapper. The engine is the same; persistence is what changed.""")


# ---------- Slide 4: The doctrine ----------
s = new_slide("The doctrine", "Four rules the system never breaks")
add_bullets(s, [
    "1. AI never decides. The LLM extracts facts; a named human always decides.",
    "2. Missing data becomes a named information request — never a silent Pass.",
    "3. Every fact carries provenance: source document + quote, or feed + licence + timestamp.",
    "4. Everything is append-only. Evaluations, decisions, rounds — never rewritten. A Case never forks.",
], size=17)
add_notes(s, """Timing: 1:30–2:00
This is the slide to land. Read the four rules slowly. Then: "everything you see next exists to honour these." """)


# ---------- Slide 5: Six phases ----------
s = new_slide("Six phases, shipped", "v1.10.0 → v1.16.0")
phases = [
    ("1", "Workboard + persistent Cases", "v1.10.0"),
    ("2", "Provenance viewer + docs on disk", "v1.10.1"),
    ("3", "Info-requests + broker portal + successors", "v1.11.0"),
    ("4", "Rules console (maker-checker) + file picker", "v1.12.0"),
    ("5", "Reference-data facts layer", "v1.13.0"),
    ("6", "Live capacity desk + MI + retention", "v1.14.0"),
]
y = 1.5
for num, name, tag in phases:
    sh = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(0.6), Inches(y), Inches(0.5), Inches(0.5))
    sh.fill.solid()
    sh.fill.fore_color.rgb = ACCENT
    sh.line.fill.background()
    tf = sh.text_frame
    p = tf.paragraphs[0]
    p.text = num
    p.font.size = Pt(14)
    p.font.bold = True
    p.font.color.rgb = WHITE
    p.alignment = PP_ALIGN.CENTER
    tb = s.shapes.add_textbox(Inches(1.3), Inches(y), Inches(9.5), Inches(0.5))
    tf2 = tb.text_frame
    p2 = tf2.paragraphs[0]
    p2.text = name
    p2.font.size = Pt(16)
    p2.font.color.rgb = INK
    tb2 = s.shapes.add_textbox(Inches(11.0), Inches(y), Inches(1.8), Inches(0.5))
    tf3 = tb2.text_frame
    p3 = tf3.paragraphs[0]
    p3.text = tag
    p3.font.size = Pt(12)
    p3.font.color.rgb = MUT
    p3.alignment = PP_ALIGN.RIGHT
    y += 0.85
add_notes(s, """Timing: 2:00–2:30
Point at phase 3 and 6 — those are the two that change the business story.""")


# ---------- Slide 6: Differentiators ----------
s = new_slide("What makes it different", "Three things the demo never had")
add_bullets(s, [
    "Broker portal — restricted view: ask-lists, their documents, outcome letters. Never scores, rules, or other binders.",
    "Maker-checker rulesets — a proposal needs a different approver; effective-dating means no surprise changes.",
    "Live capacity desk — reservations expire in 30 days; alerts at 80%/90%; stale reservations can't silently eat a binder.",
], size=16)
add_notes(s, """Timing: 2:30–3:00
Then: "let me show you." Transition to the live demo.""")


# ---------- Slide 7: Demo transition ----------
s = new_slide("Live demo", "10 minutes · 12 scenes")
add_bullets(s, [
    "1. Login & workboard",
    "2. Create a case (sample + real file upload)",
    "3. Run evaluation — verdict, facts, per-binder results",
    "4. Provenance viewer — tabbed, multi-document, quote highlights",
    "5. Reference data — feeds with licence + timestamp",
    "6. Underwriter decision — accept / override / refer back + letter",
    "7. Request round — issue, broker answers, submit, successor eval, delta",
    "8. Rules console — propose, dry-run, four-eyes approve",
    "9. Capacity desk + admin surfaces",
], size=15)
tb = s.shapes.add_textbox(Inches(0.6), Inches(6.0), Inches(12), Inches(0.8))
tf = tb.text_frame
p = tf.paragraphs[0]
p.text = "Key takeaway: AI never decides. A named human always does — with full provenance."
p.font.size = Pt(16)
p.font.bold = True
p.font.color.rgb = ACCENT
add_notes(s, """Timing: 3:00 → live demo (10 min)
Credentials: admin/change-me-admin · uw/change-me-uw · broker/change-me-broker
Run through the demo script in TaskNotes/binderselection-demo-script.md.""")


out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "binderselection-deck.pptx")
prs.save(out)
print("saved", out)
print("slides:", len(prs.slides))
