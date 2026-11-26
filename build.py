#!/usr/bin/env python3
"""Compile course Markdown sources (index, lessons, reference sheets) into HTML."""

from __future__ import annotations

import argparse
import html
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml
from markdown_it import MarkdownIt

COURSE_NAME = "Tang Nano 20K with Amaranth HDL"
PRISM_VERSION = "1.29.0"
MERMAID_VERSION = "11.4.1"
KATEX_VERSION = "0.16.11"

FENCED_RE = re.compile(
    r"^```([^\n]*)\n(.*?)^```\s*$",
    re.MULTILINE | re.DOTALL,
)
ATTR_RE = re.compile(r'([A-Za-z0-9_-]+)="([^"]*)"')
BLANK_RE = re.compile(r"\{\{blank:([^|}]+)\|([^|}]+)\|([^|}]+)\|(\d+)\}\}")
DISPLAY_MATH_RE = re.compile(r"(?<!\\)\$\$(.+?)(?<!\\)\$\$", re.DOTALL)
INLINE_MATH_RE = re.compile(r"(?<!\\)\$(?!\$)([^$\n]+?)(?<!\\)\$")
INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
HEADING_ANCHOR_RE = re.compile(r"<h([1-6])>(.*?)\s*\{#([A-Za-z0-9_-]+)\}\s*</h\1>")
MD_HREF_RE = re.compile(r'href="([^":#]+\.md)(#[^"]*)?"')
TABLE_CAPTION_RE = re.compile(r"<p>Table:\s*(.*?)</p>\s*<table>", re.DOTALL)
VERIFY_ITEM_RE = re.compile(r"<li>\s*\[([ xX])\]\s*(.*?)</li>", re.DOTALL)
BARE_TEX_MACRO_RE = re.compile(
    r"\\(?:approx|pm|Omega|times|le|ge|frac|cdot|mu|Delta|alpha|beta)\b"
)

MD = MarkdownIt("commonmark", {"html": True, "linkify": False}).enable("table")


@dataclass
class PageMeta:
    source: Path
    rel_out: Path
    kind: str  # "index" | "lesson" | "reference"
    title: str
    page_title: str
    nav_id: str
    nav_label: str
    badge: str
    subtitle: str
    card_title: str
    card_summary: str
    lesson_num: str
    body: str


def parse_attrs(raw: str) -> dict[str, str]:
    return {m.group(1): m.group(2) for m in ATTR_RE.finditer(raw)}


def split_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    meta = yaml.safe_load(text[4:end]) or {}
    return meta, text[end + 5 :]


def reference_out_name(stem: str) -> str:
    return "glossary.html" if stem == "GLOSSARY" else f"{stem}.html"


def rewrite_md_href(href: str, from_rel_out: Path) -> str:
    if href.startswith(("http://", "https://", "mailto:", "#")):
        return href
    path_part, sep, frag = href.partition("#")
    if not path_part.endswith(".md"):
        return href
    if path_part.endswith("/GLOSSARY.md") or path_part == "GLOSSARY.md":
        new_path = path_part[: -len("GLOSSARY.md")] + "glossary.html"
    else:
        new_path = path_part[:-3] + ".html"
    return f"{new_path}{sep}{frag}"


def render_inline_md(text: str, rel_out: Path) -> str:
    math_tokens: list[str] = []

    def stash_math(m: re.Match[str]) -> str:
        idx = len(math_tokens)
        math_tokens.append(m.group(0))
        return f"@@MATH_{idx}@@"

    protected = DISPLAY_MATH_RE.sub(stash_math, text)
    protected = INLINE_MATH_RE.sub(stash_math, protected)
    rendered = MD.renderInline(protected)
    rendered = MD_HREF_RE.sub(
        lambda m: f'href="{rewrite_md_href(m.group(1), rel_out)}{m.group(2) or ""}"',
        rendered,
    )
    for idx, raw_math in enumerate(math_tokens):
        rendered = rendered.replace(f"@@MATH_{idx}@@", html.escape(raw_math, quote=False))
    return rendered


