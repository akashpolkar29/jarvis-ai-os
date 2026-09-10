"""Unit tests for jarvis.domain.events: the real event model + EventBus (WP-111)."""

from __future__ import annotations

import logging

import pytest

from jarvis.domain.events import EventBus, TaskCreated, TaskStatusChanged


def _make_created(task_id: str = "mem:1") -> TaskCreated:
    return TaskCreated(
        event_id="evt:1", task_id=task_id, goal="do a thing", status="created", timestamp="t1"
    )


def _make_status_changed(task_id: str = "mem:1") -> TaskStatusChanged:
    return TaskStatusChanged(
        event_id="evt:2",
        task_id=task_id,
        goal="do a thing",
        previous_status="created",
        new_status="running",
        reason=None,
        timestamp="t2",
    )


# ---------------------------------------------------------------------------
# Event model -- valid construction, required fields
# ---------------------------------------------------------------------------


def test_task_created_carries_every_required_field() -> None:
    event = _make_created()

    assert event.event_id == "evt:1"
    assert event.task_id == "mem:1"
    assert event.goal == "do a thing"
    assert event.status == "created"
    assert event.timestamp == "t1"


def test_task_status_changed_carries_every_required_field() -> None:
    event = _make_status_changed()

    assert event.previous_status == "created"
    assert event.new_status == "running"
    assert event.reason is None


def test_task_status_changed_previous_status_may_be_none() -> None:
    """A real, honest "we don't know" -- not a guessed value -- is a valid, representable state."""
    event = TaskStatusChanged(
        event_id="evt:3",
        task_id="mem:1",
        goal="do a thing",
        previous_status=None,
        new_status="failed",
        reason="PlanningError: boom",
        timestamp="t3",
    )

    assert event.previous_status is None
    assert event.reason == "PlanningError: boom"


def test_events_are_frozen_not_mutable() -> None:
    event = _make_created()

    with pytest.raises(AttributeError):
        event.status = "running"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# EventBus -- subscribe / publish / unsubscribe
# ---------------------------------------------------------------------------


def test_publish_with_no_subscribers_is_a_harmless_no_op() -> None:
    bus = EventBus()

    bus.publish(_make_created())  # must not raise


def test_subscribe_then_publish_calls_the_handler_with_the_real_event() -> None:
    bus = EventBus()
    received: list[object] = []
    bus.subscribe(TaskCreated, received.append)

    event = _make_created()
    bus.publish(event)

    assert received == [event]


def test_publish_only_notifies_subscribers_of_the_exact_matching_type() -> None:
    """A TaskCreated subscriber is never called for a TaskStatusChanged event, and vice versa."""
    bus = EventBus()
    created_received: list[object] = []
    changed_received: list[object] = []
    bus.subscribe(TaskCreated, created_received.append)
    bus.subscribe(TaskStatusChanged, changed_received.append)

    bus.publish(_make_created())

    assert len(created_received) == 1
    assert changed_received == []


def test_multiple_subscribers_to_the_same_event_type_are_all_called() -> None:
    bus = EventBus()
    first: list[object] = []
    second: list[object] = []
    bus.subscribe(TaskCreated, first.append)
    bus.subscribe(TaskCreated, second.append)

    event = _make_created()
    bus.publish(event)

    assert first == [event]
    assert second == [event]


def test_subscribers_are_called_in_real_subscription_order() -> None:
    """Deterministic delivery order -- subscribe() order, not reversed or random."""
    bus = EventBus()
    call_order: list[str] = []
    bus.subscribe(TaskCreated, lambda _e: call_order.append("first"))
    bus.subscribe(TaskCreated, lambda _e: call_order.append("second"))
    bus.subscribe(TaskCreated, lambda _e: call_order.append("third"))

    bus.publish(_make_created())

    assert call_order == ["first", "second", "third"]


def test_unsubscribe_with_the_exact_same_handler_object_stops_delivery() -> None:
    bus = EventBus()
    received: list[object] = []

    def handler(event: object) -> None:
        received.append(event)

    bus.subscribe(TaskCreated, handler)
    bus.unsubscribe(TaskCreated, handler)
    bus.publish(_make_created())

    assert received == []


def test_unsubscribe_of_an_unregistered_handler_is_a_harmless_no_op() -> None:
    bus = EventBus()

    def handler(event: object) -> None:
        del event

    bus.unsubscribe(TaskCreated, handler)  # must not raise, even though never subscribed


def test_unsubscribe_of_an_unknown_event_type_is_a_harmless_no_op() -> None:
    bus = EventBus()

    def handler(event: object) -> None:
        del event

    bus.unsubscribe(TaskStatusChanged, handler)  # never subscribed to this type at all


# ---------------------------------------------------------------------------
# EventBus -- subscriber failure behavior (Step 8)
# ---------------------------------------------------------------------------


def test_a_raising_subscriber_does_not_prevent_other_subscribers_from_being_notified() -> None:
    bus = EventBus()
    received: list[object] = []

    def failing_handler(_event: object) -> None:
        raise RuntimeError("a real, deliberate subscriber bug")

    bus.subscribe(TaskCreated, failing_handler)
    bus.subscribe(TaskCreated, received.append)

    bus.publish(_make_created())  # must not raise, despite the first subscriber's own exception

    assert len(received) == 1


def test_a_raising_subscriber_does_not_propagate_to_publish_callers(
    caplog: pytest.LogCaptureFixture,
) -> None:
    bus = EventBus()

    def failing_handler(_event: object) -> None:
        raise ValueError("boom")

    bus.subscribe(TaskCreated, failing_handler)

    with caplog.at_level(logging.ERROR, logger="jarvis.domain.events"):
        bus.publish(_make_created())  # must not raise

    assert any(record.levelno == logging.ERROR for record in caplog.records)
    assert any("boom" in record.getMessage() or record.exc_info for record in caplog.records)


def test_a_subscriber_failure_is_never_silently_swallowed() -> None:
    """The real failure is logged (visible), not caught-and-discarded with no trace at all."""
    bus = EventBus()

    def failing_handler(_event: object) -> None:
        raise RuntimeError("must be visible in logs")

    bus.subscribe(TaskCreated, failing_handler)

    with pytest.MonkeyPatch().context() as mp:
        logged: list[str] = []
        mp.setattr(
            "jarvis.domain.events._logger.exception",
            lambda msg, *args, **_kwargs: logged.append(msg % args if args else msg),
        )
        bus.publish(_make_created())

    assert len(logged) == 1
    assert "subscriber" in logged[0]


# ---------------------------------------------------------------------------
# EventBus -- handler mutating subscriptions mid-delivery
# ---------------------------------------------------------------------------


def test_a_handler_unsubscribing_itself_mid_delivery_does_not_skip_other_handlers() -> None:
    bus = EventBus()
    received: list[str] = []

    def self_unsubscribing_handler(_event: object) -> None:
        received.append("first")
        bus.unsubscribe(TaskCreated, self_unsubscribing_handler)

    def second_handler(_event: object) -> None:
        received.append("second")

    bus.subscribe(TaskCreated, self_unsubscribing_handler)
    bus.subscribe(TaskCreated, second_handler)

    bus.publish(_make_created())

    assert received == ["first", "second"]

    # And the unsubscribe genuinely took effect for the *next* publish.
    received.clear()
    bus.publish(_make_created())
    assert received == ["second"]
