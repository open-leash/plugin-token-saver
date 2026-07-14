from __future__ import annotations

import hashlib
import hmac
import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from headroom.transforms.content_router import ContentRouter, ContentRouterConfig

PROTOCOL = "openleash-container-plugin.v1"
PLUGIN_ID = "openleash.prompt-compression"
DATA_DIR = Path(os.environ.get("OPENLEASH_PLUGIN_DATA_DIR", "/data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "ccr.sqlite3"
SECRET = os.environ.get("OPENLEASH_PLUGIN_RUNTIME_SECRET", "")
MAX_CLOCK_SKEW_MS = 5 * 60 * 1000

app = FastAPI(title="OpenLeash Token Saver", docs_url=None, redoc_url=None)
_compressor_lock = threading.RLock()
_compressors: dict[str, ContentRouter] = {}


def _db() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.execute("pragma journal_mode=wal")
    connection.execute(
        """create table if not exists ccr_entries (
             tenant_id text not null,
             session_id text not null,
             content_hash text not null,
             content text not null,
             expires_at integer not null,
             created_at integer not null,
             primary key (tenant_id, session_id, content_hash)
           )"""
    )
    return connection


def _compressor(level: str) -> ContentRouter:
    with _compressor_lock:
        if level not in _compressors:
            _compressors[level] = ContentRouter(
                ContentRouterConfig(
                    enable_kompress=True,
                    enable_smart_crusher=True,
                    enable_search_compressor=True,
                    enable_log_compressor=True,
                    enable_tabular_compressor=True,
                    skip_user_messages=False,
                    protect_recent_code=0,
                    protect_analysis_context=False,
                    lossless=False,
                )
            )
        return _compressors[level]


async def _verified_json(request: Request) -> dict[str, Any]:
    raw = await request.body()
    if SECRET:
        timestamp = request.headers.get("x-openleash-timestamp", "")
        signature = request.headers.get("x-openleash-signature", "")
        try:
            if abs(int(time.time() * 1000) - int(timestamp)) > MAX_CLOCK_SKEW_MS:
                raise ValueError("stale")
        except ValueError as error:
            raise HTTPException(401, "invalid plugin request timestamp") from error
        expected = hmac.new(
            SECRET.encode(), f"{timestamp}.".encode() + raw, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, f"sha256={expected}"):
            raise HTTPException(401, "invalid plugin request signature")
    try:
        body = json.loads(raw)
    except json.JSONDecodeError as error:
        raise HTTPException(400, "invalid JSON") from error
    if body.get("protocol") != PROTOCOL:
        raise HTTPException(409, "incompatible plugin protocol")
    if body.get("plugin", {}).get("id") != PLUGIN_ID:
        raise HTTPException(400, "wrong plugin id")
    return body


@app.on_event("startup")
def startup() -> None:
    with _db() as connection:
        connection.execute("delete from ccr_entries where expires_at <= ?", (int(time.time()),))


@app.get("/healthz")
def health() -> dict[str, Any]:
    return {"ok": True, "pluginId": PLUGIN_ID, "protocol": PROTOCOL}


@app.post("/v1/transform")
async def transform(request: Request) -> dict[str, Any]:
    envelope = await _verified_json(request)
    payload = envelope.get("payload")
    if not isinstance(payload, dict):
        raise HTTPException(400, "payload must be an object")
    config = envelope.get("config") if isinstance(envelope.get("config"), dict) else {}
    if config.get("enabled") is False:
        return _response(envelope, "skipped", [], {"reason": "disabled"}, [])
    level = str(config.get("level", "standard"))
    minimum_chars = max(256, int(config.get("minimumChars", 1200)))
    protect_recent = max(0, int(config.get("protectRecent", 2)))
    ccr_enabled = bool(config.get("ccrEnabled", False))
    ttl_seconds = max(60, int(config.get("ccrTtlSeconds", 3600)))
    tenant_id = str(envelope.get("tenant", {}).get("organizationId", ""))
    session_id = str(envelope.get("context", {}).get("sessionId", "proxy"))

    transformed = json.loads(json.dumps(payload))
    before = len(json.dumps(payload, separators=(",", ":")))
    hashes: list[str] = []
    strategies: list[str] = []

    messages = transformed.get("messages")
    if isinstance(messages, list):
        changed = _compress_messages(
            messages,
            level,
            minimum_chars,
            protect_recent,
            ccr_enabled,
            ttl_seconds,
            tenant_id,
            session_id,
            hashes,
            strategies,
        )
        if not changed:
            transformed["messages"] = messages

    input_items = transformed.get("input")
    if isinstance(input_items, list):
        _compress_response_items(
            input_items,
            level,
            minimum_chars,
            ccr_enabled,
            ttl_seconds,
            tenant_id,
            session_id,
            hashes,
            strategies,
        )

    patches = []
    for key in ("messages", "input"):
        if transformed.get(key) != payload.get(key):
            patches.append({"op": "replace", "path": f"/{key}", "value": transformed[key]})
    after = len(json.dumps(transformed, separators=(",", ":")))
    metrics = {
        "charactersBefore": before,
        "charactersAfter": after,
        "charactersSaved": max(0, before - after),
        "tokensBefore": max(1, before // 4),
        "tokensAfter": max(1, after // 4),
        "tokensSaved": max(0, (before - after) // 4),
        "headroom": True,
        "strategies": ",".join(sorted(set(strategies))),
    }
    status = "modified" if patches else "unchanged"
    return _response(envelope, status, patches, metrics, hashes)


@app.post("/v1/tools/execute")
async def execute_tool(request: Request) -> dict[str, Any]:
    envelope = await _verified_json(request)
    if envelope.get("tool") not in {"headroom_retrieve", "retrieve"}:
        raise HTTPException(400, "unsupported Token Saver tool")
    arguments = envelope.get("arguments") if isinstance(envelope.get("arguments"), dict) else {}
    content_hash = str(arguments.get("hash", ""))
    tenant_id = str(envelope.get("tenant", {}).get("organizationId", ""))
    session_id = str(envelope.get("context", {}).get("sessionId", "proxy"))
    with _db() as connection:
        row = connection.execute(
            """select content from ccr_entries
               where tenant_id = ? and session_id = ? and content_hash = ? and expires_at > ?""",
            (tenant_id, session_id, content_hash, int(time.time())),
        ).fetchone()
    if not row:
        raise HTTPException(404, "CCR content not found or expired")
    return {
        "protocol": PROTOCOL,
        "requestId": envelope.get("requestId"),
        "status": "ok",
        "content": row[0],
    }


def _compress_messages(
    messages: list[Any],
    level: str,
    minimum_chars: int,
    protect_recent: int,
    ccr_enabled: bool,
    ttl_seconds: int,
    tenant_id: str,
    session_id: str,
    hashes: list[str],
    strategies: list[str],
) -> bool:
    changed = False
    protected_from = max(0, len(messages) - protect_recent)
    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            continue
        role = str(message.get("role", ""))
        content = message.get("content")
        if isinstance(content, str):
            eligible = role == "tool" or index < protected_from
            if eligible:
                compressed = _compress_text(
                    content, level, minimum_chars, ccr_enabled, ttl_seconds,
                    tenant_id, session_id, hashes, strategies,
                )
                if compressed != content:
                    message["content"] = compressed
                    changed = True
        elif isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                kind = str(block.get("type", ""))
                is_tool_result = kind in {"tool_result", "function_call_output"}
                if not is_tool_result and index >= protected_from:
                    continue
                for field in ("content", "output", "text"):
                    value = block.get(field)
                    if isinstance(value, str):
                        compressed = _compress_text(
                            value, level, minimum_chars, ccr_enabled, ttl_seconds,
                            tenant_id, session_id, hashes, strategies,
                        )
                        if compressed != value:
                            block[field] = compressed
                            changed = True
    return changed


def _compress_response_items(
    items: list[Any], level: str, minimum_chars: int, ccr_enabled: bool,
    ttl_seconds: int, tenant_id: str, session_id: str, hashes: list[str],
    strategies: list[str],
) -> None:
    for item in items:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("type", ""))
        if "output" not in kind:
            continue
        for field in ("output", "content"):
            value = item.get(field)
            if isinstance(value, str):
                item[field] = _compress_text(
                    value, level, minimum_chars, ccr_enabled, ttl_seconds,
                    tenant_id, session_id, hashes, strategies,
                )


def _compress_text(
    value: str, level: str, minimum_chars: int, ccr_enabled: bool,
    ttl_seconds: int, tenant_id: str, session_id: str, hashes: list[str],
    strategies: list[str],
) -> str:
    if len(value) < minimum_chars:
        return value
    with _compressor_lock:
        bias = {"light": 1.35, "standard": 1.0, "maximum": 0.75}.get(level, 1.0)
        result = _compressor(level).compress(value, bias=bias)
    compressed = result.compressed
    if not compressed or len(compressed) >= len(value) * 0.98:
        return value
    strategies.append(result.strategy_used.value)
    if not ccr_enabled:
        return compressed
    content_hash = hashlib.sha256(value.encode()).hexdigest()[:24]
    expires_at = int(time.time()) + ttl_seconds
    with _db() as connection:
        connection.execute(
            """insert into ccr_entries
               (tenant_id, session_id, content_hash, content, expires_at, created_at)
               values (?, ?, ?, ?, ?, ?)
               on conflict (tenant_id, session_id, content_hash) do update set
                 content = excluded.content, expires_at = excluded.expires_at""",
            (tenant_id, session_id, content_hash, value, expires_at, int(time.time())),
        )
    hashes.append(content_hash)
    return f"{compressed}\n\n[OpenLeash CCR:{content_hash}; original available through Token Saver retrieval]"


def _response(
    envelope: dict[str, Any], status: str, patches: list[dict[str, Any]],
    metrics: dict[str, Any], hashes: list[str],
) -> dict[str, Any]:
    tokens_before = int(metrics.get("tokensBefore", 0) or 0)
    tokens_after = int(metrics.get("tokensAfter", 0) or 0)
    tokens_saved = int(metrics.get("tokensSaved", 0) or 0)
    return {
        "protocol": PROTOCOL,
        "requestId": envelope.get("requestId"),
        "status": status,
        "patches": patches,
        "metrics": metrics,
        "ccrHashes": hashes,
        "summary": "Headroom compression applied locally." if patches else "Headroom found no safe compression opportunity.",
        "emissions": {
            "logs": [{
                "level": "info",
                "category": "plugin",
                "code": "headroom-compression",
                "message": "Headroom compressed the provider request." if patches else "Headroom found no safe compression opportunity.",
                "data": {
                    "status": status,
                    "charactersBefore": metrics.get("charactersBefore", 0),
                    "charactersAfter": metrics.get("charactersAfter", 0),
                    "charactersSaved": metrics.get("charactersSaved", 0),
                    "tokensSaved": tokens_saved,
                    "strategies": metrics.get("strategies", ""),
                    "ccrEntries": len(hashes),
                },
            }],
            "usage": [{
                "kind": "llm.tokens",
                "provider": "headroom",
                "quantity": tokens_after,
                "unit": "tokens-after-compression",
                "inputTokens": tokens_before,
                "savedTokens": tokens_saved,
                "details": {
                    "compressionEngine": "headroom",
                    "status": status,
                    "strategies": metrics.get("strategies", ""),
                },
            }],
        },
    }
