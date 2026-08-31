from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from astrbot.core.message.components import File, Image, Reply
from astrbot_plugin_angel_heart.core.config_manager import ConfigManager
from astrbot_plugin_angel_heart.roles.front_desk import FrontDesk


ROOT = Path(__file__).resolve().parents[1]


def _make_file(name: str):
    """Build a file component without assuming one AstrBot constructor shape."""

    item = File()
    item.name = name
    if not hasattr(item, "file_"):
        item.file_ = ""
    if not hasattr(item, "url"):
        item.url = ""
    return item


def _read_simple_metadata() -> dict[str, str]:
    result: dict[str, str] = {}
    for raw_line in (ROOT / "metadata.yaml").read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip().strip("\"").strip("'")
    return result


def test_cary_release_metadata_is_unambiguous():
    metadata = _read_simple_metadata()
    assert metadata["version"] == "2.2.3+cary.1"
    assert metadata["repo"] == "https://github.com/casama233/astrbot_plugin_angel_heart"
    assert "cary" in metadata["author"].casefold()


def test_absorbed_familiarity_timeout_accessor_remains_available():
    manager = ConfigManager(
        {
            "timing": {
                "observation_timeout": 60,
                "familiarity_timeout": 135,
            }
        }
    )
    assert manager.familiarity_timeout == 135
    assert ConfigManager({"timing": {"observation_timeout": 75}}).familiarity_timeout == 75


def test_media_iterator_includes_nested_quotes_and_breaks_cycles():
    direct_image = Image()
    quoted_image = Image()
    quoted_file = _make_file("quoted.md")
    outer = Reply()
    inner = Reply(chain=[quoted_image, quoted_file, outer])
    outer.chain = [inner]

    media = list(FrontDesk._iter_media_components([direct_image, outer]))

    assert media == [direct_image, quoted_image, quoted_file]
    assert getattr(FrontDesk, "_cary_quoted_media_patch_installed", False) is True


class _QuotedMediaEvent:
    def __init__(self, messages):
        self._messages = list(messages)
        self.unified_msg_origin = "aiocqhttp:GroupMessage:1"
        self.message_obj = SimpleNamespace(
            message_id="message-1",
            group=None,
            sender=SimpleNamespace(user_id="user-1", nickname="User"),
        )
        self.extras = {}

    def get_messages(self):
        return list(self._messages)

    def get_message_outline(self):
        return ""

    def get_sender_id(self):
        return "user-1"

    def get_sender_name(self):
        return "User"

    def get_self_id(self):
        return "bot-1"

    def get_timestamp(self):
        return 1_785_991_141.0

    def set_extra(self, key, value):
        self.extras[key] = value


@pytest.mark.asyncio
async def test_cache_message_caches_quoted_image_and_file():
    config = MagicMock()
    config.for_chat.return_value = SimpleNamespace(alias="", focus_instructions="")
    context = MagicMock()
    context.astr_context = MagicMock()
    context.conversation_ledger = MagicMock()

    front_desk = FrontDesk(config, context)
    front_desk.chat_sources = None
    front_desk._normalize_sender_name = lambda *args: "User"
    front_desk._get_event_message_id = MagicMock(return_value="message-1")
    front_desk._build_cached_image_item = AsyncMock(
        return_value={
            "type": "image_url",
            "image_url": {"url": "cache://quoted-image"},
        }
    )
    front_desk._build_cached_file_text_item = AsyncMock(
        return_value={"type": "text", "text": "[文件: quoted.md]\nquoted body"}
    )

    quoted_image = Image()
    quoted_file = _make_file("quoted.md")
    event = _QuotedMediaEvent(
        [
            Reply(
                sender_id="user-2",
                sender_nickname="Other",
                message_str="quoted text",
                chain=[quoted_image, quoted_file],
            )
        ]
    )

    await front_desk.cache_message(event.unified_msg_origin, event)

    front_desk._build_cached_image_item.assert_awaited_once_with(
        event.unified_msg_origin,
        quoted_image,
    )
    front_desk._build_cached_file_text_item.assert_awaited_once_with(
        event.unified_msg_origin,
        quoted_file,
    )
    stored = context.conversation_ledger.add_message.call_args.args[1]
    assert any(
        item.get("type") == "image_url"
        for item in stored["content"]
        if isinstance(item, dict)
    )
    assert any(
        "quoted body" in str(item.get("text", ""))
        for item in stored["content"]
        if isinstance(item, dict)
    )


@pytest.mark.asyncio
async def test_empty_result_chain_with_real_stream_delivery_closes_state():
    from astrbot_plugin_angel_heart.main import AngelHeartPlugin

    plugin = object.__new__(AngelHeartPlugin)

    class _FakeRuntimeTasks:
        async def run(self, event, fn):
            del event
            return await fn()

    plugin._runtime_tasks = _FakeRuntimeTasks()
    plugin._finish_secretary_dispatch = AsyncMock(return_value=True)
    plugin._extract_sent_message_content = MagicMock(return_value="streamed reply")
    plugin.front_desk = SimpleNamespace(
        _get_event_message_id=MagicMock(return_value="message-1")
    )
    plugin.angel_context = SimpleNamespace(
        debounce_manager=SimpleNamespace(
            get_leave_reply_trigger=MagicMock(return_value=None)
        ),
        handle_message_sent=AsyncMock(),
        work_ledger=SimpleNamespace(complete_work=MagicMock()),
    )

    event = MagicMock()
    event.unified_msg_origin = "whatsapp:GroupMessage:1203631"
    event._has_send_oper = True
    event.get_result.return_value = SimpleNamespace(chain=[])
    event.get_extra.return_value = "work-1"

    await plugin.handle_message_sent(event)

    plugin.angel_context.handle_message_sent.assert_awaited_once_with(
        event.unified_msg_origin,
        keep_not_present=False,
    )
    plugin._finish_secretary_dispatch.assert_awaited_once()
    plugin.angel_context.work_ledger.complete_work.assert_called_once_with(
        event.unified_msg_origin,
        "work-1",
        status="done",
        result_summary="streamed reply",
    )