def render_code_fence(info: str, body: str, interactive_blanks: bool = False) -> str:
    parts = info.strip().split(None, 1)
    lang = parts[0] if parts else "text"
    attrs = parse_attrs(parts[1]) if len(parts) > 1 else {}
    caption = attrs.get("caption", "")

    if lang == "mermaid":
        escaped = html.escape(body.rstrip("\n"), quote=False)
        cap_html = f"<figcaption>{html.escape(caption)}</figcaption>" if caption else ""
        return f'<figure class="mermaid-figure"><pre class="mermaid">{escaped}</pre>{cap_html}</figure>'

    escaped = html.escape(body.rstrip("\n"), quote=False)
    if interactive_blanks:
        def replace_blank(m: re.Match[str]) -> str:
            answer, hint, placeholder, width = m.groups()
            return (
                f'<input class="blank-input" type="text" '
                f'data-answer="{html.escape(answer)}" '
                f'data-hint="{html.escape(hint)}" '
                f'placeholder="{html.escape(placeholder)}" '
                f'aria-label="{html.escape(hint)}" '
                f'style="width: {int(width) + 2}ch;">'
            )

        escaped = BLANK_RE.sub(replace_blank, escaped)

    cap_html = f"<figcaption>{html.escape(caption)}</figcaption>" if caption else ""
    return (
        f'<figure class="code-figure">{cap_html}'
        f'<pre><code class="language-{html.escape(lang)}">{escaped}</code></pre></figure>'
    )


def expand_sidenotes(text: str, rel_out: Path, start_idx: int) -> tuple[str, dict[str, str], int]:
    out: list[str] = []
    placeholders: dict[str, str] = {}
    i = 0
    counter = start_idx
    marker = "{{sidenote:"
    while i < len(text):
        pos = text.find(marker, i)
        if pos == -1:
            out.append(text[i:])
            break
        out.append(text[i:pos])
        depth = 2
        j = pos + len(marker)
        while j < len(text) and depth > 0:
            if text[j : j + 2] == "}}":
                depth -= 2
                if depth == 0:
                    break
                j += 2
            elif text[j : j + 2] == "{{":
                depth += 2
                j += 2
            else:
                j += 1
        if depth != 0:
            raise ValueError(f"Unclosed sidenote starting near: {text[pos:pos + 60]!r}")
        note_md = text[pos + len(marker) : j].strip()
        counter += 1
        note_id = f"sidenote-{counter}"
        token = f"SIDENOTEPLACEHOLDER{counter}END"
        note_html = render_inline_md(note_md, rel_out)
        placeholders[token] = (
            f'<button type="button" class="sidenote-toggle" '
            f'aria-expanded="false" aria-controls="{note_id}">'
            f'<span class="sidenote-number" aria-label="Sidenote {counter}"></span>'
            f"</button>"
            f'<span class="sidenote" id="{note_id}" hidden>{note_html}</span>'
        )
        out.append(token)
        i = j + 2
    return "".join(out), placeholders, counter


