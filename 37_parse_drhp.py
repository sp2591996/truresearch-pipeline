"""
37_parse_drhp.py
-------------------------------------------------------------------
Reads DRHP (Draft Red Herring Prospectus) PDFs out of a folder,
extracts the "core details" of each IPO -- qualitative text (what the
company does, what its industry looks like, why it's raising money,
its top risks) and quantitative data (a small financial summary
table) -- and writes them onto that IPO's row in `ipo_assessments`.

WHY THIS IS BUILT THE WAY IT IS (read this before changing anything)
-------------------------------------------------------------------
Every SEBI-registered DRHP follows the same *overall* structure
(mandated by SEBI's ICDR regulations: General -> Risk Factors ->
Introduction -> About the Company -> Financial Information -> ...),
but the *exact wording* of section titles, the page layout, and where
things sit differ company to company, because each is prepared by a
different merchant banker / printer. Avdhoot was explicit about this:
"there would be some differences in the formats... make sure your
code takes that into account." So this script never hardcodes a page
number. Instead, for every document it:

  1. Finds that document's own Table of Contents (every DRHP has one)
     and reads out (section title text, printed page number) pairs.
  2. Works out that document's own "page offset" -- the difference
     between a PDF page index and the printed page number shown in
     the document itself (the first few pages -- cover, disclaimers --
     are usually unnumbered, so PDF page 4 might be printed page "1").
  3. Uses fuzzy text matching (not an exact string match) to find
     which TOC entry corresponds to each section we care about, so
     "Offer Document Summary" still matches something titled "Summary
     of the Offer Document" in a different company's DRHP.
  4. Extracts text from that section's page range only.

The single richest target is the short "Offer Document Summary"
section that SEBI requires near the front of every DRHP -- it already
contains a condensed business summary, industry summary, objects-of-
the-offer figures, a compact financial summary table, and (often) a
top-N risk factors table, all in a few pages. This script leans on
that section first, and falls back to scanning the fuller "Our
Business" / "Industry Overview" / "Risk Factors" sections (using the
same TOC-driven lookup) only to fill in anything the summary didn't
have or to pull a couple of extra paragraphs.

HONESTY RULES (same as every other script in this pipeline)
-------------------------------------------------------------------
- If a section can't be confidently located in a given document, its
  column is left NULL -- never guessed or left as a truncated,
  misleading fragment.
- This script never fabricates numbers. The financial summary table
  is only written if a table matching known financial-summary column
  headers is actually found on the page.
- One PDF failing to parse must not stop the rest of the folder.

WHAT YOU NEED BEFORE RUNNING THIS
-------------------------------------------------------------------
1. Run 36_add_drhp_columns.sql once in the Supabase SQL editor (adds
   the new columns this script writes to).
2. Install the PDF-reading library (one-time):
       pip install pdfplumber
3. Put your downloaded DRHP PDFs into one folder, e.g.:
       TrueResearch Code/drhp_pdfs/
   Any file names are fine -- this script reads each PDF's own cover
   page to figure out which company it is, then matches that against
   the `ipos.company_name` already in the database. It does NOT rely
   on the filename.

HOW TO RUN
-------------------------------------------------------------------
    python 37_parse_drhp.py drhp_pdfs

(replace drhp_pdfs with wherever you put the folder of PDFs)

For every PDF it will print which company it matched to, which
sections it found, and what it wrote -- so you can sanity check the
first document (Pranav Constructions) before running it against the
rest of the folder.
-------------------------------------------------------------------
"""
import difflib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from db_client import get_client

try:
    import pdfplumber
except ImportError:
    print("Missing dependency. Run:  pip install pdfplumber")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Canonical sections we're looking for, and the fuzzy keywords/phrases that
