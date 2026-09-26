from __future__ import annotations

import json
from pathlib import Path

import pytest

from squinch_qa.remote import _gh
from squinch_qa.remote.errors import PollError, PollTimeoutError
from squinch_qa.remote.poll import _run_title, find_dispatched_run, wait_for_completion


class TestRemotePoll:
    def test_find_matches_deterministic_run_name(self, tmp_path: Path, monkeypatch):
        def fake_run_gh(*args, timeout, cwd, check=True):
            assert args[:2] == ("run", "list")
            assert cwd == tmp_path
            return _gh.GhResult(
                tuple(args),
                0,
                json.dumps(
                    [
                        {"databaseId": 1, "name": "qa-1111111111-aaaaaaaa"},
                        {
                            "databaseId": 2,
                            "name": "qa-1234567890-deadbeef",
                            "status": "queued",
                            "conclusion": None,
                            "createdAt": "2026-01-01T00:00:00Z",
                        },
                    ]
                ),
                "",
            )

        monkeypatch.setattr(_gh, "run_gh", fake_run_gh)

        run = find_dispatched_run("1234567890-deadbeef", repo_root=tmp_path)

        assert run is not None
        assert run.database_id == 2
        assert run.name == "qa-1234567890-deadbeef"

    def test_wait_views_matched_run_until_completed(self, monkeypatch):
        calls = []

        def fake_run_gh(*args, timeout, cwd, check=True):
            calls.append(args)
            if args[:2] == ("run", "list"):
                return _gh.GhResult(
                    tuple(args),
                    0,
                    json.dumps([{"databaseId": 42, "name": "qa-1234567890-deadbeef"}]),
                    "",
                )
            if args[:2] == ("run", "view"):
                return _gh.GhResult(
                    tuple(args),
                    0,
                    json.dumps({"status": "completed", "conclusion": "success"}),
                    "",
                )
            raise AssertionError(args)

        monkeypatch.setattr(_gh, "run_gh", fake_run_gh)

        result = wait_for_completion(
            "1234567890-deadbeef",
            poll_interval=0,
            timeout=10,
            sleep=lambda _: None,
        )

        assert result.database_id == 42
        assert result.conclusion == "success"
        assert ("run", "view", "42", "--json", "status,conclusion") in calls

    def test_wait_times_out_when_run_never_appears(self, monkeypatch):
        ticks = iter([0.0, 1.0, 2.0, 3.0])

        def fake_run_gh(*args, timeout, cwd, check=True):
            return _gh.GhResult(tuple(args), 0, "[]", "")

        monkeypatch.setattr(_gh, "run_gh", fake_run_gh)

        with pytest.raises(PollTimeoutError):
            wait_for_completion(
                "1234567890-deadbeef",
                poll_interval=0,
                timeout=2,
                sleep=lambda _: None,
                monotonic=lambda: next(ticks),
            )

    def test_invalid_json_raises_poll_error(self, monkeypatch):
        monkeypatch.setattr(
            _gh,
            "run_gh",
            lambda *a, **k: _gh.GhResult(tuple(a), 0, "not json", ""),
        )

        with pytest.raises(PollError):
            find_dispatched_run("1234567890-deadbeef")

    @pytest.mark.parametrize("title_key", ["displayTitle", "title"])
    def test_find_matches_display_title_fallbacks(self, monkeypatch, title_key: str):
        def fake_run_gh(*args, timeout, cwd, check=True):
            return _gh.GhResult(
                tuple(args),
                0,
                json.dumps(
                    [
                        {
                            "databaseId": 42,
                            title_key: "qa-1234567890-deadbeef",
                            "status": "queued",
                            "conclusion": None,
                        }
                    ]
                ),
                "",
            )

        monkeypatch.setattr(_gh, "run_gh", fake_run_gh)

        run = find_dispatched_run("1234567890-deadbeef")

        assert run is not None
        assert run.database_id == 42
        assert run.name == "qa-1234567890-deadbeef"

    def test_run_title_prefers_name_over_display_title_and_title(self) -> None:
        item = {
            "name": "qa-name-value",
            "displayTitle": "qa-display-title-value",
            "title": "qa-title-value",
        }

        assert _run_title(item) == "qa-name-value"

    def test_run_title_prefers_display_title_over_title_when_name_absent(self) -> None:
        item = {
            "displayTitle": "qa-display-title-value",
            "title": "qa-title-value",
        }

        assert _run_title(item) == "qa-display-title-value"

    def test_find_dispatched_run_coerces_non_string_status_fields_to_none(
        self, monkeypatch
    ):
        def fake_run_gh(*args, timeout, cwd, check=True):
            return _gh.GhResult(
                tuple(args),
                0,
                json.dumps(
                    [
                        {
                            "databaseId": 42,
                            "name": "qa-1234567890-deadbeef",
                            "status": 123,
                            "conclusion": None,
                            "createdAt": ["not", "a", "string"],
                        }
                    ]
                ),
                "",
            )

        monkeypatch.setattr(_gh, "run_gh", fake_run_gh)

        run = find_dispatched_run("1234567890-deadbeef")

        assert run is not None
        assert run.status is None
        assert run.conclusion is None
        assert run.created_at is None

    def test_non_array_list_json_raises_poll_error(self, monkeypatch):
        monkeypatch.setattr(
            _gh,
            "run_gh",
            lambda *a, **k: _gh.GhResult(tuple(a), 0, "{}", ""),
        )

        with pytest.raises(PollError, match="not an array"):
            find_dispatched_run("1234567890-deadbeef")

    def test_matched_run_without_integer_database_id_raises(self, monkeypatch):
        monkeypatch.setattr(
            _gh,
            "run_gh",
            lambda *a, **k: _gh.GhResult(
                tuple(a), 0, '[{"name":"qa-1234567890-deadbeef"}]', ""
            ),
        )

        with pytest.raises(PollError, match="integer databaseId"):
            find_dispatched_run("1234567890-deadbeef")

    def test_wait_times_out_after_run_appears_but_never_completes(self, monkeypatch):
        ticks = iter([0.0, 0.5, 1.0, 1.5, 2.1])

        def fake_run_gh(*args, timeout, cwd, check=True):
            if args[:2] == ("run", "list"):
                return _gh.GhResult(
                    tuple(args),
                    0,
                    '[{"databaseId":42,"name":"qa-1234567890-deadbeef"}]',
                    "",
                )
            if args[:2] == ("run", "view"):
                return _gh.GhResult(
                    tuple(args), 0, '{"status":"in_progress","conclusion":null}', ""
                )
            raise AssertionError(args)

        monkeypatch.setattr(_gh, "run_gh", fake_run_gh)

        with pytest.raises(PollTimeoutError, match="waiting for run 42"):
            wait_for_completion(
                "1234567890-deadbeef",
                poll_interval=0,
                timeout=2,
                sleep=lambda _: None,
                monotonic=lambda: next(ticks),
            )
