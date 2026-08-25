from __future__ import annotations

from datetime import datetime, timezone


def parse_timestamp(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def serialize_model(model) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    raise TypeError(f"unsupported model type: {type(model)}")


def serialize_models(models: list) -> list[dict]:
    return [serialize_model(item) for item in models]
