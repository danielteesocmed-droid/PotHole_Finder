"""
Optional email notifications via Resend (https://resend.com).
Set RESEND_API_KEY in your environment to enable.
If the key is absent, all notification calls are silent no-ops.
"""
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

RESEND_API_KEY  = os.getenv("RESEND_API_KEY", "")
FROM_EMAIL      = os.getenv("NOTIFY_FROM_EMAIL", "noreply@potholefinder.com")
APP_NAME        = os.getenv("APP_NAME", "PotHole Finder")
APP_URL         = os.getenv("APP_URL", "")

_ENABLED = bool(RESEND_API_KEY)


async def _send(to: str, subject: str, html: str) -> bool:
    """Send an email via Resend. Returns True on success."""
    if not _ENABLED or not to:
        return False
    try:
        import httpx
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
                json={"from": f"{APP_NAME} <{FROM_EMAIL}>", "to": [to], "subject": subject, "html": html},
            )
            if resp.status_code not in (200, 201):
                logger.warning("Resend API returned %s: %s", resp.status_code, resp.text)
                return False
        return True
    except Exception as exc:
        logger.warning("Email notification failed (non-fatal): %s", exc)
        return False


STATUS_LABELS = {
    "pending":     "Pending review",
    "in_progress": "In Progress — our crew is on it!",
    "resolved":    "Resolved ✓",
}


async def notify_report_submitted(ref_code: str, address: str, contact: Optional[str]) -> None:
    """Send confirmation email when a new report is created."""
    if not contact or "@" not in contact:
        return
    track_url = f"{APP_URL}#track" if APP_URL else ""
    html = f"""
    <div style="font-family:sans-serif;max-width:480px;margin:0 auto;color:#1a1a1a">
      <h2 style="color:#E8510A">Report Received 🚧</h2>
      <p>Thanks for reporting a pothole! Here are your details:</p>
      <table style="border-collapse:collapse;width:100%">
        <tr><td style="padding:6px 0;color:#666">Reference Code</td>
            <td style="padding:6px 0;font-weight:600;font-family:monospace">{ref_code}</td></tr>
        <tr><td style="padding:6px 0;color:#666">Location</td>
            <td style="padding:6px 0">{address}</td></tr>
        <tr><td style="padding:6px 0;color:#666">Status</td>
            <td style="padding:6px 0"><span style="background:#FEF3C7;color:#92400E;padding:2px 8px;border-radius:4px;font-size:13px">Pending Review</span></td></tr>
      </table>
      {"<p><a href='" + track_url + "' style='color:#E8510A'>Track your report</a></p>" if track_url else ""}
      <p style="color:#666;font-size:13px">We'll email you when the status changes. Thank you for helping keep our roads safe!</p>
    </div>
    """
    await _send(contact, f"[{APP_NAME}] Report Received — {ref_code}", html)


async def notify_status_changed(
    ref_code: str,
    address: str,
    new_status: str,
    admin_notes: Optional[str],
    contact: Optional[str],
) -> None:
    """Send email when an admin updates a report's status."""
    if not contact or "@" not in contact:
        return
    status_label = STATUS_LABELS.get(new_status, new_status)
    track_url = f"{APP_URL}#track" if APP_URL else ""
    notes_block = (
        f"<div style='background:#EFF6FF;border-radius:6px;padding:10px 14px;margin:14px 0;"
        f"font-size:13px;color:#1D4ED8'><strong>Note from our team:</strong><br>{admin_notes}</div>"
    ) if admin_notes else ""
    html = f"""
    <div style="font-family:sans-serif;max-width:480px;margin:0 auto;color:#1a1a1a">
      <h2 style="color:#E8510A">Report Update 🚧</h2>
      <p>Your pothole report <strong style="font-family:monospace">{ref_code}</strong> has been updated.</p>
      <table style="border-collapse:collapse;width:100%">
        <tr><td style="padding:6px 0;color:#666">Location</td>
            <td style="padding:6px 0">{address}</td></tr>
        <tr><td style="padding:6px 0;color:#666">New Status</td>
            <td style="padding:6px 0;font-weight:600">{status_label}</td></tr>
      </table>
      {notes_block}
      {"<p><a href='" + track_url + "' style='color:#E8510A'>View your report</a></p>" if track_url else ""}
      <p style="color:#666;font-size:13px">Thank you for helping make our roads safer!</p>
    </div>
    """
    await _send(contact, f"[{APP_NAME}] Report Update — {ref_code} is now {status_label}", html)
