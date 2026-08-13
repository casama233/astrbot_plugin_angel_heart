from __future__ import annotations

import asyncio
import sys
import threading
from pathlib import Path
from types import SimpleNamespace


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT.parent))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from astrbot_plugin_angel_heart.core.utils.context_utils import format_final_prompt
from astrbot_plugin_angel_heart.core.conversation_ledger import ConversationLedger
from astrbot_plugin_angel_heart.roles.front_desk import FrontDesk
from astrbot.core.message.components import Image, Plain, Reply


_DEFAULT_MODALITIES = object()
_MISSING_MODALITIES = object()


def _front_desk(
    *,
    supports_image: bool,
    image_caption_provider_id: str = "",
    modalities=_DEFAULT_MODALITIES,
) -> FrontDesk:
    front_desk = object.__new__(FrontDesk)
    front_desk._config_manager = SimpleNamespace(
        image_caption_provider_id=image_caption_provider_id
    )
    if modalities is _DEFAULT_MODALITIES:
        modalities = ["text", "image"] if supports_image else ["text"]
    provider_config = {}
    if modalities is not _MISSING_MODALITIES:
        provider_config["modalities"] = modalities
    provider = SimpleNamespace(provider_config=provider_config)
    front_desk.astr_context = SimpleNamespace(
        get_using_provider=lambda chat_id: provider
    )
    front_desk.context = SimpleNamespace(astr_context=front_desk.astr_context)
    return front_desk


def _request(image_urls: list[str]):
    return SimpleNamespace(
        contexts=[{"role": "user", "content": "old"}],
        prompt="old prompt",
        image_urls=image_urls,
        extra_user_content_parts=[],
        system_prompt="",
    )


def _image(url: str) -> dict:
    return {"type": "image_url", "image_url": {"url": url}}


class _CaptionLedger:
    def __init__(self):
        self.generated = 0
        self.checked = 0

    async def generate_captions_for_chat(self, **kwargs):
        self.generated += 1
        return 1

    async def process_image_captions_if_needed(self, **kwargs):
        self.checked += 1
        return 0


class _EarlyCaptionLedger:
    TEMPORARY_IMAGE_CAPTION = "图片转述服务暂时不可用"
    BROKEN_IMAGE_CAPTION = "图片无法打开"
    EXPIRED_IMAGE_CAPTION = "图片缓存已经丢失"

    def __init__(self, event_id: str, caption: str, temporary: bool = False):
        self.event_id = event_id
        self.caption = caption
        self.temporary = temporary
        self.generated = 0

    async def generate_captions_for_chat(self, **kwargs):
        self.generated += 1
        return 1

    def get_all_messages(self, chat_id):
        return [
            {
                "role": "user",
                "source_event_id": self.event_id,
                "image_caption": self.caption,
                "_image_caption_temporary": self.temporary,
                "content": [_image("data:image/png;base64,KEEP_IN_LEDGER")],
            }
        ]


def test_angelheart_captions_before_core_provider_selection():
    event_id = "ah-current"
    ledger = _EarlyCaptionLedger(event_id, "表格中显示 DeepSeek 得分最高")
    front_desk = object.__new__(FrontDesk)
    front_desk._config_manager = SimpleNamespace(
        image_caption_provider_id="vision-provider"
    )
    front_desk.astr_context = SimpleNamespace()
    front_desk.context = SimpleNamespace(conversation_ledger=ledger)

    image = Image()
    text = Plain("请分析")
    message_obj = SimpleNamespace(message=[text, image], message_str="请分析")
    extras = {}
    event = SimpleNamespace(
        unified_msg_origin="default:FriendMessage:1",
        angelheart_event_id=event_id,
        message_obj=message_obj,
        message_str="请分析",
        get_messages=lambda: message_obj.message,
        set_extra=lambda key, value: extras.__setitem__(key, value),
        get_extra=lambda key, default=None: extras.get(key, default),
    )

    changed = asyncio.run(front_desk.prepare_current_image_for_text_model(event))

    assert changed is True
    assert ledger.generated == 1
    assert all(not isinstance(component, Image) for component in message_obj.message)
    assert message_obj.message[0] is text
    assert "表格中显示 DeepSeek 得分最高" in message_obj.message[-1].text
    assert "表格中显示 DeepSeek 得分最高" in event.message_str
    assert message_obj.message_str == event.message_str
    assert extras["angelheart_image_caption_preprocessed"] is True

    assert front_desk.restore_original_image_event(event) is True
    assert message_obj.message == [text, image]
    assert event.message_str == "请分析"
    assert message_obj.message_str == "请分析"


