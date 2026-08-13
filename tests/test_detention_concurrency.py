from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from astrbot_plugin_angel_heart.roles.front_desk import FrontDesk


def _front_desk(acquire_results) -> FrontDesk:
    front_desk = object.__new__(FrontDesk)
    front_desk.secretary = object()
    front_desk.context = SimpleNamespace(
        acquire_chat_processing=AsyncMock(side_effect=acquire_results)
    )
    front_desk._call_secretary_and_execute = AsyncMock()
    front_desk._enter_detention_queue = AsyncMock()
    return front_desk


def _event(origin: str, *, explicit_wake: bool = False):
    return SimpleNamespace(
        unified_msg_origin=origin,
        is_at_or_wake_command=explicit_wake,
        stop_event=MagicMock(),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "origin",
    ["default:GroupMessage:123", "whatsapp:GroupMessage:123"],
)
async def test_cooldown_boundary_loser_is_already_covered_by_winner(origin):
    front_desk = _front_desk(
        [(False, "COOLDOWN", 0.0), (False, "LOCKED", 0.0)]
    )
    event = _event(origin)

    with patch("astrbot_plugin_angel_heart.roles.front_desk.asyncio.sleep", new=AsyncMock()):
        await front_desk._notify_secretary(event)

    front_desk._enter_detention_queue.assert_not_awaited()
    front_desk._call_secretary_and_execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_explicit_wake_still_waits_after_losing_cooldown_boundary():
    front_desk = _front_desk(
        [(False, "COOLDOWN", 0.0), (False, "LOCKED", 0.0)]
    )
    event = _event("whatsapp:GroupMessage:123", explicit_wake=True)

    with patch("astrbot_plugin_angel_heart.roles.front_desk.asyncio.sleep", new=AsyncMock()):
        await front_desk._notify_secretary(event)

    front_desk._enter_detention_queue.assert_awaited_once_with(
        event, "门锁占用(LOCKED)"
    )


@pytest.mark.asyncio
async def test_initial_locked_event_keeps_existing_detention_semantics():
    front_desk = _front_desk([(False, "LOCKED", 0.0)])
    event = _event("default:GroupMessage:123")

    with patch("astrbot_plugin_angel_heart.roles.front_desk.asyncio.sleep", new=AsyncMock()) as sleep:
        await front_desk._notify_secretary(event)

    sleep.assert_not_awaited()
    front_desk._enter_detention_queue.assert_awaited_once_with(
        event, "门锁占用(LOCKED)"
    )


@pytest.mark.asyncio
async def test_killed_ticket_clears_result_before_stopping_event():
    front_desk = object.__new__(FrontDesk)
    ticket = asyncio.get_running_loop().create_future()
    ticket.set_result("KILL")
    front_desk.context = SimpleNamespace(
        hold_and_start_observation=AsyncMock(return_value=ticket)
    )

    state = {"result": SimpleNamespace(chain=["stale"])}
    event = SimpleNamespace(
        unified_msg_origin="whatsapp:GroupMessage:123",
        get_result=lambda: state["result"],
        clear_result=MagicMock(side_effect=lambda: state.update(result=None)),
        stop_event=MagicMock(),
    )

    await front_desk._enter_detention_queue(event, "test")

    event.clear_result.assert_called_once_with()
    assert event.get_result() is None
    event.stop_event.assert_called_once_with()