def render_markdown_fragment(
    md_text: str,
    rel_out: Path,
    *,
    interactive_blanks: bool = False,
    sidenote_start: int = 0,
) -> tuple[str, int]:
    fenced_blocks: dict[str, str] = {}
    math_blocks: dict[str, str] = {}
    inline_code_blocks: dict[str, str] = {}

    def stash_fence(m: re.Match[str]) -> str:
        idx = len(fenced_blocks)
        token = f"\n<!--FENCED_CODE_PLACEHOLDER_{idx}-->\n"
        fenced_blocks[token.strip()] = render_code_fence(
            m.group(1), m.group(2), interactive_blanks=interactive_blanks
        )
        return token

    working = FENCED_RE.sub(stash_fence, md_text)

    def stash_code_span(m: re.Match[str]) -> str:
        idx = len(inline_code_blocks)
        token = f"INLINECODEPLACEHOLDER{idx}END"
        inline_code_blocks[token] = f"<code>{html.escape(m.group(1), quote=False)}</code>"
        return token

    working = INLINE_CODE_RE.sub(stash_code_span, working)

    def stash_math(m: re.Match[str]) -> str:
        idx = len(math_blocks)
        token = f"MATHPLACEHOLDER{idx}END"
        math_blocks[token] = html.escape(m.group(0), quote=False)
        return token

    working = DISPLAY_MATH_RE.sub(stash_math, working)
    working = INLINE_MATH_RE.sub(stash_math, working)

    working, sidenote_blocks, sidenote_count = expand_sidenotes(
        working, rel_out, sidenote_start
    )

    rendered = MD.render(working)
    rendered = HEADING_ANCHOR_RE.sub(r'<h\1 id="\3">\2</h\1>', rendered)
    rendered = MD_HREF_RE.sub(
        lambda m: f'href="{rewrite_md_href(m.group(1), rel_out)}{m.group(2) or ""}"',
        rendered,
    )
    rendered = TABLE_CAPTION_RE.sub(
        r'<div class="table-caption">\1</div><div class="table-scroll"><table class="ref-table">',
        rendered,
    )
    rendered = re.sub(
        r"<table>",
        '<div class="table-scroll"><table class="ref-table">',
        rendered,
    )
    rendered = rendered.replace("</table>", "</table></div>")

    for token, replacement in sidenote_blocks.items():
        rendered = rendered.replace(token, replacement)
    for token, replacement in math_blocks.items():
        rendered = rendered.replace(token, replacement)
    for token, replacement in inline_code_blocks.items():
        rendered = rendered.replace(token, replacement)
    for token, replacement in fenced_blocks.items():
        rendered = rendered.replace(f"<p>{token}</p>", replacement)
        rendered = rendered.replace(token, replacement)

    return rendered, sidenote_count


def render_box_header(kicker: str, title: str, badge: str = "") -> str:
    parts = ['<div class="box-header"><div class="box-heading-group">']
    if kicker:
        parts.append(f'<span class="box-kicker">{html.escape(kicker)}</span>')
    if title:
        parts.append(f'<h3 class="box-title">{html.escape(title)}</h3>')
    parts.append("</div>")
    if badge:
        parts.append(f'<span class="box-badge">{html.escape(badge)}</span>')
    parts.append("</div>")
    return "".join(parts)


def render_quiz_block(
    attrs: dict[str, str],
    yaml_body: str,
    rel_out: Path,
    errors: list[str],
) -> str:
    quiz_id = attrs.get("id", "quiz")
    title = attrs.get("title", "Retrieval Practice")
    badge = attrs.get("badge", "")
    questions = yaml.safe_load(yaml_body) or []

    parts = [
        f'<section class="quiz-box" id="{html.escape(quiz_id)}">',
        render_box_header("RETRIEVAL CHECK", title, badge),
    ]

    for q_idx, q in enumerate(questions, start=1):
        prompt = q["question"]
        wrong_hint = q.get("wrong_hint", "Review the section above and try again.")
        options = q.get("options", [])
        if len(options) != 4:
            errors.append(
                f"{rel_out}: quiz '{quiz_id}' question {q_idx} has {len(options)} options (expected 4)"
            )
        word_counts = [len(str(opt["text"]).split()) for opt in options]
        if len(set(word_counts)) != 1:
            errors.append(
                f"{rel_out}: quiz '{quiz_id}' question {q_idx} option word counts differ: {word_counts}"
            )

        parts.append(
            f'<div class="quiz-question" data-wrong-hint="{html.escape(wrong_hint)}">'
        )
        parts.append(
            f'<div class="quiz-prompt">{q_idx}. {render_inline_md(prompt, rel_out)}</div>'
        )
        parts.append('<div class="quiz-options">')
        for opt in options:
            letter = str(opt["letter"])
            text_html = render_inline_md(str(opt["text"]), rel_out)
            correct = "true" if opt.get("correct") else "false"
            explain = str(opt.get("explain", ""))
            parts.append(
                f'<button type="button" class="quiz-option" aria-pressed="false" '
                f'data-correct="{correct}" data-explain="{html.escape(explain)}">'
                f'<span class="quiz-letter">{html.escape(letter)}</span>'
                f"<span>{text_html}</span>"
                f"</button>"
            )
        parts.append("</div>")
        parts.append('<div class="quiz-explain" aria-live="polite" hidden></div>')
        parts.append("</div>")

    parts.append("</section>")
    return "\n".join(parts)


