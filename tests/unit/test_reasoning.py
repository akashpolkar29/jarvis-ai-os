"""Unit tests for jarvis.domain.reasoning."""

from __future__ import annotations

import dataclasses

import pytest

from jarvis.domain.reasoning import ProviderProfile, TaskBudget


def test_provider_profile_accepts_valid_construction() -> None:
    """A well-formed ProviderProfile is constructable and its fields round-trip."""
    profile = ProviderProfile(name="provider-a", is_local=False)
    assert profile.name == "provider-a"
    assert profile.is_local is False


def test_provider_profile_accepts_local_provider() -> None:
    """is_local=True is a valid, distinct configuration from a cloud provider."""
    profile = ProviderProfile(name="local-model", is_local=True)
    assert profile.is_local is True


def test_provider_profile_rejects_empty_name() -> None:
    """ProviderProfile.name must not be empty."""
    with pytest.raises(ValueError, match=r"ProviderProfile\.name"):
        ProviderProfile(name="", is_local=False)


def test_provider_profile_is_frozen() -> None:
    """ProviderProfile is immutable, matching every other domain value object."""
    profile = ProviderProfile(name="provider-a", is_local=False)
    with pytest.raises(dataclasses.FrozenInstanceError):
        profile.is_local = True  # type: ignore[misc]


def test_task_budget_accepts_valid_construction() -> None:
    """A well-formed TaskBudget is constructable and its fields round-trip."""
    limit, spent = 10, 0
    budget = TaskBudget(limit=limit, spent=spent)
    assert budget.limit == limit
    assert budget.spent == spent


def test_task_budget_defaults_spent_to_zero() -> None:
    """A freshly constructed TaskBudget with only a limit has spent nothing yet."""
    assert TaskBudget(limit=5).spent == 0


def test_task_budget_rejects_negative_limit() -> None:
    """TaskBudget.limit must be non-negative."""
    with pytest.raises(ValueError, match=r"TaskBudget\.limit"):
        TaskBudget(limit=-1)


def test_task_budget_rejects_negative_spent() -> None:
    """TaskBudget.spent must be non-negative."""
    with pytest.raises(ValueError, match=r"TaskBudget\.spent"):
        TaskBudget(limit=10, spent=-1)


def test_task_budget_is_frozen() -> None:
    """TaskBudget is immutable, matching every other domain value object."""
    budget = TaskBudget(limit=10)
    with pytest.raises(dataclasses.FrozenInstanceError):
        budget.spent = 5  # type: ignore[misc]


def test_task_budget_remaining_is_limit_minus_spent() -> None:
    """remaining reflects what's left to spend."""
    limit, spent = 10, 4
    assert TaskBudget(limit=limit, spent=spent).remaining == limit - spent


def test_task_budget_remaining_floors_at_zero_when_overspent() -> None:
    """remaining never goes negative, even if spent exceeds limit."""
    limit, spent = 10, 15
    assert TaskBudget(limit=limit, spent=spent).remaining == 0


def test_task_budget_is_not_exhausted_below_limit() -> None:
    """A budget with spending left to go is not exhausted."""
    limit, spent = 10, 9
    assert TaskBudget(limit=limit, spent=spent).is_exhausted is False


def test_task_budget_is_exhausted_exactly_at_limit() -> None:
    """A budget with spent == limit is exhausted."""
    limit = 10
    assert TaskBudget(limit=limit, spent=limit).is_exhausted is True


def test_task_budget_is_exhausted_when_overspent() -> None:
    """A budget with spent > limit is still exhausted, not an error state."""
    limit, spent = 10, 11
    assert TaskBudget(limit=limit, spent=spent).is_exhausted is True


def test_task_budget_spend_returns_a_new_instance_and_does_not_mutate() -> None:
    """spend() returns a new TaskBudget; the original is untouched, like Tainted.map."""
    initial_spent, spend_amount = 2, 3
    original = TaskBudget(limit=10, spent=initial_spent)
    spent = original.spend(spend_amount)
    assert spent is not original
    assert spent.spent == initial_spent + spend_amount
    assert original.spent == initial_spent


def test_task_budget_driven_to_exhaustion_by_repeated_spend() -> None:
    """A budget spent down unit by unit is representable in pure domain terms alone."""
    limit = 3
    budget = TaskBudget(limit=limit)
    for _ in range(limit):
        assert budget.is_exhausted is False
        budget = budget.spend(1)
    assert budget.is_exhausted is True


def test_task_budget_spend_rejects_negative_amount() -> None:
    """spend() rejects a negative amount rather than silently reducing spend."""
    with pytest.raises(ValueError, match=r"TaskBudget\.spend"):
        TaskBudget(limit=10).spend(-1)
