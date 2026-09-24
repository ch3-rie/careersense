"""Load and fill institutional email templates. HTML values are escaped unless marked safe."""

from __future__ import annotations

from html import escape
from pathlib import Path

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

HTML_HEADLINES = {
    "password_reset": "Password Reset Verification",
    "profile_update": "Profile Update Required",
    "account_approved": "Your CareerSense account was approved",
    "account_rejected": "Registration rejected",
    "account_status": "CareerSense account update",
}


def _read(name: str) -> str:
    path = TEMPLATE_DIR / name
    return path.read_text(encoding="utf-8")


def _fill(template: str, values: dict[str, str]) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", value)
    return rendered


def html_escape(value: object) -> str:
    return escape(str(value or ""), quote=True)


def render_pair(stem: str, *, html_values: dict[str, str], text_values: dict[str, str]) -> tuple[str, str]:
    text = _fill(_read(f"{stem}.txt"), text_values)
    inner = _fill(_read(f"{stem}.html"), html_values)
    html = _fill(
        _read("base.html"),
        {
            "headline": html_values.get("headline") or html_escape(HTML_HEADLINES.get(stem, "CareerSense")),
            "content": inner,
            "office": html_values.get("office") or html_escape(text_values.get("office", "")),
        },
    )
    return text, html


def render_password_reset(*, name: str, pin: str, minutes: int, office: str) -> tuple[str, str]:
    greeting = f"Hello {name}," if name else "Hello,"
    values = {
        "greeting": greeting,
        "pin": pin,
        "minutes": str(minutes),
        "office": office,
    }
    html_values = {
        "greeting": html_escape(greeting),
        "pin": html_escape(pin),
        "minutes": html_escape(minutes),
        "office": html_escape(office),
        "headline": html_escape(HTML_HEADLINES["password_reset"]),
    }
    return render_pair("password_reset", html_values=html_values, text_values=values)


def render_profile_update(
    *,
    name: str,
    office: str,
    message: str,
    fields: list[str],
    action_url: str,
) -> tuple[str, str]:
    greeting = f"Dear {name}," if name else "Dear Alumni,"
    labels = [str(item).strip() for item in fields if str(item).strip()]
    fields_text = "\n".join(f"- {label}" for label in labels)
    fields_html = "".join(f"<li>{html_escape(label)}</li>" for label in labels)
    text_values = {
        "greeting": greeting,
        "office": office,
        "message": message,
        "fields_text": fields_text,
        "action_url": action_url,
    }
    html_values = {
        "greeting": html_escape(greeting),
        "office": html_escape(office),
        "message": html_escape(message),
        "fields_html": fields_html,
        "action_url": html_escape(action_url),
        "headline": html_escape(HTML_HEADLINES["profile_update"]),
    }
    return render_pair("profile_update", html_values=html_values, text_values=text_values)


def render_account_status(
    *,
    name: str,
    office: str,
    headline: str,
    intro: str,
    detail: str,
    action_url: str,
    cta_label: str,
    template: str = "account_approved",
) -> tuple[str, str]:
    greeting = f"Hello {name}," if name else "Hello,"
    action_line = f"{cta_label}:" if action_url else ""
    detail_html = f"<p>{html_escape(detail)}</p>" if detail.strip() else ""
    text_values = {
        "greeting": greeting,
        "intro": intro,
        "detail": detail,
        "action_line": action_line,
        "cta_label": cta_label,
        "action_url": action_url,
        "office": office,
    }
    html_values = {
        "greeting": html_escape(greeting),
        "headline": html_escape(headline),
        "intro": html_escape(intro),
        "detail_html": detail_html,
        "action_url": html_escape(action_url),
        "cta_label": html_escape(cta_label),
        "office": html_escape(office),
    }
    return render_pair(template, html_values=html_values, text_values=text_values)