def render_exercise_block(
    attrs: dict[str, str],
    body_lines: list[str],
    rel_out: Path,
    sidenote_start: int,
    errors: list[str],
) -> tuple[str, int]:
    ex_id = attrs.get("id", "exercise")
    title = attrs.get("title", "Interactive Lab")
    badge = attrs.get("badge", "")

    body_text = "\n".join(body_lines)
    prompts_match = re.search(
        r"\n:::prompts\s*\n(.*?)\n:::\s*$",
        body_text,
        re.DOTALL,
    )
    if not prompts_match:
        errors.append(f"{rel_out}: exercise '{ex_id}' missing nested :::prompts block")
        prompts = {}
        inner_md = body_text
    else:
        prompts = yaml.safe_load(prompts_match.group(1)) or {}
        inner_md = body_text[: prompts_match.start()]

    if not BLANK_RE.search(inner_md):
        errors.append(f"{rel_out}: exercise '{ex_id}' has no {{{{blank:...}}}} tokens")

    inner_html, sidenote_count = render_markdown_fragment(
        inner_md, rel_out, interactive_blanks=True, sidenote_start=sidenote_start
    )

    hint = str(prompts.get("hint", "Check the highlighted blanks."))
    success = str(prompts.get("success", "Verified!"))

    html_out = "\n".join(
        [
            (
                f'<section class="exercise-box" id="{html.escape(ex_id)}" '
                f'data-hint="{html.escape(hint)}" data-success="{html.escape(success)}">'
            ),
            render_box_header("INTERACTIVE LAB", title, badge),
            inner_html,
            '<div class="widget-actions">',
            '<button type="button" class="btn btn-primary" data-action="check">Check Answers</button>',
            '<button type="button" class="btn" data-action="reveal">Reveal Solution</button>',
            '<button type="button" class="btn" data-action="reset">Reset</button>',
            "</div>",
            '<div class="feedback-banner exercise-feedback" aria-live="polite" hidden></div>',
            "</section>",
        ]
    )
    return html_out, sidenote_count


