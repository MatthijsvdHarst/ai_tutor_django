from __future__ import annotations

import markdown as md
import bleach
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

ALLOWED_TAGS = [
    "p",
    "br",
    "strong",
    "em",
    "ul",
    "ol",
    "li",
    "code",
    "pre",
    "blockquote",
]
ALLOWED_ATTRS = {"*": ["class"]}


@register.filter
def render_markdown(text: str | None):
    if not text:
        return ""
    html = md.markdown(text, extensions=["extra"])
    cleaned = bleach.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)
    return mark_safe(cleaned)
