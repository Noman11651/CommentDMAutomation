from fastapi import APIRouter, Request, Query, HTTPException
import random
import re
import time
from config import (
    VERIFY_TOKEN,
    IG_BUSINESS_ACCOUNT_ID,
    FLOW_START_COOLDOWN_SECONDS,
    INBOUND_PAYLOAD_DEDUP_SECONDS,
)
from services.instagram import (
    send_dm,
    reply_to_comment,
    send_text_dm,
    send_quick_replies_dm,
    send_button_text_template_dm,
    send_button_template_dm,
)
from services import flow_engine
from services.config_manager import (
    get_reel_config,
    is_reel_configured,
    try_claim_webhook_event,
    get_contact,
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
    body = await request.json()

    if body.get("object") != "instagram":
        return {"status": "ignored"}

    for entry in body.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") == "comments":
                val = change.get("value") or {}
                _handle_comment_change(val)
                break
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
    if payload_type == "text_with_quick_replies":
        if recipient_type == "comment_id":
            return send_dm(recipient, payload.get("text", ""), quick_replies=payload.get("options", []))
        # Fallback if somehow called with id recipient (shouldn't happen)
        return send_quick_replies_dm(recipient, payload.get("text", ""), payload.get("options", []))
    if payload_type == "quick_replies":
        opts = payload.get("options", [])
        text = payload.get("text", "")
        # Stacked full-width buttons (button template); Instagram allows max 3 per template.
        if len(opts) <= 3:
            result = send_button_text_template_dm(recipient, text, opts)
            if not result.get("error"):
                return result
            print(f"[webhook] button template failed, falling back to quick_replies: {result.get('error')}")
        return send_quick_replies_dm(recipient, text, opts)
    if payload_type == "button_template":
        return send_button_template_dm(
            recipient,
            payload.get("title", "Info"),
            payload.get("subtitle", ""),
            payload.get("image_url", ""),
            payload.get("buttons", []),
        )
    return {"error": {"message": f"unsupported_payload_type:{payload_type}"}}


def _is_recent_flow_start(sender_id: str, media_id: str, now_ts: int) -> bool:
    if FLOW_START_COOLDOWN_SECONDS <= 0:
        return False
    contact = get_contact(sender_id) or {}
    last_media = str(contact.get("last_flow_start_media_id", "")).strip()
    last_ts = int(contact.get("last_flow_start_at") or 0)
    return last_media == str(media_id) and (now_ts - last_ts) < FLOW_START_COOLDOWN_SECONDS


def _is_duplicate_inbound_payload(
    sender_id: str, payload: str, kind: str, now_ts: int
) -> bool:
    if INBOUND_PAYLOAD_DEDUP_SECONDS <= 0:
        return False
    contact = get_contact(sender_id) or {}
    last_payload = str(contact.get("last_inbound_payload", ""))
    last_kind = str(contact.get("last_inbound_kind", ""))
    last_ts = int(contact.get("last_inbound_payload_at") or 0)
    return (
        last_payload == payload
        and last_kind == kind
        and (now_ts - last_ts) < INBOUND_PAYLOAD_DEDUP_SECONDS
    )


def _pick_comment_reply(config: dict) -> str:
    replies = config.get("comment_replies") or []
    if isinstance(replies, list):
        clean = [str(item).strip() for item in replies if str(item).strip()]
        if clean:
            return random.choice(clean)
    return str(config.get("comment_reply", "")).strip()


def _handle_comment_change(value: dict):
    comment_id = value.get("id")
    comment_text = value.get("text", "")
    media_id = value.get("media", {}).get("id")
    sender_id = value.get("from", {}).get("id")
    sender_id = str(sender_id) if sender_id else ""

    if not comment_id or not media_id:
        return

    # Ignore nested thread replies (only automate top-level comments on the reel).
    if value.get("parent_id"):
        print(f"[webhook] skip nested comment parent_id={value.get('parent_id')} id={comment_id}")
        return

    # Do not react to our own IG account (avoids loops when comment_reply matches the keyword).
    ig_self = str(IG_BUSINESS_ACCOUNT_ID or "").strip()
    if ig_self and sender_id == ig_self:
        print(f"[webhook] skip own IG comment sender={sender_id} id={comment_id}")
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

    # Event-level deduplication: Ensure we process this exact comment ID only once
    if not try_claim_webhook_event(f"ig_comment:{comment_id}"):
        print(f"[webhook] event dedup skip comment_id={comment_id}")
        return

    record_analytics("trigger_matched", sender_id=sender_key, media_id=media_id, trigger=trigger)
    print(f"[webhook] matched media_id={media_id} comment_id={comment_id} trigger={trigger}")

    comment_reply = _pick_comment_reply(config)
    if comment_reply:
        reply_result = reply_to_comment(comment_id, comment_reply)
        if isinstance(reply_result, dict) and reply_result.get("error"):
            print(f"[webhook] reply failed comment_id={comment_id}: {reply_result['error']}")
        else:
            print(f"[webhook] comment reply sent comment_id={comment_id}")
            record_analytics("comment_reply_sent", media_id=media_id, comment_id=comment_id)

    dm_message = config.get("dm_message", "")
    flow_id = str(config.get("flow_id", "")).strip()
    now_ts = int(time.time())

    if sender_id:
        if _is_recent_flow_start(sender_id, str(media_id), now_ts):
            print(
                f"[webhook] skip duplicate flow start sender={sender_id} media_id={media_id}"
            )
            record_analytics(
                "flow_start_cooldown_skip",
                sender_id=sender_id,
                media_id=media_id,
                cooldown_seconds=FLOW_START_COOLDOWN_SECONDS,
            )
            return
        upsert_contact(
            sender_id,
            {
                "last_triggered_at": now_ts,
                "last_flow_start_at": now_ts,
                "last_flow_start_media_id": str(media_id),
            },
        )

    if flow_id and sender_id:
        flow_result = flow_engine.execute_flow(sender_id, flow_id, trigger_comment_id=comment_id)
        print(f"[webhook] flow_start sender={sender_id} flow={flow_id} result={flow_result}")
    elif dm_message:
        enqueue_dm(
            recipient=comment_id,
            recipient_type="comment_id",
            payload_type="text",
            payload={"text": dm_message},
            metadata={"media_id": media_id, "comment_id": comment_id},
        )


def _extract_payload_from_event(event: dict) -> tuple[str, str, str]:
    msg = event.get("message", {}) or {}
    quick = msg.get("quick_reply", {}) or {}
    postback = event.get("postback", {}) or {}
    payload = (
        str(quick.get("payload") or postback.get("payload") or msg.get("text") or "").strip()
    )
    kind = "quick_reply" if quick.get("payload") else "postback" if postback.get("payload") else "text"
    event_id = str(msg.get("mid") or postback.get("mid") or "")
    return payload, kind, event_id

def _handle_messaging_event(event: dict):
    sender_id = str((event.get("sender") or {}).get("id") or "").strip()
    if not sender_id:
        return
    payload, kind, event_id = _extract_payload_from_event(event)
    if not payload:
        return
    now_ts = int(time.time())

    if event_id and not try_claim_webhook_event(f"ig_msg:{event_id}"):
        print(f"[webhook] event dedup skip messaging event_id={event_id}")
        return

    if _is_duplicate_inbound_payload(sender_id, payload, kind, now_ts):
        print(
            f"[webhook] skip duplicate inbound payload sender={sender_id} kind={kind} payload={payload}"
        )
        record_analytics(
            "inbound_payload_dedup_skip",
            sender_id=sender_id,
            kind=kind,
            payload=payload,
            cooldown_seconds=INBOUND_PAYLOAD_DEDUP_SECONDS,
        )
        return

    upsert_contact(
        sender_id,
        {
            "last_message_at": now_ts,
            "last_inbound_payload": payload,
            "last_inbound_kind": kind,
            "last_inbound_payload_at": now_ts,
        },
    )
    result = flow_engine.handle_response(sender_id, payload)
    print(f"[webhook] messaging sender={sender_id} kind={kind} payload={payload} result={result}")