def render_body_with_directives(
    body: str,
    rel_out: Path,
    lessons: list[PageMeta],
    references: list[PageMeta],
    errors: list[str],
) -> str:
    lines = body.splitlines()
    chunks: list[tuple[str, object]] = []
    buf: list[str] = []
    i = 0

    def flush_buf() -> None:
        if buf:
            chunks.append(("md", "\n".join(buf)))
            buf.clear()

    while i < len(lines):
        line = lines[i]
        m = re.match(r"^:::(callout-warn|callout-success|callout|teacher-prompt|verify|exercise|quiz)\s*(.*)$", line)
        if not m:
            buf.append(line)
            i += 1
            continue

        flush_buf()
        kind = m.group(1)
        attrs = parse_attrs(m.group(2))
        i += 1
        block_lines: list[str] = []
        nested_depth = 0
        while i < len(lines):
            cur = lines[i]
            if cur.startswith(":::") and cur.strip() != ":::":
                nested_depth += 1
                block_lines.append(cur)
            elif cur.strip() == ":::":
                if nested_depth > 0:
                    nested_depth -= 1
                    block_lines.append(cur)
                else:
                    i += 1
                    break
            else:
                block_lines.append(cur)
            i += 1
        chunks.append((kind, (attrs, block_lines)))

    flush_buf()

    sidenote_count = 0
    rendered_parts: list[str] = []
    for chunk_kind, payload in chunks:
        if chunk_kind == "md":
            html_part, sidenote_count = render_markdown_fragment(
                str(payload), rel_out, sidenote_start=sidenote_count
            )
            rendered_parts.append(html_part)
        elif chunk_kind in {"callout", "callout-warn", "callout-success", "teacher-prompt"}:
            attrs, block_lines = payload  # type: ignore[misc]
            title = attrs.get("title", "")
            inner_html, sidenote_count = render_markdown_fragment(
                "\n".join(block_lines), rel_out, sidenote_start=sidenote_count
            )
            kicker_map = {
                "callout": "NOTE",
                "callout-warn": "CAUTION",
                "callout-success": "CONFIRMED",
                "teacher-prompt": "AGENT PROMPT",
            }
            css_class = "teacher-prompt" if chunk_kind == "teacher-prompt" else f"callout {chunk_kind}"
            header_html = render_box_header(kicker_map[chunk_kind], title)
            rendered_parts.append(f'<aside class="{css_class}">{header_html}{inner_html}</aside>')
        elif chunk_kind == "verify":
            attrs, block_lines = payload  # type: ignore[misc]
            ver_id = attrs.get("id", "verify")
            title = attrs.get("title", "Verification Lab")
            badge = attrs.get("badge", "")
            inner_html, sidenote_count = render_markdown_fragment(
                "\n".join(block_lines), rel_out, sidenote_start=sidenote_count
            )
            inner_html = inner_html.replace("<ul>", '<ul class="verify-list">', 1)
            inner_html = VERIFY_ITEM_RE.sub(
                lambda mm: (
                    f'<li><label class="verify-check">'
                    f'<input type="checkbox"{" checked" if mm.group(1).lower() == "x" else ""}>'
                    f'<span>{mm.group(2)}</span></label></li>'
                ),
                inner_html,
            )
            header_html = render_box_header("VERIFICATION GATE", title, badge)
            rendered_parts.append(
                f'<section class="verify-box" id="{html.escape(ver_id)}">'
                f"{header_html}"
                f"{inner_html}</section>"
            )
        elif chunk_kind == "exercise":
            attrs, block_lines = payload  # type: ignore[misc]
            ex_html, sidenote_count = render_exercise_block(
                attrs, block_lines, rel_out, sidenote_count, errors
            )
            rendered_parts.append(ex_html)
        elif chunk_kind == "quiz":
            attrs, block_lines = payload  # type: ignore[misc]
            rendered_parts.append(
                render_quiz_block(attrs, "\n".join(block_lines), rel_out, errors)
            )

    html_body = "\n".join(rendered_parts)
    if "{{widget:lesson-cards}}" in html_body:
        html_body = html_body.replace(
            "{{widget:lesson-cards}}", build_lesson_cards_html(lessons, rel_out)
        )
    if "{{widget:reference-cards}}" in html_body:
        html_body = html_body.replace(
            "{{widget:reference-cards}}", build_reference_cards_html(references, rel_out)
        )
    return html_body


def build_lesson_cards_html(lessons: list[PageMeta], from_rel_out: Path) -> str:
    prefix = "../" if len(from_rel_out.parts) > 1 else ""
    cards = ['<div class="card-grid">']
    for lesson in lessons:
        clean_badge = re.sub(r"^Lesson\s+\d+\s*[•·-]\s*", "", lesson.badge).strip()
        meta_label = (
            f"LESSON {lesson.lesson_num} • {clean_badge}"
            if clean_badge
            else f"LESSON {lesson.lesson_num}"
        )
        href = f"{prefix}{lesson.rel_out.as_posix()}"
        title_html = render_inline_md(lesson.card_title, from_rel_out)
        summary_html = render_inline_md(lesson.card_summary, from_rel_out)
        cards.append(
            f'<a class="course-card" href="{html.escape(href)}">'
            f'<span class="lesson-card-meta">{html.escape(meta_label)}</span>'
            f'<span class="course-card-title">{title_html}</span>'
            f'<span class="course-card-summary">{summary_html}</span>'
            f"</a>"
        )
    cards.append("</div>")
    return "\n".join(cards)


def build_reference_cards_html(references: list[PageMeta], from_rel_out: Path) -> str:
    prefix = "../" if len(from_rel_out.parts) > 1 else ""
    cards = ['<div class="card-grid">']
    for ref in references:
        href = f"{prefix}{ref.rel_out.as_posix()}"
        title_html = render_inline_md(ref.card_title, from_rel_out)
        summary_html = render_inline_md(ref.card_summary, from_rel_out)
        cards.append(
            f'<a class="course-card" href="{html.escape(href)}">'
            f'<span class="lesson-card-meta">Reference</span>'
            f'<span class="course-card-title">{title_html}</span>'
            f'<span class="course-card-summary">{summary_html}</span>'
            f"</a>"
        )
    cards.append("</div>")
    return "\n".join(cards)


