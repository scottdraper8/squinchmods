from pathlib import Path

from .errors import LaunchError

APP_ID = "275850"
VISIBLE_SAVE_ROWS = 5


def steam_root() -> Path:
    return Path.home() / ".local/share/Steam"


def save_profile() -> Path:
    root = (
        steam_root()
        / "steamapps/compatdata"
        / APP_ID
        / "pfx/drive_c/users/steamuser/AppData/Roaming/HelloGames/NMS"
    )
    profiles = sorted(path for path in root.glob("st_*") if path.is_dir())
    if len(profiles) != 1:
        raise LaunchError(
            f"Expected one NMS save profile under {root}, found {len(profiles)}"
        )
    return profiles[0]


def save_pair_index(path: Path) -> int:
    stem = path.stem
    if stem == "save":
        number = 1
    elif stem.startswith("save") and stem[4:].isdigit():
        number = int(stem[4:])
    else:
        raise LaunchError(f"Unrecognized NMS save filename: {path.name}")
    if number < 1:
        raise LaunchError(f"Invalid NMS save number: {path.name}")
    return (number - 1) // 2


def verify_latest_save(profile: Path) -> dict[str, object]:
    saves = [
        path
        for path in profile.glob("save*.hg")
        if path.is_file() and not path.name.startswith("mf_")
    ]
    if not saves:
        raise LaunchError(f"No save*.hg files found in {profile}")
    latest = max(saves, key=lambda path: (path.stat().st_mtime_ns, path.name))
    return verify_save(profile, latest.name)


def verify_save(profile: Path, filename: str) -> dict[str, object]:
    if Path(filename).name != filename or filename.startswith("mf_"):
        raise LaunchError(f"Invalid NMS save filename: {filename!r}")
    latest = profile / filename
    if latest.suffix != ".hg" or not latest.is_file():
        raise LaunchError(f"NMS save does not exist: {latest}")
    pair_index = save_pair_index(latest)
    if pair_index >= VISIBLE_SAVE_ROWS:
        raise LaunchError(
            f"The selected save is {latest.name} in row {pair_index + 1}, outside the "
            f"{VISIBLE_SAVE_ROWS} currently proven visible rows; refusing unproved scrolling"
        )
    return {
        "profile": str(profile),
        "save": str(latest),
        "save_pair": pair_index + 1,
        "mtime_ns": latest.stat().st_mtime_ns,
        "bytes": latest.stat().st_size,
    }