def test_temporary_caption_failure_stays_with_text_model_and_reports_failure():
    event_id = "ah-failed"
    ledger = _EarlyCaptionLedger(
        event_id,
        _EarlyCaptionLedger.TEMPORARY_IMAGE_CAPTION,
        temporary=True,
    )
    front_desk = object.__new__(FrontDesk)
    front_desk._config_manager = SimpleNamespace(
        image_caption_provider_id="vision-provider"
    )
    front_desk.astr_context = SimpleNamespace()
    front_desk.context = SimpleNamespace(conversation_ledger=ledger)

    image = Image()
    message_obj = SimpleNamespace(message=[image], message_str="")
    extras = {}
    event = SimpleNamespace(
        unified_msg_origin="default:FriendMessage:2",
        angelheart_event_id=event_id,
        message_obj=message_obj,
        message_str="",
        get_messages=lambda: message_obj.message,
        set_extra=lambda key, value: extras.__setitem__(key, value),
        get_extra=lambda key, default=None: extras.get(key, default),
    )

    changed = asyncio.run(front_desk.prepare_current_image_for_text_model(event))

    assert changed is True
    assert all(not isinstance(component, Image) for component in message_obj.message)
    assert _EarlyCaptionLedger.TEMPORARY_IMAGE_CAPTION in event.message_str
    assert "不要猜测图片内容" not in event.message_str
    assert isinstance(extras["angelheart_original_image_event"], dict)

    assert front_desk.restore_original_image_event(event) is True
    assert message_obj.message == [image]
    assert event.message_str == ""


def test_quoted_image_is_captioned_and_removed_from_temporary_request():
    event_id = "ah-quoted"
    ledger = _EarlyCaptionLedger(event_id, "引用图片中是一张天气预报")
    front_desk = object.__new__(FrontDesk)
    front_desk._config_manager = SimpleNamespace(
        image_caption_provider_id="vision-provider"
    )
    front_desk.astr_context = SimpleNamespace()
    front_desk.context = SimpleNamespace(conversation_ledger=ledger)

    image = Image()
    reply = Reply(chain=[Plain("引用正文"), image])
    question = Plain("这张图是什么？")
    message_obj = SimpleNamespace(message=[reply, question], message_str="")
    extras = {}
    event = SimpleNamespace(
        unified_msg_origin="whatsapp:FriendMessage:1",
        angelheart_event_id=event_id,
        message_obj=message_obj,
        message_str="这张图是什么？",
        get_messages=lambda: message_obj.message,
        set_extra=lambda key, value: extras.__setitem__(key, value),
        get_extra=lambda key, default=None: extras.get(key, default),
    )

    changed = asyncio.run(front_desk.prepare_current_image_for_text_model(event))

    assert changed is True
    assert ledger.generated == 1
    sanitized_reply = message_obj.message[0]
    assert isinstance(sanitized_reply, Reply)
    assert all(not isinstance(component, Image) for component in sanitized_reply.chain)
    assert "引用图片中是一张天气预报" in event.message_str

    assert front_desk.restore_original_image_event(event) is True
    assert message_obj.message == [reply, question]
    assert reply.chain[1] is image


def test_multiple_images_are_all_captioned_before_text_only_routing():
    ledger = object.__new__(ConversationLedger)
    ledger._lock = threading.RLock()
    ledger._caption_locks = {}
    ledger.config_manager = SimpleNamespace(image_caption_prompt="完整描述图片")
    ledger._ledgers = {
        "chat": {
            "messages": [
                {
                    "role": "user",
                    "timestamp": 1.0,
                    "content": [
                        _image("file:///tmp/first.png"),
                        _image("file:///tmp/second.png"),
                    ],
                }
            ],
            "last_processed_timestamp": 0.0,
        }
    }

    async def caption_one(_chat_id, sources, *_args):
        return "第一张内容" if "first.png" in sources[0] else "第二张内容"

    ledger._caption_one_image = caption_one
    astr_context = SimpleNamespace(get_provider_by_id=lambda _provider_id: object())

    count = asyncio.run(
        ledger.generate_captions_for_chat("chat", "vision-provider", astr_context)
    )

    message = ledger._ledgers["chat"]["messages"][0]
    assert count == 2
    assert message["image_caption"] == (
        "[图片1]\n第一张内容\n\n[图片2]\n第二张内容"
    )
    assert len(message["content"]) == 2