def build_nav_html(
    page: PageMeta,
    lessons: list[PageMeta],
    references: list[PageMeta],
) -> str:
    prefix = "../" if len(page.rel_out.parts) > 1 else ""
    index_href = f"{prefix}index.html"

    if page.kind == "index":
        crumbs = '<span aria-current="page">Index</span>'
    elif page.kind == "lesson":
        crumbs = (
            f'<a href="{index_href}">Index</a>'
            f' <span aria-hidden="true">›</span> '
            f'<span aria-current="page">Lesson {html.escape(page.lesson_num)}</span>'
        )
    else:
        crumbs = (
            f'<a href="{index_href}">Index</a>'
            f' <span aria-hidden="true">›</span> '
            f'<span aria-current="page">{html.escape(page.nav_label or page.title)}</span>'
        )

    controls: list[str] = []
    if page.kind == "lesson":
        idx = next(i for i, item in enumerate(lessons) if item.nav_id == page.nav_id)
        prev_lesson = lessons[idx - 1] if idx > 0 else None
        next_lesson = lessons[idx + 1] if idx + 1 < len(lessons) else None
        prev_html = (
            f'<a href="{prefix}{prev_lesson.rel_out.as_posix()}" title="{html.escape(prev_lesson.title)}">← Prev</a>'
            if prev_lesson
            else '<span class="nav-pager-disabled">← Prev</span>'
        )
        next_html = (
            f'<a href="{prefix}{next_lesson.rel_out.as_posix()}" title="{html.escape(next_lesson.title)}">Next →</a>'
            if next_lesson
            else '<span class="nav-pager-disabled">Next →</span>'
        )
        controls.append(f'<span class="nav-pager-group">{prev_html} <span aria-hidden="true">·</span> {next_html}</span>')
        controls.append('<span class="nav-sep" aria-hidden="true">|</span>')

    for ref in references:
        aria = ' aria-current="page"' if ref.nav_id == page.nav_id else ""
        label = ref.nav_label or ref.title
        controls.append(
            f'<a class="nav-ref-link" href="{prefix}{ref.rel_out.as_posix()}"{aria}>{html.escape(label)}</a>'
        )
    controls.append('<span class="mission-badge">Tang Nano 20K</span>')

    return (
        '<header class="site-header">'
        '<nav class="course-nav" aria-label="Course navigation">'
        f'<div class="nav-breadcrumbs">{crumbs}</div>'
        f'<div class="nav-controls">{" ".join(controls)}</div>'
        "</nav></header>"
    )


def build_lesson_pager_html(page: PageMeta, lessons: list[PageMeta]) -> str:
    if page.kind != "lesson":
        return ""
    idx = next(i for i, item in enumerate(lessons) if item.nav_id == page.nav_id)
    prev_lesson = lessons[idx - 1] if idx > 0 else None
    next_lesson = lessons[idx + 1] if idx + 1 < len(lessons) else None
    prefix = "../" if len(page.rel_out.parts) > 1 else ""

    prev_card = (
        f'<a class="pager-card" href="{prefix}{prev_lesson.rel_out.as_posix()}">'
        f'<span class="pager-label">← Previous • Lesson {html.escape(prev_lesson.lesson_num)}</span>'
        f'<span class="pager-title">{html.escape(prev_lesson.title)}</span></a>'
        if prev_lesson
        else '<div class="pager-card" aria-hidden="true"><span class="pager-label">Start of Course</span>'
        '<span class="pager-title">Index</span></div>'
    )
    next_card = (
        f'<a class="pager-card pager-card-next" href="{prefix}{next_lesson.rel_out.as_posix()}">'
        f'<span class="pager-label">Next • Lesson {html.escape(next_lesson.lesson_num)} →</span>'
        f'<span class="pager-title">{html.escape(next_lesson.title)}</span></a>'
        if next_lesson
        else '<div class="pager-card pager-card-next"><span class="pager-label">Up Next</span>'
        '<span class="pager-title">Ask your agent for Lesson 0002</span></div>'
    )
    return f'<nav class="lesson-pager" aria-label="Lesson pagination">{prev_card}{next_card}</nav>'


