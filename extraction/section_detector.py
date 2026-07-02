"""
Step 2 of the extraction pipeline: take the flat list of TextBlocks from
pdf_text_extractor.py and turn it into a list of Sections (title + HTML
body), which is what becomes the tabs on the document's webpage.
"""

import re
from collections import Counter
from typing import List

from schema import TextBlock, Section
import config

# Matches leading bullet markers: "-", "•", "1.", "2)", etc.
_BULLET_PATTERN = re.compile(r"^\s*(?:[-\u2022]|\d+[.)])\s+")


def compute_heading_font_threshold(blocks: List[TextBlock]) -> float:
    """
    Input: blocks (List[TextBlock]) - the full text-block list for one PDF.
    Output: float - the font size above which a line should be treated as
            a section heading rather than body text.

    Pseudocode:
    1. Collect all block.font_size values.
    2. Find the most common value (the mode) - this represents the
       document's body text size, since body text vastly outnumbers
       headings in any real document.
    3. Multiply that body size by config.HEADING_FONT_SIZE_MULTIPLIER.
    4. Return the resulting threshold.
    """
    if not blocks:
        return 0.0

    font_sizes = [block.font_size for block in blocks]
    body_size = Counter(font_sizes).most_common(1)[0][0]
    return body_size * config.HEADING_FONT_SIZE_MULTIPLIER


def is_heading(block: TextBlock, threshold: float) -> bool:
    """
    Input: block (TextBlock) - one line of text with formatting metadata.
           threshold (float) - the font-size cutoff from
           compute_heading_font_threshold().
    Output: bool - True if this line should start a new Section.

    Pseudocode:
    1. Consider the line a heading if EITHER:
        a. block.font_size >= threshold, OR
        b. block.is_bold is True AND the line is short (e.g. fewer than
           ~12 words) - catches bold headings that aren't necessarily
           larger than body text.
    2. Otherwise return False.
    """
    if block.font_size >= threshold:
        return True

    if block.is_bold and len(block.text.split()) < 12:
        return True

    return False


def convert_blocks_to_html(blocks: List[TextBlock]) -> str:
    """
    Input: blocks (List[TextBlock]) - the body text lines belonging to
           ONE section (everything between one heading and the next).
    Output: str - an HTML string (e.g. "<p>...</p><ul><li>...</li></ul>")
            ready to be dropped directly into the WordPress rich-text
            editor field for that section.

    Pseudocode:
    1. Initialize an empty list of HTML fragments, and track whether a
       <ul>/<ol> list is currently "open".
    2. For each block:
        a. If block.text starts with a bullet marker ("-", "•", or a
           number followed by "." or ")"), open a <ul> if one isn't
           already open, and append the text (marker stripped) as an
           <li> item.
        b. Otherwise: close any open <ul>, and wrap the line in a <p>
           tag. Wrap the whole line in <strong> first if block.is_bold
           is True.
    3. Close any list that is still open at the end.
    4. Join all fragments into a single HTML string and return it.
    """
    fragments: List[str] = []
    list_open = False

    for block in blocks:
        text = block.text.strip()
        if not text:
            continue

        bullet_match = _BULLET_PATTERN.match(text)
        if bullet_match:
            if not list_open:
                fragments.append("<ul>")
                list_open = True
            item_text = _BULLET_PATTERN.sub("", text)
            fragments.append(f"<li>{item_text}</li>")
        else:
            if list_open:
                fragments.append("</ul>")
                list_open = False
            if block.is_bold:
                fragments.append(f"<p><strong>{text}</strong></p>")
            else:
                fragments.append(f"<p>{text}</p>")

    if list_open:
        fragments.append("</ul>")

    return "".join(fragments)


def split_into_sections(blocks: List[TextBlock]) -> List[Section]:
    """
    Input: blocks (List[TextBlock]) - the full text-block list for one PDF.
    Output: List[Section] - the document broken into its sections, each
            with a title, an order index, and an HTML body.

    Pseudocode:
    1. threshold = compute_heading_font_threshold(blocks).
    2. Initialize: sections = [], current_title = None,
       current_body_blocks = [].
    3. For each block in blocks:
        a. If is_heading(block, threshold):
            - If current_title is not None (i.e. this isn't the very
              first heading), close out the section-in-progress:
              html = convert_blocks_to_html(current_body_blocks);
              sections.append(Section(title=current_title,
              body_html=html, order=len(sections))).
            - Set current_title = block.text; reset
              current_body_blocks = [].
        b. Else: append block to current_body_blocks.
    4. After the loop ends, close out the final section the same way
       (as long as current_title is not None).
    5. Return sections.
    """
    threshold = compute_heading_font_threshold(blocks)

    sections: List[Section] = []
    current_title = None
    current_body_blocks: List[TextBlock] = []

    for block in blocks:
        if is_heading(block, threshold):
            if current_title is not None:
                html = convert_blocks_to_html(current_body_blocks)
                sections.append(
                    Section(title=current_title, body_html=html, order=len(sections))
                )
            current_title = block.text.strip()
            current_body_blocks = []
        else:
            current_body_blocks.append(block)

    if current_title is not None:
        html = convert_blocks_to_html(current_body_blocks)
        sections.append(
            Section(title=current_title, body_html=html, order=len(sections))
        )

    return sections
