import time
from typing import Any, Optional

from services import config_manager
from services import instagram


def _enqueue_text(recipient_id: str, text: str, metadata: dict[str, Any]) -> None:
    config_manager.enqueue_dm(
        recipient=recipient_id,
        recipient_type="id",
        payload_type="text",
        payload={"text": text},
        metadata=metadata,
    )


def _enqueue_quick_reply(
    recipient_id: str, text: str, options: list[dict[str, Any]], metadata: dict[str, Any]
) -> None:
    config_manager.enqueue_dm(
        recipient=recipient_id,
        recipient_type="id",
        payload_type="quick_replies",
        payload={"text": text, "options": options},
        metadata=metadata,
    )


def _enqueue_button_template(
    recipient_id: str, step: dict[str, Any], metadata: dict[str, Any]
) -> None:
    config_manager.enqueue_dm(
        recipient=recipient_id,
        recipient_type="id",
        payload_type="button_template",
        payload={
            "title": step.get("title", "Info"),
            "subtitle": step.get("subtitle", ""),
            "image_url": step.get("image_url", ""),
            "buttons": step.get("buttons", []),
        },
        metadata=metadata,
    )


def _index_steps(flow: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(step.get("id")): step for step in flow.get("steps", []) if step.get("id")}


def _first_step_id(flow: dict[str, Any]) -> Optional[str]:
    steps = flow.get("steps", [])
    if not steps:
        return None
    return str(steps[0].get("id")) if steps[0].get("id") else None


def _save_contact_state(
    sender_id: str,
    flow_id: str,
    step_id: Optional[str],
    awaiting_map: Optional[dict[str, str]] = None,
) -> None:
    config_manager.upsert_contact(
        sender_id,
        {
            "state": {"flow_id": flow_id, "step_id": step_id or ""},
            "awaiting_map": awaiting_map or {},
        },
    )


def _clear_contact_state(sender_id: str) -> None:
    config_manager.clear_contact_state(sender_id)


