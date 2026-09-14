import ctypes
import traceback


def attach(probe):
    if hasattr(probe, "_arrival_observer"):
        raise RuntimeError("arrival observer already attached")
    original_publish = probe._scan_event_hook.detour
    original_check = probe._check_navigation
    previous = None

    def snapshot():
        manager = probe._engine.scan_event_manager()
        events = probe._navigation.active_scan_event_snapshot()
        return {
            "manager": hex(manager),
            "count": len(events),
            "owned": [event for event in events if event["name"].startswith("SE_SQN")],
            "mission_active": probe._missions.active(b"SQN_SS11_NAV"),
        }

    def publish(original, manager, event_data, table, context, callback, address):
        name = ctypes.string_at(event_data + 0x228, 0x20).split(b"\0", 1)[0]
        owned = name.startswith(b"SE_SQN")
        if owned:
            probe._emit(
                "arrival_publish_before", snapshot=snapshot(), address=hex(address)
            )
        try:
            result = original_publish(
                original, manager, event_data, table, context, callback, address
            )
        except BaseException:
            probe._emit("arrival_publish_exception", error=traceback.format_exc())
            raise
        if owned:
            probe._emit(
                "arrival_publish_after", snapshot=snapshot(), address=hex(address)
            )
        return result

    def check():
        nonlocal previous
        original_check()
        current = snapshot()
        if current != previous:
            probe._emit("arrival_state_changed", snapshot=current, tick=probe._ticks)
            previous = current

    probe._arrival_observer = (original_publish, original_check)
    probe._scan_event_hook.detour = publish
    probe._check_navigation = check
    probe._emit("arrival_observer_attached")


def detach(probe):
    original_publish, original_check = probe._arrival_observer
    probe._scan_event_hook.detour = original_publish
    probe._check_navigation = original_check
    del probe._arrival_observer
    probe._emit("arrival_observer_detached")