# should match that section's title in ANY DRHP's own Table of Contents,
# however that particular document happens to word it.
# ---------------------------------------------------------------------------
SECTION_TARGETS = {
    "offer_summary": [
        "offer document summary",
        "summary of the offer document",
        "summary of offer document",
        "prospectus summary",
    ],
    "objects_of_offer": [
        "objects of the offer",
        "objects of the issue",
        "use of proceeds",
    ],
    "industry_overview": [
        "industry overview",
        "overview of the industry",
        "industry description",
    ],
    "our_business": [
        "our business",
        "business overview",
        "description of business",
    ],
    "risk_factors": [
        "risk factors",
    ],
}

# Column headers that show up in a DRHP's own "Select Financial
# Information" / financial summary table -- used to recognise the right
# table on a page (a page can have several tables; we only want this one).
FINANCIAL_TABLE_KEYWORDS = [
    "revenue from operations",
    "restated profit",
    "profit for the period",
    "profit after tax",
    "earnings per share",
    "net asset value",
    "net worth",
    "total borrowings",
]

TOC_LINE_RE = re.compile(r"^(.*?)[\.\s]{4,}(\d{1,4})\s*$")


def normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().lower()


def fuzzy_match_score(candidate: str, targets: list[str]) -> float:
    candidate = normalize(candidate)
    best = 0.0
    for t in targets:
        best = max(best, difflib.SequenceMatcher(None, candidate, t).ratio())
        # also reward a straightforward substring containment, which
        # catches cases like "SUMMARY OF THE OFFER DOCUMENT" containing
        # "offer document" as a strong signal even if ratio() is middling
        if t in candidate or candidate in t:
            best = max(best, 0.85)
    return best


def find_toc_pages(pdf) -> list[int]:
    """A DRHP's Table of Contents can span more than one page. Look at
    the first ~15 pages (it's always near the front) for pages whose
    text contains a heading like 'TABLE OF CONTENTS'."""
    toc_pages = []
    for i, page in enumerate(pdf.pages[:15]):
        text = page.extract_text() or ""
        if re.search(r"table of contents", text, re.IGNORECASE):
            toc_pages.append(i)
            continue
        # Some DRHPs title this page just "CONTENTS" rather than "TABLE
        # OF CONTENTS". Only treat that as a match when it's a short,
        # standalone heading line AND the page actually looks like a
        # listing (several "<title> ... <page number>" lines) -- this
        # avoids false-positives on body text that happens to mention
        # "contents" in a sentence.
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        if lines and re.fullmatch(r"contents", lines[0], re.IGNORECASE):
            hits = sum(1 for line in lines if TOC_LINE_RE.match(line))
            if hits >= 3:
                toc_pages.append(i)
    # the page(s) immediately after a "TABLE OF CONTENTS" heading page
    # often continue the listing without repeating the heading -- include
    # up to 3 pages following the last hit, stopping once a page clearly
    # stops looking like a TOC (few or no "<title> ... <number>" lines).
    if toc_pages:
        last = toc_pages[-1]
        for j in range(last + 1, min(last + 4, 15)):
            text = pdf.pages[j].extract_text() or ""
            hits = sum(1 for line in text.splitlines() if TOC_LINE_RE.match(line.strip()))
            if hits >= 3:
                toc_pages.append(j)
            else:
                break
    return toc_pages


def extract_toc_entries(pdf, toc_pages: list[int]) -> list[tuple[str, int]]:
    """Returns [(title, printed_page_number), ...] found on the TOC pages."""
    entries = []
    for i in toc_pages:
        text = pdf.pages[i].extract_text() or ""
        for line in text.splitlines():
            m = TOC_LINE_RE.match(line.strip())
            if not m:
                continue
            title, page_num = m.group(1).strip(), m.group(2)
            if len(title) < 3:
                continue
            try:
                entries.append((title, int(page_num)))
            except ValueError:
                continue
    return entries