def execute_flow(sender_id: str, flow_id: str, start_step_id: Optional[str] = None, trigger_comment_id: Optional[str] = None) -> dict[str, Any]:
    flow = config_manager.get_flow(flow_id)
    if not flow:
        return {"error": {"message": f"flow_not_found:{flow_id}"}}

    step_map = _index_steps(flow)
    current_step_id = start_step_id or _first_step_id(flow)
    if not current_step_id or current_step_id not in step_map:
        return {"error": {"message": "flow_missing_start_step"}}

    # Protect from bad cyclic configs.
    for _ in range(20):
        step = step_map.get(current_step_id)
        if not step:
            _clear_contact_state(sender_id)
            return {"status": "ended", "reason": "step_not_found"}

        step_type = str(step.get("type", "text"))
        config_manager.record_analytics(
            "flow_step_executed", sender_id=sender_id, flow_id=flow_id, step_id=current_step_id, step_type=step_type
        )

        if step_type == "end":
            _clear_contact_state(sender_id)
            return {"status": "ended"}

        if step_type == "condition":
            contact = config_manager.get_contact(sender_id) or {}
            if step.get("condition", {}).get("check") == "follow_confirmed":
                is_true = bool(contact.get("follow_confirmed"))
                # Prefer live IG follow status when available; fallback to cached flag.
                follow_status = instagram.get_user_follow_status(sender_id)
                if isinstance(follow_status, dict) and not follow_status.get("error"):
                    if "is_user_follow_business" in follow_status:
                        is_true = bool(follow_status.get("is_user_follow_business"))
                        config_manager.upsert_contact(
                            sender_id,
                            {
                                "follow_confirmed": is_true,
                                "follow_status_checked_at": int(time.time()),
                            },
                        )
                current_step_id = step.get("condition", {}).get("onTrue" if is_true else "onFalse")
                if not current_step_id:
                    _clear_contact_state(sender_id)
                    return {"status": "ended", "reason": "condition_missing_branch"}
                continue
            _clear_contact_state(sender_id)
            return {"status": "ended", "reason": "unsupported_condition"}

        if step_type == "text":
            recip_id = trigger_comment_id if trigger_comment_id else sender_id
            recip_type = "comment_id" if trigger_comment_id else "id"
            next_step_id = step.get("next_step_id")
            next_step = step_map.get(str(next_step_id)) if next_step_id else None

            # If using comment_id (private reply) and next step is quick_reply, combine them
            if recip_type == "comment_id" and next_step and next_step.get("type") == "quick_reply":
                options = next_step.get("quick_replies", [])
                config_manager.enqueue_dm(
                    recipient=recip_id,
                    recipient_type=recip_type,
                    payload_type="text_with_quick_replies",
                    payload={
                        "text": str(step.get("message", "")),
                        "options": options,
                    },
                    metadata={"flow_id": flow_id, "step_id": current_step_id},
                )
                # Build awaiting_map for quick_reply step
                awaiting_map = {}
                for option in options:
                    payload = str(option.get("payload", "")).strip()
                    next_id = str(option.get("next_step_id", "")).strip()
                    if payload and next_id:
                        awaiting_map[payload] = next_id
                _save_contact_state(sender_id, flow_id, str(next_step_id), awaiting_map)
                return {"status": "waiting_quick_reply"}

            # Normal text message
            config_manager.enqueue_dm(
                recipient=recip_id,
                recipient_type=recip_type,
                payload_type="text",
                payload={"text": str(step.get("message", ""))},
                metadata={"flow_id": flow_id, "step_id": current_step_id},
            )
            trigger_comment_id = None  # Only use comment_id for the first text message
            if not next_step_id:
                _clear_contact_state(sender_id)
                return {"status": "ended"}
            current_step_id = str(next_step_id)
            continue

        if step_type == "quick_reply":
            options = step.get("quick_replies", [])

            # If this is the first step triggered via comment_id, convert to text_with_quick_replies
            if trigger_comment_id and current_step_id == _first_step_id(flow):
                config_manager.enqueue_dm(
                    recipient=trigger_comment_id,
                    recipient_type="comment_id",
                    payload_type="text_with_quick_replies",
                    payload={
                        "text": str(step.get("message", "")),
                        "options": options,
                    },
                    metadata={"flow_id": flow_id, "step_id": current_step_id},
                )
                awaiting_map = {}
                for option in options:
                    payload = str(option.get("payload", "")).strip()
                    next_id = str(option.get("next_step_id", "")).strip()
                    if payload and next_id:
                        awaiting_map[payload] = next_id
                _save_contact_state(sender_id, flow_id, current_step_id, awaiting_map)
                return {"status": "waiting_quick_reply"}

            # Normal quick_reply (not first step or no comment_id)
            _enqueue_quick_reply(
                sender_id,
                str(step.get("message", "")),
                options,
                {"flow_id": flow_id, "step_id": current_step_id},
            )
            awaiting_map = {}
            for option in options:
                payload = str(option.get("payload", "")).strip()
                next_id = str(option.get("next_step_id", "")).strip()
                if payload and next_id:
                    awaiting_map[payload] = next_id
            _save_contact_state(sender_id, flow_id, current_step_id, awaiting_map)
            return {"status": "waiting_quick_reply"}

        if step_type == "button_template":
            _enqueue_button_template(
                sender_id,
                step,
                {"flow_id": flow_id, "step_id": current_step_id},
            )
            awaiting_map = {}
            for button in step.get("buttons", []):
                if button.get("type") != "postback":
                    continue
                payload = str(button.get("payload", "")).strip()
                next_id = str(button.get("next_step_id", "")).strip()
                if payload and next_id:
                    awaiting_map[payload] = next_id
            _save_contact_state(sender_id, flow_id, current_step_id, awaiting_map)
            return {"status": "waiting_postback"}

        _clear_contact_state(sender_id)
        return {"status": "ended", "reason": f"unsupported_step_type:{step_type}"}

    _clear_contact_state(sender_id)
    return {"status": "ended", "reason": "step_limit_exceeded"}


def handle_response(sender_id: str, payload: str) -> dict[str, Any]:
    payload = str(payload or "").strip()
    if not payload:
        return {"status": "ignored", "reason": "empty_payload"}

    contact = config_manager.get_contact(sender_id) or {}
    state = contact.get("state", {})
    awaiting_map = contact.get("awaiting_map", {})
    flow_id = str(state.get("flow_id", "")).strip()

    if payload.upper() == "FOLLOW_CONFIRMED":
        config_manager.upsert_contact(sender_id, {"follow_confirmed": True})

    next_step_id = awaiting_map.get(payload)
    if not flow_id or not next_step_id:
        return {"status": "ignored", "reason": "no_waiting_mapping"}

    config_manager.record_analytics("quick_reply_response", sender_id=sender_id, payload=payload, flow_id=flow_id)
    return execute_flow(sender_id, flow_id, start_step_id=next_step_id)
