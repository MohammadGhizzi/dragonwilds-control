#!/usr/bin/env python3
import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path


BASE_DIR = Path("/home/moha/palworld")
COMPOSE_FILE = BASE_DIR / "compose.yaml"
SAVED_DIR = BASE_DIR / "Saved"
SETTINGS_FILE = SAVED_DIR / "Config/LinuxServer/PalWorldSettings.ini"
BACKUP_SCRIPT = BASE_DIR / "scripts/backup.sh"
IMAGE_REPOSITORY = "ghcr.io/pocketpairjp/palserver"
CONTAINER_NAME = "palworld-server"
VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)\.(\d+)$")
IMAGE_LINE_RE = re.compile(
    rf"(?m)^(\s*image:\s*{re.escape(IMAGE_REPOSITORY)}:)([^\s#]+)(\s*(?:#.*)?)$"
)
OPTION_RE = re.compile(r"(?m)^OptionSettings=\((.*)\)\s*$")


def version_tuple(tag):
    match = VERSION_RE.fullmatch(tag)
    return tuple(int(part) for part in match.groups()) if match else None


def select_newest(tags):
    versions = [(version_tuple(tag), tag) for tag in tags]
    versions = [item for item in versions if item[0] is not None]
    if not versions:
        raise RuntimeError("The official registry returned no versioned tags")
    return max(versions, key=lambda item: item[0])[1]


def parse_fields(body):
    fields = []
    start = 0
    depth = 0
    quoted = False
    escaped = False
    for index, char in enumerate(body):
        if escaped:
            escaped = False
            continue
        if char == "\\" and quoted:
            escaped = True
            continue
        if char == '"':
            quoted = not quoted
        elif not quoted:
            if char in "([{" :
                depth += 1
            elif char in ")]}":
                depth -= 1
                if depth < 0:
                    raise ValueError("Unbalanced setting value")
            elif char == "," and depth == 0:
                fields.append(body[start:index])
                start = index + 1
    if quoted or depth != 0:
        raise ValueError("Unbalanced quotes or brackets in settings")
    fields.append(body[start:])

    parsed = []
    for field in fields:
        if not field.strip():
            continue
        if "=" not in field:
            raise ValueError(f"Invalid setting field: {field}")
        key, value = field.split("=", 1)
        parsed.append((key.strip(), value.strip()))
    return parsed


def merge_settings(active, defaults):
    active_match = OPTION_RE.search(active)
    default_match = OPTION_RE.search(defaults)
    if not active_match or not default_match:
        raise ValueError("OptionSettings tuple missing from Palworld settings")

    active_fields = parse_fields(active_match.group(1))
    default_fields = parse_fields(default_match.group(1))
    active_keys = {key for key, _ in active_fields}
    additions = [(key, value) for key, value in default_fields if key not in active_keys]
    if not additions:
        return active, []

    merged_fields = active_fields + additions
    merged_body = ",".join(f"{key}={value}" for key, value in merged_fields)
    merged = active[: active_match.start(1)] + merged_body + active[active_match.end(1) :]
    return merged, [key for key, _ in additions]


def run(args, *, capture=False, check=True):
    print("+", " ".join(str(arg) for arg in args), flush=True)
    return subprocess.run(
        [str(arg) for arg in args],
        cwd=BASE_DIR,
        check=check,
        text=True,
        capture_output=capture,
    )


def registry_tags():
    query = urllib.parse.urlencode(
        {
            "service": "ghcr.io",
            "scope": "repository:pocketpairjp/palserver:pull",
        }
    )
    with urllib.request.urlopen(f"https://ghcr.io/token?{query}", timeout=30) as response:
        token = json.load(response)["token"]
    request = urllib.request.Request(
        "https://ghcr.io/v2/pocketpairjp/palserver/tags/list?n=100",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response).get("tags", [])


def configured_tag(compose_text):
    match = IMAGE_LINE_RE.search(compose_text)
    if not match:
        raise ValueError("Official Palworld image line not found in compose.yaml")
    return match.group(2)


def compose_with_tag(compose_text, tag):
    updated, count = IMAGE_LINE_RE.subn(rf"\g<1>{tag}\g<3>", compose_text, count=1)
    if count != 1:
        raise ValueError("Could not update Palworld image tag")
    return updated


