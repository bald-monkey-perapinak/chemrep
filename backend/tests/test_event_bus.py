"""
Тесты EventBus (SSE pub/sub).

Запуск: cd backend && pytest tests/test_event_bus.py -v
"""

import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.events.bus import EventBus


class TestEventBus:
    def setup_method(self):
        self.bus = EventBus()

    # ── Subscribe / unsubscribe ────────────────────────────────────────────

    def test_subscribe_returns_queue(self):
        q = self.bus.subscribe("lesson-1")
        assert q is not None
        assert self.bus.subscriber_count("lesson-1") == 1

    def test_subscribe_multiple_clients(self):
        q1 = self.bus.subscribe("lesson-1")
        q2 = self.bus.subscribe("lesson-1")
        assert self.bus.subscriber_count("lesson-1") == 2

    def test_unsubscribe_removes_client(self):
        q = self.bus.subscribe("lesson-1")
        self.bus.unsubscribe("lesson-1", q)
        assert self.bus.subscriber_count("lesson-1") == 0

    def test_unsubscribe_removes_key_when_empty(self):
        q = self.bus.subscribe("lesson-1")
        self.bus.unsubscribe("lesson-1", q)
        assert "lesson-1" not in self.bus._subscribers

    def test_unsubscribe_nonexistent_no_crash(self):
        q = asyncio.Queue()
        self.bus.unsubscribe("nonexistent", q)  # не должно падать

    def test_unsubscribe_only_target_queue(self):
        q1 = self.bus.subscribe("lesson-1")
        q2 = self.bus.subscribe("lesson-1")
        self.bus.unsubscribe("lesson-1", q1)
        assert self.bus.subscriber_count("lesson-1") == 1

    # ── Publish ───────────────────────────────────────────────────────────

    def test_publish_puts_event_in_queue(self):
        q = self.bus.subscribe("lesson-1")
        self.bus.publish("lesson-1", "step_started", {"step": 1})
        assert not q.empty()
        event = q.get_nowait()
        assert event["kind"] == "step_started"
        assert event["data"]["step"] == 1
        assert "ts" in event

    def test_publish_to_multiple_subscribers(self):
        q1 = self.bus.subscribe("lesson-1")
        q2 = self.bus.subscribe("lesson-1")
        self.bus.publish("lesson-1", "bot_joined", {})
        assert not q1.empty()
        assert not q2.empty()

    def test_publish_no_subscribers_no_crash(self):
        self.bus.publish("lesson-nobody", "heartbeat")  # не должно падать

    def test_publish_different_lessons_isolated(self):
        q1 = self.bus.subscribe("lesson-1")
        q2 = self.bus.subscribe("lesson-2")
        self.bus.publish("lesson-1", "step_started", {"step": 1})
        assert not q1.empty()
        assert q2.empty()

    def test_publish_uuid_and_string_keys_equivalent(self):
        import uuid
        lid = uuid.uuid4()
        q = self.bus.subscribe(lid)
        self.bus.publish(str(lid), "bot_joined", {})
        assert not q.empty()

    def test_publish_event_has_required_fields(self):
        q = self.bus.subscribe("lesson-x")
        self.bus.publish("lesson-x", "session_ended", {"lesson_status": "completed"})
        event = q.get_nowait()
        assert "kind" in event
        assert "ts" in event
        assert "data" in event
        assert event["kind"] == "session_ended"

    def test_publish_empty_data_defaults_to_dict(self):
        q = self.bus.subscribe("lesson-x")
        self.bus.publish("lesson-x", "heartbeat")
        event = q.get_nowait()
        assert event["data"] == {}

    def test_subscriber_count_zero_for_unknown_lesson(self):
        assert self.bus.subscriber_count("nonexistent") == 0

    # ── Queue full handling ───────────────────────────────────────────────

    def test_full_queue_drops_event_without_crash(self):
        q = asyncio.Queue(maxsize=2)
        self.bus._subscribers["lesson-full"] = [q]
        # Заполняем очередь
        self.bus.publish("lesson-full", "e1", {})
        self.bus.publish("lesson-full", "e2", {})
        # Третье событие должно быть сброшено без исключения
        self.bus.publish("lesson-full", "e3", {})
        assert q.qsize() == 2

    # ── Async receive ─────────────────────────────────────────────────────

    def test_async_receive_event(self):
        async def _run():
            q = self.bus.subscribe("lesson-async")
            self.bus.publish("lesson-async", "question_asked", {"question": "Что такое алкан?"})
            event = await asyncio.wait_for(q.get(), timeout=1.0)
            return event

        event = asyncio.get_event_loop().run_until_complete(_run())
        assert event["kind"] == "question_asked"
        assert event["data"]["question"] == "Что такое алкан?"
