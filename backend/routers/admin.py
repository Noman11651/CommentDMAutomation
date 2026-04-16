from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from services.instagram import (
    get_account_media,
    send_dm,
    reply_to_comment,
    send_text_dm,
    send_quick_replies_dm,
    send_button_template_dm,
)
from services.config_manager import (
    get_all_configs,
    update_reel_config,
    get_reel_config,
    list_flows,
    upsert_flow,
    get_queue_status,
    process_dm_queue,
    get_analytics_summary,
)

router = APIRouter(prefix="/api", tags=["admin"])

class ReelConfigUpdate(BaseModel):
    trigger_keyword: str
    dm_message: str
    comment_reply: str
    active: bool
    flow_id: str = ""

class TestDMRequest(BaseModel):
    comment_id: str
    message: str

class TestReplyRequest(BaseModel):
    comment_id: str
    message: str

class FlowPayload(BaseModel):
    id: str | None = None
    name: str
    steps: list[dict[str, Any]] = Field(default_factory=list)


def _send_queue_job(job: dict[str, Any]) -> dict[str, Any]:
    payload_type = job.get("payload_type")
    recipient = job.get("recipient")
    recipient_type = job.get("recipient_type")
    payload = job.get("payload", {})

    if payload_type == "text":
        if recipient_type == "comment_id":
            return send_dm(recipient, payload.get("text", ""))
        return send_text_dm(recipient, payload.get("text", ""))

    if payload_type == "quick_replies":
        return send_quick_replies_dm(
            recipient,
            payload.get("text", ""),
            payload.get("options", []),
        )

    if payload_type == "button_template":
        return send_button_template_dm(
            recipient,
            payload.get("title", "Info"),
            payload.get("subtitle", ""),
            payload.get("image_url", ""),
            payload.get("buttons", []),
        )

    return {"error": {"message": f"unsupported_payload_type:{payload_type}"}}


@router.get("/reels")
async def fetch_reels():
    try:
        media_items = get_account_media()
        configs = get_all_configs()
        
        reels = []
        for item in media_items:
            media_id = item["id"]
            config = configs["reels"].get(media_id, configs["default"])
            
            reels.append({
                "id": media_id,
                "thumbnail_url": item.get("thumbnail_url", item.get("media_url")),
                "permalink": item.get("permalink"),
                "caption": item.get("caption", "")[:100],
                "config": config
            })
        
        return {"reels": reels, "total": len(reels)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/reels/{media_id}")
async def get_reel(media_id: str):
    config = get_reel_config(media_id)
    return {"media_id": media_id, "config": config}

@router.put("/reels/{media_id}")
async def update_reel(media_id: str, config: ReelConfigUpdate):
    try:
        update_reel_config(media_id, config.dict())
        return {"status": "updated", "media_id": media_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats")
async def get_stats():
    try:
        media_items = get_account_media()
        configs = get_all_configs()
        analytics = get_analytics_summary()
        queue = get_queue_status()

        total = len(media_items)
        configured = 0
        using_default = 0

        for item in media_items:
            media_id = item["id"]
            if media_id in configs["reels"]:
                configured += 1
            else:
                using_default += 1

        return {
            "total_reels": total,
            "configured": configured,
            "using_default": using_default,
            "analytics": analytics,
            "queue": queue,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/flows")
async def get_flows():
    try:
        return {"flows": list_flows()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/flows")
async def save_flow(payload: FlowPayload):
    try:
        flow = upsert_flow(payload.dict())
        return {"status": "saved", "flow": flow}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/queue/process")
async def run_queue():
    try:
        result = process_dm_queue(_send_queue_job)
        return {"status": "processed", **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/queue/status")
async def queue_status():
    try:
        return get_queue_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/test/send-dm")
async def test_send_dm(request: TestDMRequest):
    """Test endpoint to manually send a DM using a comment_id"""
    try:
        result = send_dm(request.comment_id, request.message)
        return {"status": "success", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/test/reply-comment")
async def test_reply_comment(request: TestReplyRequest):
    """Test endpoint to manually reply to a comment"""
    try:
        result = reply_to_comment(request.comment_id, request.message)
        return {"status": "success", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
