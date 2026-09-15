from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest


def _module():
    class Codes:
        def __getattr__(self, name: str) -> int:
            return sum(name.encode("ascii"))

    evdev = types.ModuleType("evdev")
    evdev.UInput = object
    evdev.AbsInfo = lambda *values: values
    evdev.ecodes = Codes()
    sys.modules["evdev"] = evdev
    path = Path(__file__).parents[2] / "client/form-control.py"
    spec = importlib.util.spec_from_file_location("form_control_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_pointer_target_must_be_inside_visible_form(monkeypatch: pytest.MonkeyPatch) -> None:
    form = _module()
    monkeypatch.setattr(
        form,
        "query",
        lambda *args: (
            "42"
            if args[:2] == ("search", "--onlyvisible")
            else "X=100\nY=200\nWIDTH=500\nHEIGHT=400"
        ),
    )
    monkeypatch.setattr(form, "ensure_uinput_access", lambda: pytest.fail("uinput accessed"))
    monkeypatch.setattr(sys, "argv", ["form-control.py", "click", "700", "300"])

    with pytest.raises(ValueError, match="outside"):
        form.main()


def test_pointer_refuses_click_after_focus_is_lost(monkeypatch: pytest.MonkeyPatch) -> None:
    form = _module()
    responses = iter(("42", "X=100\nY=200\nWIDTH=500\nHEIGHT=400", "42", "99"))
    monkeypatch.setattr(form, "query", lambda *_args: next(responses))
    monkeypatch.setattr(form, "ensure_uinput_access", lambda: None)
    monkeypatch.setattr(sys, "argv", ["form-control.py", "click", "300", "300"])

    class Pointer:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    monkeypatch.setattr(form, "UInput", lambda *_args, **_kwargs: Pointer())
    with pytest.raises(RuntimeError, match="lost focus"):
        form.main()


def test_pointer_converges_with_fractional_desktop_scaling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    form = _module()
    position = [293, 300]
    clicks = []

    def query(*args):
        if args[0] == "getwindowgeometry":
            return "X=100\nY=200\nWIDTH=500\nHEIGHT=400"
        if args[0] == "getmouselocation":
            return f"X={position[0]}\nY={position[1]}"
        return "42"

    class Pointer:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def write(self, kind, axis, value):
            if kind == form.e.EV_REL:
                index = 0 if axis == form.e.REL_X else 1
                position[index] += int(value * 0.5)
            else:
                clicks.append(value)

        def syn(self):
            pass

    monkeypatch.setattr(form, "query", query)
    monkeypatch.setattr(form, "ensure_uinput_access", lambda: None)
    monkeypatch.setattr(form.time, "sleep", lambda *_args: None)
    monkeypatch.setattr(form, "UInput", lambda *_args, **_kwargs: Pointer())
    monkeypatch.setattr(sys, "argv", ["form-control.py", "click", "300", "300"])
    form.main()
    assert abs(position[0] - 300) <= 6
    assert clicks == [1, 0]