def load_pages(root_dir: Path) -> tuple[PageMeta, list[PageMeta], list[PageMeta]]:
    def make_page(path: Path, kind: str, rel_out: Path, lesson_num: str = "") -> PageMeta:
        meta, body = split_frontmatter(path.read_text(encoding="utf-8"))
        card = meta.get("card") or {}
        title = str(meta.get("title", path.stem))
        return PageMeta(
            source=path,
            rel_out=rel_out,
            kind=kind,
            title=title,
            page_title=str(meta.get("page_title", f"{title} — {COURSE_NAME}")),
            nav_id=str(meta.get("nav_id", path.stem)),
            nav_label=str(meta.get("nav_label", title)),
            badge=str(meta.get("badge", "")),
            subtitle=str(meta.get("subtitle", "")),
            card_title=str(card.get("title", title)),
            card_summary=str(card.get("summary", meta.get("subtitle", ""))),
            lesson_num=lesson_num,
            body=body,
        )

    index_page = make_page(root_dir / "index.md", "index", Path("index.html"))
    lessons: list[PageMeta] = []
    for path in sorted((root_dir / "lessons").glob("[0-9][0-9][0-9][0-9]-*.md")):
        num = path.stem.split("-", 1)[0]
        lessons.append(make_page(path, "lesson", Path("lessons") / f"{path.stem}.html", num))

    references: list[PageMeta] = []
    for path in sorted((root_dir / "reference").glob("*.md")):
        references.append(
            make_page(path, "reference", Path("reference") / reference_out_name(path.stem))
        )

    return index_page, lessons, references


def wrap_html_document(page: PageMeta, nav_html: str, body_html: str, pager_html: str) -> str:
    prefix = "../" if len(page.rel_out.parts) > 1 else ""
    badge_html = f'<span class="page-badge">{html.escape(page.badge)}</span>' if page.badge else ""
    subtitle_html = f'<p class="page-subtitle">{html.escape(page.subtitle)}</p>' if page.subtitle else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="dark">
  <title>{html.escape(page.page_title)}</title>
  <link rel="stylesheet" href="{prefix}assets/style.css">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/prismjs@{PRISM_VERSION}/themes/prism-tomorrow.min.css">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@{KATEX_VERSION}/dist/katex.min.css">
</head>
<body>
  <a class="skip-link" href="#main-content">Skip to main content</a>
  {nav_html}
  <main id="main-content" class="page-shell">
    <article class="lesson-article">
      <header class="page-hero">
        {badge_html}
        <h1>{html.escape(page.title)}</h1>
        {subtitle_html}
      </header>
      {body_html}
      {pager_html}
    </article>
  </main>
  <footer class="site-footer">
    Sipeed Tang Nano 20K Course • Apache 2.0 License • Not an officially supported Google product.
  </footer>
  <script src="https://cdn.jsdelivr.net/npm/prismjs@{PRISM_VERSION}/components/prism-core.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/prismjs@{PRISM_VERSION}/plugins/autoloader/prism-autoloader.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/prismjs@{PRISM_VERSION}/plugins/keep-markup/prism-keep-markup.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/mermaid@{MERMAID_VERSION}/dist/mermaid.min.js"></script>
  <script defer src="https://cdn.jsdelivr.net/npm/katex@{KATEX_VERSION}/dist/katex.min.js"></script>
  <script defer src="https://cdn.jsdelivr.net/npm/katex@{KATEX_VERSION}/dist/contrib/auto-render.min.js"></script>
  <script defer src="{prefix}assets/course.js"></script>
