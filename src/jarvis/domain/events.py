"""A real, minimal, in-process task-lifecycle event model + EventBus (WP-111).

**Where this lives, and why**: the event dataclasses below
(:class:`TaskCreated`/:class:`TaskStatusChanged`) are pure, frozen,
stdlib-only data -- the identical shape this project's own
``domain/capability.py``/``domain/policy.py`` types already have.
:class:`EventBus` is a real, stateful, in-process registry (a
``dict``-backed subscriber list) with no real external I/O -- the
same shape :class:`~jarvis.domain.audit.AuditChain` already has (a
real, mutable, in-memory sequence with its own real behavior, living
in ``domain`` despite being stateful, because nothing about it is an
*external-system* boundary the way a port/adapter models one). There
is, deliberately, no ``EventBusPort``/adapter split: Step 4 of this
work package's own scope explicitly rules out any swappable backend
(no Redis/Kafka/RabbitMQ/database-backed event system) for this first,
real version -- introducing a port for a mechanism with exactly one
real implementation and no second one even contemplated would be
speculative abstraction ahead of any real need.

**Generation of `event_id`/`timestamp` is deliberately not this
module's own job.** `domain` may depend on the standard library only
(C2) -- it cannot import a real `IdPort`/`ClockPort` implementation.
Exactly like :class:`~jarvis.domain.audit.AuditChain.append`'s own
`written_at` parameter, the real caller (`jarvis.kernel.tasks`, which
already has a real, resolved `ClockPort`/`IdPort` in hand) computes
both values itself and passes them in already-formed; this module only
ever holds them.

**Events are derived from real state changes, never fabricated.**
Nothing in this module lets a caller construct a `TaskStatusChanged`
except by deliberately choosing to -- the real discipline that keeps
this honest lives in `jarvis.kernel.tasks`, which only ever constructs
one of these two event types immediately after its own real,
already-granted write to the task store actually happened (see that
module's own `write_task_record`/`update_task_status`, where an event
is built from the same `status`/`reason` values that were just
durably persisted, never a separate, independently-chosen value).

**Deliberately only two real event types, not five.** The prompt this
work package was built from lists `TaskCreated`/`TaskStatusChanged`/
`TaskCompleted`/`TaskFailed`/`TaskCancelled` as a conceptual sketch,
then explicitly says not to blindly implement every one of those if
the real task lifecycle doesn't support it, and to keep the schema
minimal. `jarvis.kernel.tasks` has exactly two real places a task's
stored state changes: a brand-new record is written
(`write_task_record`), or an existing record's status is updated in
place (`update_task_status`) -- the second of these already carries
real `previous_status`/`new_status`/`reason` fields able to represent
every real transition (`created` -> `running`, `running` -> `completed`,
`running` -> `failed`) without a separate class per destination status.
Introducing `TaskCompleted`/`TaskFailed`/`TaskCancelled` as distinct
dataclasses would just be `TaskStatusChanged` with `new_status` fixed
to one literal value each -- real duplication for no real subscriber
benefit (a subscriber that only cares about completions checks
`event.new_status == "completed"`, exactly as cheaply as it would
check `isinstance(event, TaskCompleted)`). `"cancelled"` remains a
real, reserved value in `jarvis.kernel.tasks.VALID_TASK_STATUSES` with
no code path that produces it yet, per that module's own docstring --
`TaskStatusChanged.new_status` can already represent it the moment a
real caller exists, with zero changes needed here.

**No concurrency, on purpose, not merely omitted.** Unlike
`AuditChain`'s own `threading.Lock` (added in response to a real,
demonstrated race under concurrent access), `EventBus` below has no
lock. This is a considered choice, not an oversight: every real caller
in this codebase either runs fully synchronously in one thread (every
one-shot CLI subcommand) or runs inside `jarvis.cli.ui_server`'s own
deliberately single-threaded `http.server.HTTPServer` (WP-108), which
never hands two requests to two threads at once -- so no real,
demonstrated concurrent access to one `EventBus` instance exists
anywhere in this codebase today. Adding a lock here regardless would
be exactly the kind of speculative, "what if someday" hardening this
project's own conventions reject; if a real, concurrent caller is ever
introduced, add the lock then, the same way `AuditChain`'s own lock was
added only once a real test proved the gap, not preemptively.

**Subscriber-failure semantics, a real, explicit decision (Step 8 of
this work package's own prompt)**: a subscriber that raises is caught
and logged via ``logging.exception`` -- visible, never silently
swallowed -- but does not propagate to :meth:`EventBus.publish`'s own
caller, and does not prevent any other subscriber from being notified.
The real state change a published event describes has, by
construction, *already happened and already been durably persisted*
before `publish()` is ever called (see `jarvis.kernel.tasks`'s own
call sites) -- a subscriber's own bug can therefore never roll back or
corrupt that real state; letting it propagate and abort the real
task-lifecycle operation's own return value to its own, unrelated
caller would be a far worse coupling than logging and moving on.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

_logger = logging.getLogger(__name__)

_E = TypeVar("_E")
"""The real event type a subscribe()/unsubscribe() call is about -- see EventBus.subscribe's
own docstring for why this is generic rather than a fixed Callable[[object], None]."""


@dataclass(frozen=True)
class TaskCreated:
    """A real, new task record came into existence in the task store.

    Attributes:
        event_id: A real, unique identifier for this event (from a
            real `IdPort`, supplied by the caller -- see module
            docstring for why this module never generates one itself).
        task_id: The real, stable identifier of the task this event is
            about (the same identifier `authorize_and_get_task` can
            look this task up by).
        goal: The real, natural-language goal this task was created
            for.
        status: The real, initial status this task was created with.
            Usually `"created"` (`authorize_and_create_task`'s own
            normal path) -- but a caller that writes a brand-new
            record directly at an already-terminal status (e.g.
            `jarvis.kernel.project`'s own legacy `write_task_record`
            call shape, which writes `"completed"`/`"failed"`
            directly, never passing through `"created"` first)
            produces this event with that real status instead. No
            fake intermediate `"created"` event is ever fabricated for
            a transition that did not actually happen.
        timestamp: A real, ISO-8601 wall-clock timestamp (from a real
            `ClockPort`, supplied by the caller), matching the new
            record's own real `created_at` value.
    """

    event_id: str
    task_id: str
    goal: str
    status: str
    timestamp: str


@dataclass(frozen=True)
class TaskStatusChanged:
    """A real, already-existing task's status actually changed in the task store.

    Attributes:
        event_id: As `TaskCreated.event_id`.
        task_id: As `TaskCreated.task_id`.
        goal: As `TaskCreated.goal`.
        previous_status: The task's real, previously-stored status,
            read directly from the record before this update
            overwrote it. `None` only if no prior record could be
            read (a real, honest "we don't actually know" rather than
            a guessed value).
        new_status: The task's real, newly-stored status -- one of
            `jarvis.kernel.tasks.VALID_TASK_STATUSES`.
        reason: The real reason accompanying this transition, if any
            (e.g. a `PlanningError`'s own message) -- `None` otherwise.
        timestamp: As `TaskCreated.timestamp`.
    """

    event_id: str
    task_id: str
    goal: str
    previous_status: str | None
    new_status: str
    reason: str | None
    timestamp: str


TaskEvent = TaskCreated | TaskStatusChanged
"""Every real event this module currently defines -- see module docstring for why
exactly these two, and no more, are real today."""


class EventBus:
    """A real, minimal, synchronous, in-process publish/subscribe mechanism.

    Delivery is synchronous and deterministic: `publish()` calls every
    subscriber registered for that exact event's own type, in the
    order each one called `subscribe()`, and returns only once every
    subscriber has been given a chance to run. No background thread,
    no async scheduling, no queue -- see module docstring for why.
    """

    def __init__(self) -> None:
        """Start with no subscribers at all -- a fresh, empty registry."""
        self._subscribers: dict[type, list[Callable[[Any], None]]] = {}

    def subscribe(self, event_type: type[_E], handler: Callable[[_E], None]) -> None:
        """Register `handler` to be called with every future event of exactly `event_type`.

        Generic over `_E` (rather than typed `Callable[[object], None]`)
        specifically so a real caller's own, precisely-typed handler
        (e.g. `Callable[[TaskCreated], None]`) type-checks directly,
        with no cast needed at the call site -- the internal registry
        below is where the real type-erasure this requires actually
        happens, not at any real caller's own subscribe()/unsubscribe()
        call.

        Args:
            event_type: The exact event class to listen for (e.g.
                `TaskCreated`) -- subscribing to a base/union type is
                not supported; a real subscriber that wants both
                `TaskCreated` and `TaskStatusChanged` calls this twice.
            handler: A real, callable handler. Called with the real
                event instance, nothing else.
        """
        self._subscribers.setdefault(event_type, []).append(handler)

    def unsubscribe(self, event_type: type[_E], handler: Callable[[_E], None]) -> None:
        """Remove `handler` from `event_type`'s own subscriber list. A no-op if not registered."""
        handlers = self._subscribers.get(event_type)
        if handlers is not None and handler in handlers:
            handlers.remove(handler)

    def publish(self, event: object) -> None:
        """Deliver `event` to every real subscriber registered for its exact type.

        A snapshot (`tuple(...)`) of the subscriber list is taken
        before delivery begins, so a handler that calls
        `subscribe()`/`unsubscribe()` on this same bus while it is
        itself being called cannot change which handlers receive
        *this* event -- delivery for one `publish()` call always
        reflects one fixed, consistent subscriber list.

        A subscriber that raises is caught, logged via
        `logging.exception` (never silently swallowed), and does not
        stop delivery to the remaining subscribers or propagate to
        this method's own caller -- see module docstring for the full
        reasoning.
        """
        handlers = tuple(self._subscribers.get(type(event), ()))
        for handler in handlers:
            try:
                handler(event)
            except Exception:
                _logger.exception(
                    "EventBus: subscriber %r raised handling %r -- continuing to the "
                    "remaining subscribers; the real state change this event describes "
                    "already happened and is unaffected.",
                    handler,
                    event,
                )
