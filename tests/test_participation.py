"""Tests for conservative provider session verification."""
from custom_components.chastity_calendar.participation import (
    chastify_session_active,
    chaster_has_active_lock,
    emlalock_session_active,
)


def test_emlalock_requires_an_open_session():
    assert emlalock_session_active(
        {"chastitysession": {"closedate": 0, "startdate": 100}}
    )
    assert not emlalock_session_active({"user": {"userid": "example"}})
    assert not emlalock_session_active(
        {"chastitysession": {"closedate": 123, "startdate": 100}}
    )
    assert not emlalock_session_active(
        {"chastitysession": {"closedate": 0, "startdate": 0}}
    )


def test_chastify_requires_current_lock_context():
    assert chastify_session_active({"lock": {"_id": "abc"}, "lockData": {}})
    assert not chastify_session_active({"message": "ok"})
    assert not chastify_session_active({"lock": {"_id": "abc"}})


def test_chaster_requires_explicit_locked_status():
    assert chaster_has_active_lock([{"status": "locked"}])
    assert not chaster_has_active_lock([{"status": "unlocked"}])
    assert not chaster_has_active_lock([{"status": "deserted"}])
    assert not chaster_has_active_lock({"status": "locked"})
