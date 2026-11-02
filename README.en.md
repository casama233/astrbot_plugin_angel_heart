# AngelHeart — Intelligent Group and Private Chat Interaction

[简体中文](README.md) · [繁體中文](README.zh-TW.md) · **English**

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)

Documentation for plugin version **0.9.3**.

AngelHeart is an [AstrBot](https://github.com/Soulter/AstrBot) plugin coordinating **front desk, secretary and assistant** roles and **out-of-conversation / observing** states, to decide when to reply and when not to interrupt group or private chats.

## Three-role model

| Role | Responsibility | Model |
| --- | --- | --- |
| Front desk | Record messages, maintain the ledger, dispatch events | No LLM |
| Secretary | Check conversation rhythm and decide whether to engage | Lightweight model |
| Assistant | Generate actual responses | Main LLM |

Flow: **message → front desk logging → secretary inspection → speak/no-speak decision → assistant response**. If the secretary declines, the assistant is not activated.

## Two group participation states

- **Out of conversation (`NOT_PRESENT`)**: log messages but do not proactively join. An @mention or configured name summons the bot. Optional one-off responses to repetition or intense activity do not make it persistently present.
- **Observing (`OBSERVATION`)**: after being addressed, remain in the conversation. The secretary considers speaking once the group becomes quiet. Expiry returns the bot to out-of-conversation on the next message.

**Inspection / debouncing:** addressed messages wait for clarification; ordinary checks happen after a lull. New messages replace older pending boundaries. Only one secretary decision runs per conversation. A direct mention can upgrade an existing ordinary check without creating a duplicate. Rest gates prevent immediate repeat interruptions; mentions still respect busy/active rest limits.

## Assistant energy and reply pacing

Energy is managed per group and recovers over elapsed time before ordinary inspections. Longer messages cost more energy.

| Parameter | Default |
| --- | --- |
| Initial/max energy | `100` |
| Lower bound | `-100` |
| Energy regenerated each second | `0.6` |
| Base reply cost | `14` |
| Cost per effective character | `0.12` |

Cost: `14 + effective_characters × 0.12`. Group energy is in memory and resets when the plugin restarts. Ordinary checks require sufficient energy; **direct mentions and one-off out-of-conversation responses bypass the energy threshold**, but not other busy/rest protections.

## Context and optional companion

The plugin manages group/private context with configurable triggers, waits, cooldowns and model routing. It can be paired with [Angel Memory](https://github.com/kawayiYokami/astrbot_plugin_angel_memory) for long-term memories, short notes, reranking and knowledge management. Angel Memory is an optional companion, **not a prerequisite for AngelHeart's core conversation behavior**.

## Installation

Requires an installed [AstrBot](https://github.com/Soulter/AstrBot) environment, **Python 3.10+** and at least one working AI model provider. Install “天使之心” from AstrBot's plugin marketplace, or place the source in AstrBot's plugin directory and enable it in WebUI.

## Contributions, license and upstream

Issues and pull requests are welcome. Licensed [GNU AGPL-3.0](LICENSE). Forked from [kawayiYokami/astrbot_plugin_angel_heart](https://github.com/kawayiYokami/astrbot_plugin_angel_heart). Preserve upstream AGPL notices and copyright attribution. Fork modifications do not claim upstream code as newly authored or extend rights to third-party assets and dependencies. Thanks to the AstrBot team and contributors.
