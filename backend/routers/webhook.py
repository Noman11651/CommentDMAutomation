from fastapi import APIRouter, Request, Query, HTTPException
from config import VERIFY_TOKEN
from services.instagram import send_dm, reply_to_comment
from services.config_manager import get_reel_config, is_reel_configured

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
                value = change.get("value", {})
                comment_id = value.get("id")
                comment_text = value.get("text", "").strip().lower()
                media_id = value.get("media", {}).get("id")
                
                if not comment_id or not media_id:
                    continue

                # Robust per-reel behavior: only process reels with explicit config.
                if not is_reel_configured(media_id):
                    print(f"[webhook] skip media_id={media_id}: no explicit reel config")
                    continue
                
                config = get_reel_config(media_id)
                
                if not config.get("active"):
                    print(f"[webhook] skip media_id={media_id}: reel inactive")
                    continue
                
                trigger = config.get("trigger_keyword", "").strip().lower()
                if not trigger:
                    print(f"[webhook] skip media_id={media_id}: missing trigger keyword")
                    continue

                if trigger and trigger in comment_text:
                    dm_message = config.get("dm_message", "")
                    comment_reply = config.get("comment_reply", "")
                    print(
                        f"[webhook] matched media_id={media_id} comment_id={comment_id} trigger={trigger}"
                    )
                    
                    if dm_message:
                        dm_result = send_dm(comment_id, dm_message)
                        if isinstance(dm_result, dict) and dm_result.get("error"):
                            print(
                                f"[webhook] DM failed comment_id={comment_id}: {dm_result['error']}"
                            )
                        else:
                            print(f"[webhook] DM sent comment_id={comment_id}")
                    
                    if comment_reply:
                        reply_result = reply_to_comment(comment_id, comment_reply)
                        if isinstance(reply_result, dict) and reply_result.get("error"):
                            print(
                                f"[webhook] reply failed comment_id={comment_id}: {reply_result['error']}"
                            )
                        else:
                            print(f"[webhook] comment reply sent comment_id={comment_id}")
                else:
                    print(
                        f"[webhook] no match media_id={media_id} trigger={trigger} comment={comment_text}"
                    )
    
    return {"status": "ok"}