def detect_page_offset(pdf, toc_entries: list[tuple[str, int]], toc_pages: list[int]) -> int | None:
    """Works out (pdf_page_index - printed_page_number) for this document
    by finding an early TOC entry's printed page number stamped as a
    plain digit somewhere near the bottom/top of a PDF page, and seeing
    how far into the PDF that page actually is.

    Different DRHPs print folios differently (bottom-center, bottom-right,
    top-right, sometimes as "1" alone, sometimes "Page 1 of 469") so this
    tries a few candidate offsets (found from where the TOC pages
    themselves sit) and confirms by checking that the printed page number
    appears somewhere on that candidate PDF page.
    """
    if not toc_entries:
        return None

    # Sort by printed page number and only look at genuinely early
    # sections -- offset detection is unreliable deep into the document.
    early_entries = sorted(toc_entries, key=lambda e: e[1])[:8]
    search_start = max(toc_pages) + 1 if toc_pages else 0

    for _, printed_page in early_entries:
        if printed_page <= 0:
            continue
        # try a range of plausible offsets (front matter is rarely more
        # than ~15 unnumbered pages before numbering starts at "1")
        for offset in range(0, 16):
            pdf_index = printed_page - 1 + offset
            if pdf_index < search_start or pdf_index >= len(pdf.pages):
                continue
            text = pdf.pages[pdf_index].extract_text() or ""
            # look for the printed page number standing alone near the
            # start or end of the page's text (a folio, not just any
            # number that happens to appear in a paragraph)
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            edge_lines = lines[:2] + lines[-2:]
            for l in edge_lines:
                if re.fullmatch(rf"(page\s+)?{printed_page}(\s+of\s+\d+)?", l, re.IGNORECASE):
                    return offset
    return None


def locate_sections(toc_entries: list[tuple[str, int]], offset: int, total_pdf_pages: int) -> dict:
    """For each canonical target, finds the best-matching TOC entry and
    returns its (start_pdf_page, end_pdf_page) range -- end is the start
    of the next TOC entry after it (by printed page order), or the end
    of the document."""
    sorted_entries = sorted(toc_entries, key=lambda e: e[1])
    located = {}

    for key, phrases in SECTION_TARGETS.items():
        best_score, best_entry_idx = 0.0, None
        for idx, (title, _) in enumerate(sorted_entries):
            score = fuzzy_match_score(title, phrases)
            if score > best_score:
                best_score, best_entry_idx = score, idx
        if best_entry_idx is not None and best_score >= 0.55:
            title, printed_page = sorted_entries[best_entry_idx]
            start = printed_page - 1 + offset
            end = total_pdf_pages - 1
            if best_entry_idx + 1 < len(sorted_entries):
                next_printed = sorted_entries[best_entry_idx + 1][1]
                end = next_printed - 1 + offset - 1
            end = max(start, min(end, start + 40))  # cap runaway sections
            located[key] = {
                "matched_title": title,
                "score": round(best_score, 2),
                "start": max(0, start),
                "end": min(total_pdf_pages - 1, end),
            }
    return located


def extract_section_text(pdf, start: int, end: int, max_pages: int = 12) -> str:
    parts = []
    for i in range(start, min(end + 1, start + max_pages)):
        if 0 <= i < len(pdf.pages):
            t = pdf.pages[i].extract_text() or ""
            parts.append(t)
    return "\n".join(parts).strip()


# The "Offer Document Summary" section is a SEBI-mandated template --
# every DRHP breaks it into roughly this same fixed sequence of
# sub-topics (only the free-text content in between differs company to
# company). These phrases mark where ONE sub-topic ends and the next
# begins, even though they're printed in ordinary title case rather
# than ALL CAPS -- so a naive "all-caps line = heading" check (which is
# right for the document's main chapter titles) misses them entirely
# and lets extraction run straight through into the next topic.
_SUMMARY_SUBSECTION_BOUNDARIES = [
    "summary of primary business",
    "primary business of our company",
    "summary of the industry",
    "industry in which our company operates",
    "names of the promoter",
    "offer size",
    "objects of the offer",
    "objects of the issue",
    "aggregate pre-offer shareholding",
    "select financial information",
    "qualifications of the statutory auditor",
    "summary of outstanding litigation",
    "summary of contingent liabilities",
    "risk factors",
    "average cost of acquisition",
    "weighted average cost of acquisition",
]