</body>
</html>
"""


def validate_rendered_html(
    page: PageMeta,
    full_html: str,
    body_html: str,
    valid_rel_outputs: set[Path],
    errors: list[str],
) -> None:
    # 1. Check code blocks don't contain leaked markdown HTML tags
    for m in re.finditer(r"<pre><code[^>]*>(.*?)</code></pre>", body_html, re.DOTALL):
        inner = m.group(1)
        if re.search(r"<(?:p|h[1-6]|pre)\b", inner):
            errors.append(f"{page.rel_out}: <pre><code> contains forbidden <p>/<h*>/<pre>")

    # 2. Check no raw {#...} anchor syntax or malformed <[1-6] tags
    prose_no_code = re.sub(r"<pre>.*?</pre>", "", body_html, flags=re.DOTALL)
    prose_no_code = re.sub(r"<code>.*?</code>", "", prose_no_code, flags=re.DOTALL)
    if re.search(r"\{#[A-Za-z0-9_-]+\}", prose_no_code):
        errors.append(f"{page.rel_out}: unstripped {{#anchor}} token in HTML")
    if re.search(r"<[1-6]\b", prose_no_code):
        errors.append(f"{page.rel_out}: malformed <[1-6] tag in HTML")

    # 3. Check no bare TeX macros outside math delimiters and code
    prose_no_math = DISPLAY_MATH_RE.sub("", prose_no_code)
    prose_no_math = INLINE_MATH_RE.sub("", prose_no_math)
    if BARE_TEX_MACRO_RE.search(prose_no_math):
        errors.append(f"{page.rel_out}: bare TeX macro found outside $...$ delimiters")

    # 4. Check KaTeX assets if math delimiters exist
    if (
        "$" in prose_no_code
        and (INLINE_MATH_RE.search(prose_no_code) or DISPLAY_MATH_RE.search(prose_no_code))
        and ("katex.min.js" not in full_html or "katex.min.css" not in full_html)
    ):
        errors.append(f"{page.rel_out}: math delimiters present without KaTeX assets")

    # 5. Check all local .html links resolve to built pages
    for m in re.finditer(r'href="([^"]+)"', body_html):
        href = m.group(1)
        if href.startswith(("http://", "https://", "mailto:", "#")):
            continue
        target_str = href.split("#", 1)[0]
        if not target_str.endswith(".html"):
            continue
        resolved = (page.rel_out.parent / target_str).as_posix()
        norm_parts: list[str] = []
        for part in Path(resolved).parts:
            if part == "..":
                if norm_parts:
                    norm_parts.pop()
            elif part != ".":
                norm_parts.append(part)
        target_path = Path(*norm_parts)
        if target_path not in valid_rel_outputs:
            errors.append(f"{page.rel_out}: broken internal link '{href}' -> '{target_path}'")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Tang Nano 20K course HTML site.")
    parser.add_argument("--root", type=Path, default=Path("."), help="Course workspace root")
    parser.add_argument("--out-dir", type=Path, default=Path("."), help="Output directory")
    parser.add_argument("--check", action="store_true", help="Validate quizzes, links, math, and code fences")
    args = parser.parse_args()

    root_dir = args.root.resolve()
    out_dir = args.out_dir.resolve()
    index_page, lessons, references = load_pages(root_dir)
    all_pages = [index_page, *lessons, *references]
    valid_rel_outputs = {p.rel_out for p in all_pages}
    errors: list[str] = []

    if out_dir != root_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / ".nojekyll").write_text("", encoding="utf-8")
        assets_dst = out_dir / "assets"
        if assets_dst.exists():
            shutil.rmtree(assets_dst)
        shutil.copytree(root_dir / "assets", assets_dst)

    for page in all_pages:
        body_html = render_body_with_directives(
            page.body, page.rel_out, lessons, references, errors
        )
        nav_html = build_nav_html(page, lessons, references)
        pager_html = build_lesson_pager_html(page, lessons)
        full_html = wrap_html_document(page, nav_html, body_html, pager_html)

        validate_rendered_html(page, full_html, body_html, valid_rel_outputs, errors)

        dest = out_dir / page.rel_out
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(full_html, encoding="utf-8")
        print(f"[BUILT] {page.rel_out}")

    if args.check and errors:
        for err in errors:
            print(f"[CHECK ERROR] {err}", file=sys.stderr)
        return 1

    if errors:
        for err in errors:
            print(f"[WARN] {err}", file=sys.stderr)

    print(f"[OK] Built {len(all_pages)} pages in {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