def test_image_caption_cache_survives_ledger_restart(tmp_path):
    config = SimpleNamespace()
    first = ConversationLedger(config, tmp_path)
    with first._db_lock:
        first.db_cursor.execute(
            "INSERT INTO image_content_cache (dhash, caption, timestamp) "
            "VALUES (?, ?, ?)",
            ("abc123", "缓存的转述", 1.0),
        )
        first.db_conn.commit()
    first.db_conn.close()

    second = ConversationLedger(config, tmp_path)
    with second._db_lock:
        row = second.db_cursor.execute(
            "SELECT caption FROM image_content_cache WHERE dhash = ?",
            ("abc123",),
        ).fetchone()
    second.db_conn.close()

    assert row == ("缓存的转述",)


def test_preserves_current_image_urls_when_provider_supports_images():
    front_desk = _front_desk(supports_image=True, image_caption_provider_id="caption")
    req = _request(["file:///tmp/current-a.png", "file:///tmp/current-b.png"])

    front_desk._update_request(
        req,
        contexts=[],
        final_prompt="看看这两张 [图片1] [图片2]",
        alias="AngelHeart",
        preserve_current_image_urls=front_desk._should_preserve_current_image_urls("chat"),
    )

    assert req.prompt == "看看这两张 [图片1] [图片2]"
    assert req.image_urls == [
        "file:///tmp/current-a.png",
        "file:///tmp/current-b.png",
    ]


def test_keeps_current_image_urls_for_core_provider_sanitization():
    front_desk = _front_desk(supports_image=False, image_caption_provider_id="caption")
    req = _request(["file:///tmp/current.png"])

    front_desk._update_request(
        req,
        contexts=[],
        final_prompt="纯文本模型只看转述 [图片1]",
        alias="AngelHeart",
        preserve_current_image_urls=front_desk._should_preserve_current_image_urls("chat"),
    )

    assert req.image_urls == ["file:///tmp/current.png"]


def test_filter_images_defers_to_core_when_default_provider_is_text_only():
    front_desk = _front_desk(supports_image=False)
    contexts = [{"role": "user", "content": [_image("file:///tmp/routed.png")]}]

    filtered = front_desk.filter_images_for_provider("chat", contexts)

    assert filtered == contexts


def test_caption_fallback_is_generated_even_when_current_provider_supports_images():
    front_desk = _front_desk(supports_image=True, image_caption_provider_id="caption")
    ledger = _CaptionLedger()
    front_desk.context = SimpleNamespace(conversation_ledger=ledger)

    caption_count = asyncio.run(
        front_desk._ensure_image_captions_for_request(
            "chat",
            force_caption=True,
        )
    )

    assert caption_count == 1
    assert ledger.generated == 1
    assert ledger.checked == 0


def test_captioned_ledger_message_keeps_image_for_final_provider():
    ledger = object.__new__(ConversationLedger)
    ledger._lock = threading.RLock()
    ledger._ledgers = {
        "chat": {
            "messages": [
                {
                    "role": "user",
                    "timestamp": 1.0,
                    "content": [_image("file:///tmp/keep.png")],
                }
            ],
            "last_processed_timestamp": 0.0,
        }
    }

    assert ledger.add_caption_to_message("chat", 1.0, "图片文字兜底") is True
    message = ledger._ledgers["chat"]["messages"][0]
    assert message["image_caption"] == "图片文字兜底"
    assert message["content"][0]["type"] == "image_url"


def test_temporary_caption_failure_keeps_image_and_enters_cooldown():
    ledger = object.__new__(ConversationLedger)
    ledger._lock = threading.RLock()
    ledger.config_manager = SimpleNamespace(image_caption_retry_cooldown=300)
    message = {
        "role": "user",
        "timestamp": 1.0,
        "content": [_image("file:///tmp/keep-on-error.png")],
    }
    ledger._ledgers = {
        "chat": {"messages": [message], "last_processed_timestamp": 0.0}
    }
    ledger.get_context_snapshot = lambda chat_id: ([], [message], 0)

    assert ledger._mark_temporary_caption_failure("chat", 1.0) is True
    assert message["image_caption"] == ledger.TEMPORARY_IMAGE_CAPTION
    assert message["_image_caption_temporary"] is True
    assert message["content"][0]["type"] == "image_url"
    assert ledger.should_process_images("chat") is False