# Standard DRHP legal/administrative boilerplate that shows up as the FIRST
# paragraph under almost every section heading (definitions of "we"/"our",
# forward-looking-statement disclaimers, "who prepared this industry
# report and why" notices, cross-references to other sections). None of
# this is the actual business/industry content, so paragraphs matching
# these markers are skipped in favour of the real content that follows.
_BOILERPLATE_MARKERS = [
    "unless otherwise stated",
    "forward-looking statement",
    "forward looking statement",
    "references in this section",
    "prospective investors should read",
    "commissioned",
    "please refer to",
    "in compliance with applicable law",
    "certain conventions",
    "not a recommendation to invest",
    "should be read in conjunction with",
    "read this section in conjunction with",
]


def _looks_like_boilerplate(paragraph: str) -> bool:
    norm = normalize(paragraph)
    return any(marker in norm for marker in _BOILERPLATE_MARKERS)


def _is_heading_boundary(stripped_line: str) -> bool:
    """True if this short line looks like the START of a new topic --
    either one of the known Offer Document Summary sub-headings, or a
    mostly-capitalised ("ALL CAPS") chapter-title-style line."""
    if not stripped_line or len(stripped_line) >= 120:
        return False
    norm = normalize(stripped_line)
    if any(b in norm for b in _SUMMARY_SUBSECTION_BOUNDARIES):
        return True
    letters = [c for c in stripped_line if c.isalpha()]
    if letters and sum(c.isupper() for c in letters) / len(letters) > 0.8 and len(stripped_line) < 100:
        return True
    return False


def _split_paragraphs_after(lines: list[str], start_idx: int, max_paragraphs: int = 8) -> list[list[str]]:
    """Groups the lines after start_idx into paragraphs -- split at a
    blank line OR at the start of the next known sub-heading/topic
    (see _is_heading_boundary) -- stopping once max_paragraphs have
    been collected."""
    paragraphs: list[list[str]] = []
    current: list[str] = []
    for l in lines[start_idx:]:
        stripped = l.strip()
        if not stripped:
            if current:
                paragraphs.append(current)
                current = []
                if len(paragraphs) >= max_paragraphs:
                    break
            continue
        if _is_heading_boundary(stripped):
            if current:
                paragraphs.append(current)
            break
        current.append(stripped)
        if len(paragraphs) >= max_paragraphs:
            break
    else:
        if current:
            paragraphs.append(current)
    if current and current not in paragraphs:
        paragraphs.append(current)
    return paragraphs[:max_paragraphs]


