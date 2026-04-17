import requests
from config import INSTAGRAM_ACCESS_TOKEN, IG_BUSINESS_ACCOUNT_ID

GRAPH_API_URL = "https://graph.instagram.com"
REQUEST_TIMEOUT = 20


def _safe_post(path: str, payload: dict, params: dict | None = None):
    try:
        response = requests.post(
            f"{GRAPH_API_URL}{path}",
            json=payload,
            params=params or {"access_token": INSTAGRAM_ACCESS_TOKEN},
            timeout=REQUEST_TIMEOUT,
        )
        return response.json()
    except requests.RequestException as e:
        return {"error": {"message": str(e), "type": "request_exception"}}


def send_dm(comment_id: str, message: str):
    payload = {
        "recipient": {"comment_id": comment_id},
        "message": {"text": message},
    }
    return _safe_post("/me/messages", payload)


def send_text_dm(recipient_id: str, message: str):
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": message},
    }
    return _safe_post("/me/messages", payload)


def send_quick_replies_dm(recipient_id: str, text: str, options: list[dict]):
    quick_replies = []
    for opt in options:
        title = str(opt.get("title", "")).strip()[:20]
        payload = str(opt.get("payload", "")).strip()
        if title and payload:
            quick_replies.append(
                {"content_type": "text", "title": title, "payload": payload}
            )
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text, "quick_replies": quick_replies},
    }
    return _safe_post("/me/messages", payload)


def send_button_text_template_dm(recipient_id: str, text: str, options: list[dict]):
    """
    Button template: one text block with up to 3 stacked postback buttons (full-width under the
    message). Use instead of quick_replies when you want Manychat-style vertical buttons.
    """
    buttons = []
    for opt in options:
        title = str(opt.get("title", "")).strip()[:20]
        payload = str(opt.get("payload", "")).strip()
        if title and payload:
            buttons.append({"type": "postback", "title": title, "payload": payload})
    buttons = buttons[:3]
    if not buttons:
        return {"error": {"message": "button_template_requires_at_least_one_button"}}

    body_text = str(text or "").strip()[:640]
    payload = {
        "recipient": {"id": recipient_id},
        "message": {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "button",
                    "text": body_text,
                    "buttons": buttons,
                },
            }
        },
    }
    return _safe_post("/me/messages", payload)


def send_button_template_dm(
    recipient_id: str,
    title: str,
    subtitle: str,
    image_url: str,
    buttons: list[dict],
):
    normalized_buttons = []
    for button in buttons:
        b_type = button.get("type")
        b_title = str(button.get("title", "")).strip()[:20]
        if b_type not in ("web_url", "postback") or not b_title:
            continue
        out = {"type": b_type, "title": b_title}
        if b_type == "web_url":
            url = str(button.get("url", "")).strip()
            if not url:
                continue
            out["url"] = url
        else:
            payload = str(button.get("payload", "")).strip()
            if not payload:
                continue
            out["payload"] = payload
        normalized_buttons.append(out)

    payload = {
        "recipient": {"id": recipient_id},
        "message": {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "generic",
                    "elements": [
                        {
                            "title": title,
                            "subtitle": subtitle,
                            "image_url": image_url,
                            "buttons": normalized_buttons,
                        }
                    ],
                },
            }
        },
    }
    return _safe_post("/me/messages", payload)


def reply_to_comment(comment_id: str, message: str):
    payload = {"message": message}
    return _safe_post(f"/{comment_id}/replies", payload)


def get_account_media():
    params = {
        "access_token": INSTAGRAM_ACCESS_TOKEN,
        "fields": "id,media_type,media_url,thumbnail_url,permalink,caption",
        "limit": 100,
    }
    try:
        response = requests.get(
            f"{GRAPH_API_URL}/me/media", params=params, timeout=REQUEST_TIMEOUT
        )
        data = response.json()
    except requests.RequestException as e:
        print(f"Instagram API Error: {e}")
        return []

    if "error" in data:
        print(f"Instagram API Error: {data['error']}")
        return []

    return data.get("data", [])
