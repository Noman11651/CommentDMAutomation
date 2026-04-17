from fastapi import APIRouter, Request, Query, HTTPException
import re
import time
from config import VERIFY_TOKEN
from services.instagram import (
    send_dm,
    reply_to_comment,
    send_text_dm,
    send_quick_replies_dm,
    send_button_template_dm,
)
from services import flow_engine
from services.config_manager import (
    get_reel_config,
    is_reel_configured,
    enqueue_dm,
    process_dm_queue,
    record_analytics,
    upsert_contact,
)

router = APIRouter(prefix="/webhook", tags=["webhook"])

@router.get("")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge")
):
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return int(hub_challenge)
    raise HTTPException(status_code=403, detail="Verification failed")

@router.post("")
async def handle_webhook(request: Request):
    return {"status": "paused"}
    
    body = await request.json()

    if body.get("object") != "instagram":
        return {"status": "ignored"}
    for entry in body.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") == "comments":
                _handle_comment_change(change.get("value", {}))
        for event in entry.get("messaging", []):
            _handle_messaging_event(event)

    process_dm_queue(_send_queue_job)
    return {"status": "ok"}


def _keyword_matches(comment_text: str, trigger: str) -> bool:
    text = str(comment_text or "").strip().lower()
    keyword = str(trigger or "").strip().lower()
    if not text or not keyword:
        return False
    # Exact spelling, case-insensitive; punctuation around keyword allowed.
    if " " in keyword:
        return re.search(rf"(^|\W){re.escape(keyword)}($|\W)", text) is not None
    return keyword in re.findall(r"[a-z0-9_]+", text)


def _send_queue_job(job: dict) -> dict:
    payload_type = job.get("payload_type")
    recipient = job.get("recipient")
    recipient_type = job.get("recipient_type")
    payload = job.get("payload", {})

    if payload_type == "text":
        if recipient_type == "comment_id":
            return send_dm(recipient, payload.get("text", ""))
        return send_text_dm(recipient, payload.get("text", ""))
    if payload_type == "quick_replies":
        return send_quick_replies_dm(recipient, payload.get("text", ""), payload.get("options", []))
    if payload_type == "button_template":
        return send_button_template_dm(
            recipient,
            payload.get("title", "Info"),
            payload.get("subtitle", ""),
            payload.get("image_url", ""),
            payload.get("buttons", []),
        )
    return {"error": {"message": f"unsupported_payload_type:{payload_type}"}}


def _handle_comment_change(value: dict):
    comment_id = value.get("id")
    comment_text = value.get("text", "")
    media_id = value.get("media", {}).get("id")
    sender_id = value.get("from", {}).get("id")
    sender_id = str(sender_id) if sender_id else ""

    if not comment_id or not media_id:
        return

    if not is_reel_configured(media_id):
        print(f"[webhook] skip media_id={media_id}: no explicit reel config")
        return

    config = get_reel_config(media_id)
    if not config.get("active"):
        print(f"[webhook] skip media_id={media_id}: reel inactive")
        return

    trigger = config.get("trigger_keyword", "")
    if not trigger:
        print(f"[webhook] skip media_id={media_id}: missing trigger keyword")
        return

    if not _keyword_matches(comment_text, trigger):
        print(f"[webhook] no match media_id={media_id} trigger={trigger} comment={comment_text}")
        return

    sender_key = sender_id or f"comment:{comment_id}"
    record_analytics("trigger_matched", sender_id=sender_key, media_id=media_id, trigger=trigger)
    print(f"[webhook] matched media_id={media_id} comment_id={comment_id} trigger={trigger}")

    dm_message = config.get("dm_message", "")
    flow_id = str(config.get("flow_id", "")).strip()

    if sender_id:
        upsert_contact(sender_id, {"last_triggered_at": int(time.time())})

    if flow_id and sender_id:
        flow_result = flow_engine.execute_flow(sender_id, flow_id)
        print(f"[webhook] flow_start sender={sender_id} flow={flow_id} result={flow_result}")
    elif dm_message:
        enqueue_dm(
            recipient=comment_id,
            recipient_type="comment_id",
            payload_type="text",
            payload={"text": dm_message},
            metadata={"media_id": media_id, "comment_id": comment_id},
        )

    comment_reply = config.get("comment_reply", "")
    if comment_reply:
        reply_result = reply_to_comment(comment_id, comment_reply)
        if isinstance(reply_result, dict) and reply_result.get("error"):
            print(f"[webhook] reply failed comment_id={comment_id}: {reply_result['error']}")
        else:
            print(f"[webhook] comment reply sent comment_id={comment_id}")
            record_analytics("comment_reply_sent", media_id=media_id, comment_id=comment_id)


def _extract_payload_from_event(event: dict) -> tuple[str, str]:
    msg = event.get("message", {}) or {}
    quick = msg.get("quick_reply", {}) or {}
    postback = event.get("postback", {}) or {}
    payload = (
        str(quick.get("payload") or postback.get("payload") or msg.get("text") or "").strip()
    )
    kind = "quick_reply" if quick.get("payload") else "postback" if postback.get("payload") else "text"
    return payload, kind


def _handle_messaging_event(event: dict):
    sender_id = str((event.get("sender") or {}).get("id") or "").strip()
    if not sender_id:
        return
    payload, kind = _extract_payload_from_event(event)
    if not payload:
        return
    upsert_contact(sender_id, {"last_message_at": int(time.time())})
    result = flow_engine.handle_response(sender_id, payload)
    print(f"[webhook] messaging sender={sender_id} kind={kind} payload={payload} result={result}")