def extract_paragraph_after_heading(text: str, heading_phrases: list[str], max_chars: int = 1200) -> str | None:
    """Finds a heading-like line matching one of the phrases and returns
    the first substantive (non-boilerplate) paragraph that follows it,
    stopping at the next sub-heading/topic rather than running on into
    unrelated content."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        norm = normalize(line)
        # Skip lines that are clearly a "see also" cross-reference list
        # (e.g. `...see "Our Business", "Industry Overview"... on pages
        # 30, 65, ... respectively.`) rather than an actual section
        # heading -- these mention several section names close together
        # and would otherwise fool every target into matching the same
        # boilerplate line.
        if '"' in stripped or "”" in stripped or "“" in stripped:
            continue
        if "respectively" in norm or re.search(r"\bpages?\b", norm):
            continue
        matched_phrase = next((p for p in heading_phrases if p in norm), None)
        if not matched_phrase:
            continue
        # The matched phrase should make up most of the line's words --
        # a real heading is close to just the phrase itself (maybe with
        # a number or "Summary of" prefix), not a fragment inside a much
        # longer sentence.
        phrase_word_count = len(matched_phrase.split())
        line_word_count = len(norm.split())
        if line_word_count > 0 and phrase_word_count / line_word_count < 0.35:
            continue
        if len(stripped) >= 120:
            continue

        paragraphs = _split_paragraphs_after(lines, i + 1)
        for idx, para_lines in enumerate(paragraphs):
            para_text = " ".join(para_lines).strip()
            if not para_text or _looks_like_boilerplate(para_text):
                continue
            combined = para_text
            if len(combined) < 300 and idx + 1 < len(paragraphs):
                nxt = " ".join(paragraphs[idx + 1]).strip()
                if nxt and not _looks_like_boilerplate(nxt):
                    combined = (combined + " " + nxt).strip()
            return combined[:max_chars].strip()
    return None


def _looks_like_risk_sentence(s: str) -> bool:
    """A real risk-factor item is a prose sentence describing a business
    risk, NOT a numbered row from some other table (shareholder lists,
    litigation counts, financial figures) that happens to share the same
    '1. ...', '2. ...' numbering style. Filters those false positives out."""
    if "[" in s and "]" in s:  # placeholder markers like "[●]", common in tables
        return False
    if re.search(r"\d{1,3}(,\d{3})+", s):  # formatted large numbers (share counts, amounts)
        return False
    # NOTE: deliberately NOT rejecting sentences just for citing several
    # bare numbers/percentages -- real risk factors routinely do (e.g.
    # "we derived 46.86%, 46.79% and 6.52% of our revenue from..."), so
    # that would throw out genuine risks. Formatted large numbers and
    # placeholder brackets (both checked above) are what actually mark a
    # table row.
    letters = sum(c.isalpha() for c in s)
    if len(s) == 0 or letters / len(s) < 0.6:  # prose should be mostly letters, not digits/punctuation
        return False
    if len(s.split()) < 6:  # a real risk statement is a full sentence, not a short label
        return False
    norm = normalize(s)
    # Reject financial-table footnote/definition sentences (e.g. "Net
    # Worth is defined as...", "Total borrowings include current and
    # non-current borrowings.") -- these are genuine prose, pass every
    # check above, and can sit right next to a real numbered risk list
    # in the document, but they're glossary notes, not risks.
    definition_markers = [
        "is defined as",
        "is calculated as",
        "as per regulation",
        "regulation 2(1)",
        "sebi icdr regulations as",
        "shall not exceed",
    ]
    if any(marker in norm for marker in definition_markers):
        return False
    # A real DRHP risk factor is, without exception in practice, phrased
    # in terms of the company itself ("We...", "Our...", "...our
    # business/operations/revenue...") -- financial-note definitions
    # never are. Requiring this weeds out any other stray numbered-list
    # false positive that slips past the checks above. Some documents'
    # extracted text splits these words with a stray space ("W e", "Ou
    # r") -- tolerate one optional space so those aren't misread as not
    # containing "we"/"our" at all.
    if not re.search(r"\bw\s?e\b|\bou\s?r\b|\bus\b", norm):
        return False
    return True


def extract_top_risks(text: str, max_items: int = 10) -> list[str] | None:
    """Looks for a numbered list of risk factors (the summary section's
    condensed 'top N risks' table, or a numbered list at the start of the
    full Risk Factors section)."""
    risks = []
    last_num = None  # the raw printed number of the last item we ACCEPTED
    # matches lines like "1. Some risk text..." or "1 Some risk text"
    pattern = re.compile(r"^\s*(\d{1,2})[\.\)]\s+(.{15,400})$")
    for line in text.splitlines():
        m = pattern.match(line.strip())
        if m:
            num = int(m.group(1))
            item_text = m.group(2).strip()
            if not _looks_like_risk_sentence(item_text):
                # Not a real risk sentence (likely a different numbered
                # table entirely, e.g. financial-note footnotes that
                # happen to share this document's numbering run) --
                # ignore this line WITHOUT resetting what we've already
                # collected, since a real risk list can have the odd
                # non-risk line interleaved in the raw extracted text.
                continue
            if last_num is None or num == last_num + 1:
                # Continues the sequence we're already building (or is
                # the very first accepted item, whatever its own number).
                risks.append(item_text)
                last_num = num
                if len(risks) >= max_items:
                    break
            elif num == 1:
                # A fresh list starting over from 1 -- e.g. we'd
                # accidentally started collecting from an unrelated
                # earlier list; restart clean with this one.
                risks = [item_text]
                last_num = 1
    # A real DRHP risk-factor list is always a substantial list (SEBI's
    # "top risks" summary tables and full Risk Factors chapters both run
    # well past 5 items) -- requiring at least 5 sequential, prose-like
    # matches (rather than 3) filters out short false-positive numbered
    # lists picked up from unrelated tables (litigation notes, etc.)
    # elsewhere in the document, leaving the field honestly NULL instead.
    return risks if len(risks) >= 5 else None


def extract_financial_summary(pdf, start: int, end: int) -> dict | None:
    """Scans the given page range's tables for one whose header row
    contains the known 'Select Financial Information' style columns, and
    returns it as {row_label: {col_label: value}}. Returns None (never a
    fabricated/empty guess) if no matching table is found."""
    for i in range(start, min(end + 1, start + 12)):
        if not (0 <= i < len(pdf.pages)):
            continue
        try:
            tables = pdf.pages[i].extract_tables()
        except Exception:
            continue
        for table in tables or []:
            flat = normalize(" ".join(str(c) for row in table for c in row if c))
            if sum(kw in flat for kw in FINANCIAL_TABLE_KEYWORDS) >= 2:
                result = {}
                header = table[0] if table else []
                for row in table[1:]:
                    if not row or not row[0]:
                        continue
                    label = str(row[0]).strip()
                    if not label:
                        continue
                    values = [str(c).strip() if c else None for c in row[1:]]
                    result[label] = values
                if result:
                    return {"columns": [str(h).strip() if h else "" for h in header[1:]], "rows": result}
    return None


def match_company(cover_text: str, ipos: list[dict]) -> dict | None:
    cover_norm = normalize(cover_text)[:3000]
    best, best_score = None, 0.0
    for ipo in ipos:
        name = normalize(ipo.get("company_name") or "")
        if not name:
            continue
        if name in cover_norm:
            score = 1.0
        else:
            score = difflib.SequenceMatcher(None, name, cover_norm[:len(name) + 40]).ratio()
        if score > best_score:
            best_score, best = score, ipo
    return best if best_score >= 0.6 else None


def parse_one_pdf(path: Path, ipos: list[dict]) -> dict | None:
    print(f"\n--- {path.name} ---")
    with pdfplumber.open(str(path)) as pdf:
        cover_text = "\n".join((pdf.pages[i].extract_text() or "") for i in range(min(3, len(pdf.pages))))
        ipo = match_company(cover_text, ipos)
        if not ipo:
            print("  Could not confidently match this PDF to a company already in the `ipos` table. Skipping.")
            return None
        print(f"  Matched to: {ipo['company_name']} (symbol={ipo.get('symbol')})")

        toc_pages = find_toc_pages(pdf)
        if not toc_pages:
            print("  Could not find a Table of Contents page. Skipping this document.")
            return None
        toc_entries = extract_toc_entries(pdf, toc_pages)
        if not toc_entries:
            print("  Table of Contents page found, but couldn't read any (title, page) entries out of it. Skipping.")
            return None
        print(f"  Read {len(toc_entries)} Table of Contents entries.")

        offset = detect_page_offset(pdf, toc_entries, toc_pages)
        if offset is None:
            print("  Could not confidently work out this document's page-numbering offset. Skipping.")
            return None
        print(f"  Page-numbering offset detected: {offset}")

        sections = locate_sections(toc_entries, offset, len(pdf.pages))
        for key, info in sections.items():
            print(f"  Found '{key}' -> matched TOC title \"{info['matched_title']}\" (confidence {info['score']})")

        business_summary = industry_summary = objects_of_offer = None
        key_risks = None
        financial_summary = None

        if "offer_summary" in sections:
            s = sections["offer_summary"]
            summary_text = extract_section_text(pdf, s["start"], s["end"])
            business_summary = extract_paragraph_after_heading(
                summary_text,
                [
                    # SEBI's standard "Offer Document Summary" sub-heading
                    # wording -- checked first since this is the section's
                    # own condensed summary, not the full chapter later.
                    "summary of primary business",
                    "primary business of our company",
                    "business overview",
                    "overview of our business",
                    "our business",
                ],
            )
            industry_summary = extract_paragraph_after_heading(
                summary_text,
                [
                    "summary of the industry",
                    "industry in which our company operates",
                    "industry overview",
                    "overview of the industry",
                ],
            )
            objects_of_offer = extract_paragraph_after_heading(
                summary_text, ["objects of the offer", "objects of the issue"]
            )
            key_risks = extract_top_risks(summary_text)
            financial_summary = extract_financial_summary(pdf, s["start"], s["end"])

        # Fall back to the fuller sections for anything the summary didn't have.
        if not business_summary and "our_business" in sections:
            s = sections["our_business"]
            business_summary = extract_paragraph_after_heading(
                extract_section_text(pdf, s["start"], s["end"], max_pages=4),
                ["overview", "our business"],
            )
        if not industry_summary and "industry_overview" in sections:
            s = sections["industry_overview"]
            industry_summary = extract_paragraph_after_heading(
                extract_section_text(pdf, s["start"], s["end"], max_pages=4),
                ["overview", "introduction"],
            )
        if not key_risks and "risk_factors" in sections:
            s = sections["risk_factors"]
            key_risks = extract_top_risks(extract_section_text(pdf, s["start"], s["end"], max_pages=6))

        return {
            "ipo_id": ipo["ipo_id"],
            "company_name": ipo["company_name"],
            "business_summary": business_summary,
            "industry_summary": industry_summary,
            "objects_of_offer": objects_of_offer,
            # NOTE: pass the real Python list/dict here, NOT a
            # json.dumps() string. These columns are `jsonb` in
            # Postgres, and the supabase client already serializes
            # Python objects to JSON correctly for a jsonb column --
            # pre-serializing to a string here would make Postgres
            # store a jsonb value that is itself just one big STRING
            # (double-encoded), which then can't be used as an array/
            # object by anything reading it back (the frontend's
            # `.map()` on key_risks broke exactly this way).
            "key_risks": key_risks if key_risks else None,
            "financial_summary": financial_summary if financial_summary else None,
            "source_pdf_filename": path.name,
            "parsed_at": datetime.now(timezone.utc).isoformat(),
        }


def main():
    if len(sys.argv) < 2:
        print("Usage: python 37_parse_drhp.py <folder_of_drhp_pdfs>")
        sys.exit(1)

    folder = Path(sys.argv[1])
    pdf_paths = sorted(folder.glob("*.pdf"))
    if not pdf_paths:
        print(f"No .pdf files found in {folder}")
        sys.exit(1)

    supabase = get_client()
    ipos = supabase.table("ipos").select("ipo_id, company_name, symbol").execute().data or []

    ok, skipped = 0, 0
    for path in pdf_paths:
        try:
            result = parse_one_pdf(path, ipos)
        except Exception as e:
            print(f"  ! Failed to parse {path.name}: {e}")
            skipped += 1
            continue

        if not result:
            skipped += 1
            continue

        fields_found = [
            k for k in ("business_summary", "industry_summary", "objects_of_offer", "key_risks", "financial_summary")
            if result.get(k)
        ]
        print(f"  Extracted: {', '.join(fields_found) if fields_found else '(nothing usable found)'}")

        row = {
            "ipo_id": result["ipo_id"],
            "status": "complete" if fields_found else "in_progress",
            "business_summary": result["business_summary"],
            "industry_summary": result["industry_summary"],
            "objects_of_offer": result["objects_of_offer"],
            "key_risks": result["key_risks"],
            "financial_summary": result["financial_summary"],
            "source_pdf_filename": result["source_pdf_filename"],
            "parsed_at": result["parsed_at"],
            "last_updated": result["parsed_at"],
        }
        supabase.table("ipo_assessments").upsert(row, on_conflict="ipo_id").execute()
        ok += 1

    print(f"\nDone. {ok} document(s) parsed and written, {skipped} skipped.")


if __name__ == "__main__":
    main()
