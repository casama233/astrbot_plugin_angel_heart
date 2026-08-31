"""Cary-maintained compatibility patches for :mod:`roles.front_desk`.

The 2.2.3 custom baseline already formats quoted-message text, but the media
cache still walks only the outer message chain. Images and text files nested
inside ``Reply.chain`` therefore disappear before the multimodal request is
built. This module adds a cycle-safe iterator and wraps ``cache_message``
without rewriting the large upstream-derived FrontDesk implementation.
"""

from __future__ import annotations

from functools import wraps
from typing import Any, Iterable, Iterator, Sequence

from astrbot.core.message.components import File, Image, Reply

from .front_desk import FrontDesk

_PATCH_MARKER = "_cary_quoted_media_patch_installed"
_ORIGINAL_CACHE_ATTR = "_cary_original_cache_message"


class _MessageEventProxy:
    """Delegate an AstrBot event while supplying an expanded message chain."""

    __slots__ = ("_event", "_messages")

    def __init__(self, event: Any, messages: Sequence[Any]) -> None:
        self._event = event
        self._messages = tuple(messages)

    def get_messages(self) -> list[Any]:
        return list(self._messages)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._event, name)


def iter_media_components(components: Iterable[Any] | None) -> Iterator[Any]:
    """Yield direct and quoted images/files once, preserving message order.

    ``Reply.chain`` may contain nested or cyclic ``Reply`` objects on some
    adapters. Reply containers and media objects are therefore tracked by
    identity. Quoted text is deliberately not yielded; FrontDesk's existing
    reply-context formatter remains the sole owner of quoted text semantics.
    """

    pending = list(components or [])
    seen_replies: set[int] = set()
    seen_media: set[int] = set()

    while pending:
        component = pending.pop(0)
        if isinstance(component, (Image, File)):
            media_id = id(component)
            if media_id not in seen_media:
                seen_media.add(media_id)
                yield component
            continue

        if not isinstance(component, Reply):
            continue

        reply_id = id(component)
        if reply_id in seen_replies:
            continue
        seen_replies.add(reply_id)

        quoted_chain = getattr(component, "chain", None)
        if quoted_chain:
            pending[0:0] = list(quoted_chain)


def _quoted_only_media(components: Sequence[Any]) -> list[Any]:
    direct_ids = {
        id(component)
        for component in components
        if isinstance(component, (Image, File))
    }
    return [
        component
        for component in iter_media_components(components)
        if id(component) not in direct_ids
    ]


def install_quoted_media_cache_patch(front_desk_cls: type = FrontDesk) -> None:
    """Install the quoted-media cache wrapper exactly once."""

    if bool(getattr(front_desk_cls, _PATCH_MARKER, False)):
        return

    original_cache_message = getattr(front_desk_cls, "cache_message", None)
    if not callable(original_cache_message):
        raise RuntimeError("FrontDesk.cache_message 不可调用，拒绝静默安装引用附件补丁")

    @wraps(original_cache_message)
    async def cache_message_with_quoted_media(
        self: Any,
        chat_id: str,
        event: Any,
    ) -> Any:
        try:
            outer_messages = list(event.get_messages() or [])
            quoted_media = _quoted_only_media(outer_messages)
        except Exception:
            return await original_cache_message(self, chat_id, event)

        if not quoted_media:
            return await original_cache_message(self, chat_id, event)

        expanded_event = _MessageEventProxy(
            event,
            [*outer_messages, *quoted_media],
        )
        return await original_cache_message(self, chat_id, expanded_event)

    setattr(front_desk_cls, _ORIGINAL_CACHE_ATTR, original_cache_message)
    setattr(front_desk_cls, "_iter_media_components", staticmethod(iter_media_components))
    setattr(front_desk_cls, "cache_message", cache_message_with_quoted_media)
    setattr(front_desk_cls, _PATCH_MARKER, True)


__all__ = ["install_quoted_media_cache_patch", "iter_media_components"]