def atomic_write_preserving(path, content):
    stat = path.stat()
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False) as handle:
        handle.write(content)
        temp_path = Path(handle.name)
    os.chmod(temp_path, stat.st_mode)
    os.chown(temp_path, stat.st_uid, stat.st_gid)
    os.replace(temp_path, path)


def wait_for_container(timeout=120):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = run(
            ["docker", "inspect", "--format", "{{.State.Running}}", CONTAINER_NAME],
            capture=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip() == "true":
            time.sleep(10)
            confirm = run(
                ["docker", "inspect", "--format", "{{.State.Running}}", CONTAINER_NAME],
                capture=True,
                check=False,
            )
            if confirm.returncode == 0 and confirm.stdout.strip() == "true":
                return
        time.sleep(5)
    raise RuntimeError("Updated Palworld container did not remain running")


def deploy(new_tag, compose_text):
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    image = f"{IMAGE_REPOSITORY}:{new_tag}"
    config_backups = BASE_DIR / "backups/config"
    world_archives = BASE_DIR / "backups/world-resets"
    config_backups.mkdir(parents=True, exist_ok=True)
    world_archives.mkdir(parents=True, exist_ok=True)
    compose_backup = config_backups / f"compose-before-{new_tag}-{timestamp}.yaml"
    settings_backup = config_backups / f"PalWorldSettings-before-{new_tag}-{timestamp}.ini"
    world_archive = world_archives / f"SaveGames-before-{new_tag}-{timestamp}"

    run([BACKUP_SCRIPT])
    run(["docker", "pull", image])
    defaults = run(
        ["docker", "run", "--rm", "--entrypoint", "cat", image,
         "/pal/Package/DefaultPalWorldSettings.ini"],
        capture=True,
    ).stdout
    active_settings = SETTINGS_FILE.read_text(encoding="utf-8")
    merged_settings, added_keys = merge_settings(active_settings, defaults)
    updated_compose = compose_with_tag(compose_text, new_tag)
    shutil.copy2(COMPOSE_FILE, compose_backup)
    shutil.copy2(SETTINGS_FILE, settings_backup)

    stopped = False
    archived = False
    try:
        run(["docker", "compose", "down", "--timeout", "60"])
        stopped = True
        save_games = SAVED_DIR / "SaveGames"
        if save_games.exists():
            shutil.move(str(save_games), world_archive)
            archived = True
        atomic_write_preserving(COMPOSE_FILE, updated_compose)
        atomic_write_preserving(SETTINGS_FILE, merged_settings)
        run(["setfacl", "-m", "u:moha:rw", SETTINGS_FILE])
        run(["docker", "compose", "up", "-d", "--force-recreate"])
        wait_for_container()
    except Exception:
        if stopped:
            run(["docker", "compose", "down", "--timeout", "30"], check=False)
            shutil.copy2(compose_backup, COMPOSE_FILE)
            shutil.copy2(settings_backup, SETTINGS_FILE)
            save_games = SAVED_DIR / "SaveGames"
            if save_games.exists():
                failed_world = world_archives / f"failed-new-world-{timestamp}"
                shutil.move(str(save_games), failed_world)
            if archived and world_archive.exists():
                shutil.move(str(world_archive), save_games)
            run(["docker", "compose", "up", "-d", "--force-recreate"], check=False)
        raise

    print(f"Updated to {new_tag}; fresh world started", flush=True)
    print("New settings added:", ", ".join(added_keys) if added_keys else "none", flush=True)
    print("Archived test world:", world_archive if archived else "no active world existed", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    compose_text = COMPOSE_FILE.read_text(encoding="utf-8")
    current = configured_tag(compose_text)
    newest = select_newest(registry_tags())
    print(f"Configured image: {current}", flush=True)
    print(f"Newest official image: {newest}", flush=True)

    current_version = version_tuple(current)
    newest_version = version_tuple(newest)
    if current_version is None:
        raise RuntimeError(f"Configured image tag is not versioned: {current}")
    if newest_version <= current_version:
        print("No newer image; server and world left untouched", flush=True)
        return
    if args.dry_run:
        print(f"Dry run: would update to {newest} and create a fresh world", flush=True)
        return
    deploy(newest, compose_text)


if __name__ == "__main__":
    main()