def test_caption_request_reloads_provider_after_astrbot_hot_reload():
    class StaleProvider:
        async def text_chat(self, **kwargs):
            raise AttributeError("'NoneType' object has no attribute 'models'")

    class FreshProvider:
        def __init__(self):
            self.kwargs = None

        async def text_chat(self, **kwargs):
            self.kwargs = kwargs
            return SimpleNamespace(completion_text="恢复后的图片转述")

    fresh = FreshProvider()
    providers = iter([StaleProvider(), fresh])
    astr_context = SimpleNamespace(get_provider_by_id=lambda _provider_id: next(providers))
    ledger = object.__new__(ConversationLedger)
    ledger.config_manager = SimpleNamespace(image_caption_timeout=5)

    result = asyncio.run(
        ledger._request_image_caption(
            "caption-provider", astr_context, "描述图片", "data:image/png;base64,eA=="
        )
    )

    assert result.completion_text == "恢复后的图片转述"
    assert fresh.kwargs["request_max_retries"] == 1


def test_unconfigured_provider_modalities_are_treated_as_image_capable():
    for modalities in (None, [], _MISSING_MODALITIES):
        front_desk = _front_desk(
            supports_image=False,
            image_caption_provider_id="caption",
            modalities=modalities,
        )

        assert front_desk._should_preserve_current_image_urls("chat") is True


def test_filter_images_keeps_images_when_modalities_are_unconfigured():
    front_desk = _front_desk(supports_image=False, modalities=[])
    contexts = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "看图"},
                _image("file:///tmp/a.png"),
            ],
        }
    ]

    filtered = front_desk.filter_images_for_provider("chat", contexts)

    assert filtered[0]["content"][1]["type"] == "image_url"


def test_ledger_captions_images_when_provider_modalities_are_missing():
    ledger = object.__new__(ConversationLedger)
    ledger.get_context_snapshot = lambda chat_id: (
        [],
        [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "看图"},
                    _image("file:///tmp/a.png"),
                ],
            }
        ],
        0,
    )
    astr_context = SimpleNamespace(
        get_using_provider=lambda chat_id: SimpleNamespace(provider_config={})
    )

    assert ledger.should_process_images("chat", astr_context) is True


def test_preserves_current_image_urls_when_provider_supports_images_even_if_captioning_is_configured():
    front_desk = _front_desk(supports_image=True, image_caption_provider_id="caption")
    req = _request(["file:///tmp/current.png"])

    front_desk._update_request(
        req,
        contexts=[],
        final_prompt="多模态模型直接看图 [图片1]",
        alias="AngelHeart",
        preserve_current_image_urls=front_desk._should_preserve_current_image_urls("chat"),
    )

    assert req.image_urls == ["file:///tmp/current.png"]


def test_final_prompt_numbers_multiple_images_across_aggregated_messages():
    recent_dialogue = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "帮我看看 [图片]"},
                _image("data:image/png;base64,IMAGE_A"),
            ],
            "sender_name": "小明",
            "sender_id": "123456",
            "chat_id": "aiocqhttp:GroupMessage:10000",
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "还有这两张"},
                _image("data:image/png;base64,IMAGE_B"),
                _image("data:image/png;base64,IMAGE_C"),
            ],
            "sender_name": "小红",
            "sender_id": "456789",
            "chat_id": "aiocqhttp:GroupMessage:10000",
        },
    ]

    prompt = format_final_prompt(recent_dialogue, decision=None, alias="AngelHeart")

    assert "[群友: 小明 (ID: 123456)]: 帮我看看 [图片1]" in prompt
    assert "[群友: 小红 (ID: 456789)]: 还有这两张 [图片2] [图片3]" in prompt
    assert "base64" not in prompt
    assert "IMAGE_A" not in prompt


def test_appends_non_current_aggregated_images_as_extra_content_parts():
    front_desk = _front_desk(supports_image=True)
    req = _request(["file:///tmp/current.png"])
    recent_dialogue = [
        {
            "source_event_id": "old-event",
            "content": [
                {"type": "text", "text": "前一条"},
                _image("data:image/png;base64,OLD_IMAGE"),
            ],
        },
        {
            "source_event_id": "current-event",
            "content": [
                {"type": "text", "text": "当前条"},
                _image("data:image/png;base64,CURRENT_LEDGER_IMAGE"),
            ],
        },
    ]

    extra_urls = front_desk._collect_non_current_image_urls(
        recent_dialogue, "current-event"
    )
    front_desk._update_request(
        req,
        contexts=[],
        final_prompt="前一条 [图片1]\n当前条 [图片2]",
        alias="AngelHeart",
        preserve_current_image_urls=True,
        extra_image_urls=extra_urls,
    )

    assert req.image_urls == ["file:///tmp/current.png"]
    assert len(req.extra_user_content_parts) == 1
    assert req.extra_user_content_parts[0].image_url.url == "data:image/png;base64,OLD_IMAGE"
