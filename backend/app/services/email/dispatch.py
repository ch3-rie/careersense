"""Send a notice and queue a retry when the provider failure can succeed later."""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.services.email.outbox import enqueue_if_retryable
from app.services.email.render import render_account_status
from app.services.email.service import app_url, office_name, send_email

logger = logging.getLogger("careersense")


def send_notice(
    db: Optional[Session],
    *,
    kind: str,
    to_address: str,
    account_id: Optional[int],
    name: str,
    subject: str,
    headline: str,
    intro: str,
    detail: str = "",
    path: str = "/login",
    cta: str = "Open CareerSense",
    template: str = "account_approved",
):
    text_body, html_body = render_account_status(
        name=name,
        office=office_name(),
        headline=headline,
        intro=intro,
        detail=detail,
        action_url=app_url(path),
        cta_label=cta,
        template=template,
    )
    try:
        result = send_email(
            to_address=to_address,
            subject=subject,
            text_body=text_body,
            html_body=html_body,
            kind=kind,
        )
    except Exception:
        logger.exception("Transactional email crashed kind=%s", kind)
        return None
    if db is not None and result is not None and not result.ok:
        enqueue_if_retryable(
            db,
            result,
            kind=kind,
            to_address=to_address,
            subject=subject,
            text_body=text_body,
            html_body=html_body,
            account_id=account_id,
        )
    return result
