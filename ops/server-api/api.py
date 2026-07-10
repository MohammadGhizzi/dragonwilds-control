#!/usr/bin/env python3
import base64
import hmac
import json
import os
import re
import secrets
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOST = "127.0.0.1"
PORT = 8765
ALLOWED_ORIGIN = "https://mohammadghizzi.github.io"

ROOT = Path("/home/moha/palworld")
API_ROOT = Path("/home/moha/palworld-api")
CONFIG_PATH = ROOT / "Saved/Config/LinuxServer/PalWorldSettings.ini"
DEFAULT_CONFIG_PATH = ROOT / "DefaultPalWorldSettings.ini"
COMPOSE_PATH = ROOT / "compose.yaml"
LAUNCH_PATH = ROOT / "launch.json"
ADMIN_TOKEN_PATH = API_ROOT / "token"
OPERATOR_TOKEN_PATH = API_ROOT / "token_operator"
LOG_PATH = API_ROOT / "api.log"
BACKUP_SCRIPT = ROOT / "scripts/backup.sh"

DEFAULT_LAUNCH = {
    "port": 27015,
    "players": 4,
    "useperfthreads": True,
    "NoAsyncLoadingThread": True,
    "UseMultithreadForDS": True,
    "NumberOfWorkerThreadsServer": 8,
    "publiclobby": False,
    "publicip": "",
    "publicport": "",
    "logformat": "text",
}

FIELD_META = {
    "Difficulty": {"group": "World", "type": "enum", "choices": ["None"], "description": "Difficulty preset. Current dedicated-server default is None."},
    "RandomizerType": {"group": "World", "type": "enum", "choices": ["None", "Region", "All"], "description": "Pal spawn randomization mode."},
    "RandomizerSeed": {"group": "World", "type": "string", "description": "Seed used by randomizer mode."},
    "bIsRandomizerPalLevelRandom": {"group": "World", "type": "bool", "description": "If true, randomized Pal levels are fully random."},
    "DayTimeSpeedRate": {"group": "Balance", "type": "number", "description": "Daytime progression speed multiplier."},
    "NightTimeSpeedRate": {"group": "Balance", "type": "number", "description": "Nighttime progression speed multiplier."},
    "ExpRate": {"group": "Balance", "type": "number", "description": "EXP gain multiplier."},
    "PalCaptureRate": {"group": "Balance", "type": "number", "description": "Pal capture rate multiplier."},
    "PalSpawnNumRate": {"group": "Balance", "type": "number", "description": "Pal spawn rate. Higher values impact performance."},
    "PalDamageRateAttack": {"group": "Combat", "type": "number", "description": "Damage dealt by Pals multiplier."},
    "PalDamageRateDefense": {"group": "Combat", "type": "number", "description": "Damage taken by Pals multiplier."},
    "PlayerDamageRateAttack": {"group": "Combat", "type": "number", "description": "Damage dealt by players multiplier."},
    "PlayerDamageRateDefense": {"group": "Combat", "type": "number", "description": "Damage taken by players multiplier."},
    "DeathPenalty": {"group": "Death", "type": "enum", "choices": ["None", "Item", "ItemAndEquipment", "All"], "description": "Drops on death: none, items, items+equipment, or all items and team Pals."},
    "bHardcore": {"group": "Death", "type": "bool", "description": "Hardcore mode; death prevents normal respawn."},
    "bPalLost": {"group": "Death", "type": "bool", "description": "Permanently lose Pals on death."},
    "bCharacterRecreateInHardcore": {"group": "Death", "type": "bool", "description": "Allow recreating character after Hardcore death."},
    "BlockRespawnTime": {"group": "Death", "type": "number", "description": "Base cooldown before respawn, in seconds."},
    "RespawnPenaltyDurationThreshold": {"group": "Death", "type": "number", "description": "Survival-time threshold for applying repeat-death penalty."},
    "RespawnPenaltyTimeScale": {"group": "Death", "type": "number", "description": "Respawn cooldown multiplier after repeat-death threshold."},
    "bEnablePlayerToPlayerDamage": {"group": "PvP", "type": "bool", "description": "Enable player-versus-player damage."},
    "bEnableFriendlyFire": {"group": "PvP", "type": "bool", "description": "Enable friendly fire."},
    "bIsPvP": {"group": "PvP", "type": "bool", "description": "Enable PvP world mode."},
    "bCanPickupOtherGuildDeathPenaltyDrop": {"group": "PvP", "type": "bool", "description": "Allow pickup of death drops from other guilds."},
    "bEnableDefenseOtherGuildPlayer": {"group": "PvP", "type": "bool", "description": "Enable defense against other guild players."},
    "bDisplayPvPItemNumOnWorldMap_BaseCamp": {"group": "PvP", "type": "bool", "description": "Show PvP-exclusive item count on base-camp map."},
    "bDisplayPvPItemNumOnWorldMap_Player": {"group": "PvP", "type": "bool", "description": "Show player location / PvP item count on map."},
    "bAdditionalDropItemWhenPlayerKillingInPvPMode": {"group": "PvP", "type": "bool", "description": "Drop special item when killing a player in PvP."},
    "AdditionalDropItemWhenPlayerKillingInPvPMode": {"group": "PvP", "type": "string", "description": "Item ID for PvP kill special drop."},
    "AdditionalDropItemNumWhenPlayerKillingInPvPMode": {"group": "PvP", "type": "int", "description": "Quantity for PvP kill special drop."},
    "PlayerStomachDecreaceRate": {"group": "Survival", "type": "number", "description": "Player hunger depletion multiplier."},
    "PlayerStaminaDecreaceRate": {"group": "Survival", "type": "number", "description": "Player stamina depletion multiplier."},
    "PlayerAutoHPRegeneRate": {"group": "Survival", "type": "number", "description": "Player natural HP regeneration multiplier."},
    "PlayerAutoHpRegeneRateInSleep": {"group": "Survival", "type": "number", "description": "Player sleep HP regeneration multiplier."},
    "PalStomachDecreaceRate": {"group": "Survival", "type": "number", "description": "Pal hunger depletion multiplier."},
    "PalStaminaDecreaceRate": {"group": "Survival", "type": "number", "description": "Pal stamina depletion multiplier."},
    "PalAutoHPRegeneRate": {"group": "Survival", "type": "number", "description": "Pal natural HP regeneration multiplier."},
    "PalAutoHpRegeneRateInSleep": {"group": "Survival", "type": "number", "description": "Pal sleep / Palbox HP regeneration multiplier."},
    "ItemWeightRate": {"group": "Items", "type": "number", "description": "Item weight multiplier."},
    "ItemCorruptionMultiplier": {"group": "Items", "type": "number", "description": "Item corruption speed multiplier."},
    "EquipmentDurabilityDamageRate": {"group": "Items", "type": "number", "description": "Equipment durability loss multiplier."},
    "DropItemMaxNum": {"group": "Items", "type": "int", "description": "Maximum dropped items in world."},
    "DropItemMaxNum_UNKO": {"group": "Items", "type": "int", "description": "Maximum dropped UNKO items."},
    "DropItemAliveMaxHours": {"group": "Items", "type": "number", "description": "How long dropped items remain, in hours."},
    "CollectionDropRate": {"group": "Gathering", "type": "number", "description": "Gatherable item amount multiplier."},
    "CollectionObjectHpRate": {"group": "Gathering", "type": "number", "description": "Gatherable object health multiplier."},
    "CollectionObjectRespawnSpeedRate": {"group": "Gathering", "type": "number", "description": "Gatherable object respawn interval multiplier."},
    "EnemyDropItemRate": {"group": "Gathering", "type": "number", "description": "Enemy dropped item quantity multiplier."},
    "BuildObjectHpRate": {"group": "Base", "type": "number", "description": "Building health multiplier."},
    "BuildObjectDamageRate": {"group": "Base", "type": "number", "description": "Damage multiplier applied to buildings."},
    "BuildObjectDeteriorationDamageRate": {"group": "Base", "type": "number", "description": "Building decay speed multiplier."},
    "BaseCampMaxNum": {"group": "Base", "type": "int", "description": "Maximum base camps on the server."},
    "BaseCampMaxNumInGuild": {"group": "Base", "type": "int", "description": "Maximum bases per guild. Official max 10."},
    "BaseCampWorkerMaxNum": {"group": "Base", "type": "int", "description": "Maximum Pals per base. Official max 50; higher values increase load."},
    "MaxBuildingLimitNum": {"group": "Base", "type": "int", "description": "Per-player building cap. 0 = unlimited."},
    "bBuildAreaLimit": {"group": "Base", "type": "bool", "description": "Prevent building near structures such as fast-travel points."},
    "bInvisibleOtherGuildBaseCampAreaFX": {"group": "Base", "type": "bool", "description": "Hide other guild base-area boundary effects."},
    "WorkSpeedRate": {"group": "Base", "type": "number", "description": "Work speed multiplier."},
    "MonsterFarmActionSpeedRate": {"group": "Base", "type": "number", "description": "Monster Farm action-speed multiplier. New in Palworld 1.0; 1.0 is normal speed."},
    "bEnableBuildingPlayerUIdDisplay": {"group": "Base", "type": "bool", "description": "Show the owning player's user ID on buildings."},
    "BuildingNameDisplayCacheTTLSeconds": {"group": "Base", "type": "number", "description": "How long building-name display data is cached, in seconds."},
    "bEnableInvaderEnemy": {"group": "World Features", "type": "bool", "description": "Enable raids/invaders."},
    "bEnableFastTravel": {"group": "World Features", "type": "bool", "description": "Enable fast travel."},
    "bEnableFastTravelOnlyBaseCamp": {"group": "World Features", "type": "bool", "description": "Restrict fast travel to bases only."},
    "bIsStartLocationSelectByMap": {"group": "World Features", "type": "bool", "description": "Allow selecting start location from map."},
    "bExistPlayerAfterLogout": {"group": "World Features", "type": "bool", "description": "Players stay sleeping in-world after logout."},
    "SupplyDropSpan": {"group": "World Features", "type": "number", "description": "Meteorite / supply drop interval in minutes."},
    "EnablePredatorBossPal": {"group": "World Features", "type": "bool", "description": "Enable Predator Boss Pals."},
    "PalEggDefaultHatchingTime": {"group": "World Features", "type": "number", "description": "Huge egg hatch time in hours; other eggs scale from this."},
    "bAllowGlobalPalboxExport": {"group": "Global Palbox", "type": "bool", "description": "Allow saving to Global Palbox."},
    "bAllowGlobalPalboxImport": {"group": "Global Palbox", "type": "bool", "description": "Allow loading from Global Palbox."},
    "bAllowEnhanceStat_Health": {"group": "Player Stats", "type": "bool", "description": "Allow assigning stat points to HP."},
    "bAllowEnhanceStat_Attack": {"group": "Player Stats", "type": "bool", "description": "Allow assigning stat points to Attack."},
    "bAllowEnhanceStat_Stamina": {"group": "Player Stats", "type": "bool", "description": "Allow assigning stat points to Stamina."},
    "bAllowEnhanceStat_Weight": {"group": "Player Stats", "type": "bool", "description": "Allow assigning stat points to Carry Weight."},
    "bAllowEnhanceStat_WorkSpeed": {"group": "Player Stats", "type": "bool", "description": "Allow assigning stat points to Work Speed."},
    "ServerName": {"group": "Server", "type": "string", "description": "Server display name."},
    "ServerDescription": {"group": "Server", "type": "string", "description": "Server description."},
    "AdminPassword": {"group": "Server", "type": "string", "sensitive": True, "description": "Password used for admin privileges and local REST API auth."},
    "ServerPassword": {"group": "Server", "type": "string", "sensitive": True, "description": "Password players need to join."},
    "ServerPlayerMaxNum": {"group": "Server", "type": "int", "description": "Maximum players allowed by server config."},
    "PublicIP": {"group": "Server", "type": "string", "description": "Explicit public IP for community listing; blank auto-detects."},
    "PublicPort": {"group": "Server", "type": "int", "description": "Public port reported for community listing; does not change listen port."},
    "Region": {"group": "Server", "type": "string", "description": "Server region string."},
    "bUseAuth": {"group": "Server", "type": "bool", "description": "Use Palworld authentication."},
    "bAllowClientMod": {"group": "Server", "type": "bool", "description": "Allow players with mods enabled to join."},
    "CrossplayPlatforms": {"group": "Server", "type": "raw", "description": "Allowed platforms, e.g. (Steam,Xbox,PS5,Mac)."},
    "AllowConnectPlatform": {"group": "Server", "type": "enum", "choices": ["Steam", "Xbox"], "description": "Deprecated in current docs; use CrossplayPlatforms."},
    "BanListURL": {"group": "Moderation", "type": "string", "description": "URL for Palworld ban list."},
    "bShowPlayerList": {"group": "Moderation", "type": "bool", "description": "Show player list on ESC menu."},
    "ChatPostLimitPerMinute": {"group": "Moderation", "type": "int", "description": "Maximum chat messages per minute."},
    "bIsShowJoinLeftMessage": {"group": "Moderation", "type": "bool", "description": "Show join/leave messages."},
    "DenyTechnologyList": {"group": "Moderation", "type": "raw", "description": "Disabled technologies, e.g. (\"PALBOX\",\"RepairBench\")."},
    "GuildPlayerMaxNum": {"group": "Guild", "type": "int", "description": "Maximum players per guild."},
    "GuildRejoinCooldownMinutes": {"group": "Guild", "type": "int", "description": "Cooldown before rejoining a guild, in minutes."},
    "bAutoResetGuildNoOnlinePlayers": {"group": "Guild", "type": "bool", "description": "Delete structures/base Pals after no guild members log in."},
    "AutoResetGuildTimeNoOnlinePlayers": {"group": "Guild", "type": "number", "description": "Offline duration before guild reset triggers."},
    "bEnableNonLoginPenalty": {"group": "Guild", "type": "bool", "description": "Enable non-login penalty."},
    "AutoTransferMasterCheckIntervalSeconds": {"group": "Guild", "type": "number", "description": "Interval between automatic guild-master transfer checks, in seconds."},
    "AutoTransferMasterThresholdDays": {"group": "Guild", "type": "int", "description": "Guild-master inactivity threshold before automatic transfer, in days."},
    "RCONEnabled": {"group": "Local API", "type": "bool", "description": "Enable RCON."},
    "RCONPort": {"group": "Local API", "type": "int", "description": "RCON TCP port."},
    "RESTAPIEnabled": {"group": "Local API", "type": "bool", "description": "Enable Palworld REST API. Kept bound to localhost by Docker."},
    "RESTAPIPort": {"group": "Local API", "type": "int", "description": "Palworld REST API TCP port."},
    "LogFormatType": {"group": "Local API", "type": "enum", "choices": ["Text", "Json"], "description": "Server log format."},
    "bEnableVoiceChat": {"group": "Server", "type": "bool", "description": "Enable Palworld's built-in proximity voice chat."},
    "VoiceChatMaxVolumeDistance": {"group": "Server", "type": "number", "description": "Distance where proximity voice chat begins fading from maximum volume."},
    "VoiceChatZeroVolumeDistance": {"group": "Server", "type": "number", "description": "Distance where proximity voice chat becomes inaudible."},
    "bIsUseBackupSaveData": {"group": "Maintenance", "type": "bool", "description": "Enable Palworld built-in world backup save data."},
    "AutoSaveSpan": {"group": "Maintenance", "type": "number", "description": "Auto-save interval in seconds."},
    "ItemContainerForceMarkDirtyInterval": {"group": "Performance", "type": "number", "description": "Container UI force re-sync interval in seconds."},
    "ServerReplicatePawnCullDistance": {"group": "Performance", "type": "number", "description": "Pal sync distance from players in cm. Official range 5000-15000."},
    "PhysicsActiveDropItemMaxNum": {"group": "Performance", "type": "int", "description": "Maximum dropped items using active physics. -1 keeps the game default/unlimited behavior."},
    "PlayerDataPalStorageUpdateCheckTickInterval": {"group": "Performance", "type": "number", "description": "Internal interval for checking player Pal-storage updates. Keep 1 unless troubleshooting load."},
    "MaxGuildsPerFrame": {"group": "Performance", "type": "int", "description": "Maximum guilds processed in one server frame. Higher values finish work sooner but may create frame spikes."},
    "bActiveUNKO": {"group": "Other", "type": "bool", "description": "Legacy/undocumented Palworld setting."},
    "DropItemMaxNum_UNKO": {"group": "Other", "type": "int", "description": "Legacy/undocumented dropped UNKO cap."},
    "bEnableAimAssistPad": {"group": "Other", "type": "bool", "description": "Enable controller aim assist."},
    "bEnableAimAssistKeyboard": {"group": "Other", "type": "bool", "description": "Enable keyboard aim assist."},
    "bIsMultiplay": {"group": "Other", "type": "bool", "description": "Multiplayer flag present in default config."},
    "CoopPlayerMaxNum": {"group": "Other", "type": "int", "description": "Co-op max players; mostly relevant outside dedicated servers."},
}

GROUP_ORDER = [
    "Startup", "Server", "World", "World Features", "Balance", "Combat", "Survival",
    "Death", "PvP", "Base", "Gathering", "Items", "Guild", "Global Palbox",
    "Player Stats", "Moderation", "Local API", "Maintenance", "Performance", "Other",
]

rate = {}


def ensure_token(path):
    API_ROOT.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(secrets.token_urlsafe(32) + "\n", encoding="utf-8")
        os.chmod(path, 0o600)
    return path.read_text(encoding="utf-8").strip()


TOKENS = {
    ensure_token(ADMIN_TOKEN_PATH): "admin",
    ensure_token(OPERATOR_TOKEN_PATH): "operator",
}

CAPABILITIES = {
    "admin": {
        "role": "admin",
        "canEditSettings": True,
        "canEditStartup": True,
        "showTemperatures": True,
        "actions": ["start", "stop", "restart", "save", "backup", "update"],
    },
    "operator": {
        "role": "operator",
        "canEditSettings": False,
        "canEditStartup": False,
        "showTemperatures": False,
        "actions": ["start", "stop"],
    },
}


def log(msg):
    API_ROOT.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")


def run(cmd, timeout=60):
    p = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True, timeout=timeout)
    return {"rc": p.returncode, "out": p.stdout.strip(), "err": p.stderr.strip()}


def split_top(s):
    out, cur = [], []
    depth = 0
    quote = False
    esc = False
    for ch in s:
        if quote:
            cur.append(ch)
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                quote = False
            continue
        if ch == '"':
            quote = True
            cur.append(ch)
        elif ch == "(":
            depth += 1
            cur.append(ch)
        elif ch == ")":
            depth -= 1
            cur.append(ch)
        elif ch == "," and depth == 0:
            out.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if cur:
        out.append("".join(cur).strip())
    return out


def parse_options(text):
    line = next((ln.strip() for ln in text.splitlines() if ln.strip().startswith("OptionSettings=")), "")
    if not line or "(" not in line or ")" not in line:
        return [], {}
    body = line[line.index("(") + 1: line.rindex(")")]
    order, values = [], {}
    for part in split_top(body):
        if not part or "=" not in part:
            continue
        k, v = part.split("=", 1)
        k = k.strip()
        values[k] = v.strip()
        order.append(k)
    return order, values


def read_text(path):
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def quote_string(value):
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def display_value(raw):
    if raw is None:
        return ""
    if len(raw) >= 2 and raw[0] == '"' and raw[-1] == '"':
        return raw[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    if raw in ("True", "False"):
        return raw == "True"
    if re.fullmatch(r"-?\d+", raw or ""):
        try:
            return int(raw)
        except ValueError:
            return raw
    if re.fullmatch(r"-?\d+(\.\d+)?", raw or ""):
        try:
            return float(raw)
        except ValueError:
            return raw
    return raw


def infer_type(raw):
    if raw in ("True", "False"):
        return "bool"
    if raw and len(raw) >= 2 and raw[0] == '"' and raw[-1] == '"':
        return "string"
    if re.fullmatch(r"-?\d+", raw or ""):
        return "int"
    if re.fullmatch(r"-?\d+\.\d+", raw or ""):
        return "number"
    if raw and raw.startswith("("):
        return "raw"
    return "raw"


def to_raw(name, value, meta, current_raw=""):
    typ = meta.get("type") or infer_type(current_raw)
    if typ == "bool":
        return "True" if bool(value) else "False"
    if typ == "int":
        return str(int(value))
    if typ == "number":
        return f"{float(value):.6f}"
    if typ == "string":
        return quote_string(value or "")
    if typ == "enum":
        return str(value or "")
    return str(value if value is not None else "")


def serialize_config(order, values):
    body = ",".join(f"{k}={values[k]}" for k in order)
    return "[/Script/Pal.PalGameWorldSettings]\nOptionSettings=(" + body + ")\n"


def load_settings():
    default_order, defaults = parse_options(read_text(DEFAULT_CONFIG_PATH))
    order, values = parse_options(read_text(CONFIG_PATH))
    if not order:
        order, values = list(default_order), dict(defaults)
    for k in default_order:
        if k not in values:
            values[k] = defaults[k]
            order.append(k)
    return default_order, defaults, order, values


def build_settings_payload(role="admin"):
    default_order, defaults, order, values = load_settings()
    fields = []
    seen = set()
    for name in order + default_order:
        if name in seen:
            continue
        seen.add(name)
        raw = values.get(name, defaults.get(name, ""))
        default_raw = defaults.get(name, "")
        meta = FIELD_META.get(name, {})
        typ = meta.get("type") or infer_type(default_raw or raw)
        value = display_value(raw)
        raw_value = raw
        default_value = display_value(default_raw)
        default_raw_value = default_raw
        if role != "admin" and meta.get("sensitive"):
            value = ""
            raw_value = ""
            default_value = ""
            default_raw_value = ""
        fields.append({
            "name": name,
            "group": meta.get("group", "Other"),
            "type": typ,
            "value": value,
            "raw": raw_value,
            "default": default_value,
            "defaultRaw": default_raw_value,
            "description": meta.get("description", ""),
            "choices": meta.get("choices"),
            "sensitive": bool(meta.get("sensitive")),
        })
    groups = {g: [] for g in GROUP_ORDER}
    for f in fields:
        groups.setdefault(f["group"], []).append(f)
    return {
        "fields": fields,
        "groups": [{"name": g, "fields": groups[g]} for g in groups if groups[g]],
        "raw": read_text(CONFIG_PATH),
        "path": str(CONFIG_PATH),
    }


def read_launch():
    if LAUNCH_PATH.exists():
        try:
            data = json.loads(LAUNCH_PATH.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    else:
        data = {}
    merged = dict(DEFAULT_LAUNCH)
    merged.update({k: data[k] for k in data if k in DEFAULT_LAUNCH})
    return merged


def write_launch(data):
    launch = dict(DEFAULT_LAUNCH)
    launch.update({k: data[k] for k in data if k in DEFAULT_LAUNCH})
    launch["port"] = int(launch["port"])
    launch["players"] = int(launch["players"])
    launch["NumberOfWorkerThreadsServer"] = int(launch["NumberOfWorkerThreadsServer"])
    LAUNCH_PATH.write_text(json.dumps(launch, indent=2) + "\n", encoding="utf-8")
    os.chmod(LAUNCH_PATH, 0o600)
    command = [
        f"-port={launch['port']}",
        f"-players={launch['players']}",
    ]
    for flag in ("useperfthreads", "NoAsyncLoadingThread", "UseMultithreadForDS"):
        if launch.get(flag):
            command.append("-" + flag)
    if launch.get("NumberOfWorkerThreadsServer"):
        command.append(f"-NumberOfWorkerThreadsServer={launch['NumberOfWorkerThreadsServer']}")
    if launch.get("publiclobby"):
        command.append("-publiclobby")
    if launch.get("publicip"):
        command.append(f"-publicip={launch['publicip']}")
    if launch.get("publicport"):
        command.append(f"-publicport={launch['publicport']}")
    if launch.get("logformat"):
        command.append(f"-logformat={launch['logformat']}")
    cmd_yaml = "\n".join(f"      - {arg}" for arg in command)
    compose = f"""services:
  palworld-server:
    image: ghcr.io/pocketpairjp/palserver:v0.7.3.90464
    container_name: palworld-server
    restart: unless-stopped
    entrypoint: /pal/helper.sh
    command:
{cmd_yaml}
    ports:
      - "{launch['port']}:{launch['port']}/udp"
      - "127.0.0.1:8212:8212/tcp"
    volumes:
      - ./helper.sh:/pal/helper.sh:ro
      - ./Saved:/pal/Package/Pal/Saved
"""
    COMPOSE_PATH.write_text(compose, encoding="utf-8")
    return launch


def basic_auth_header():
    _, _, _, values = load_settings()
    password = display_value(values.get("AdminPassword", '""')) or ""
    token = base64.b64encode(f"admin:{password}".encode()).decode()
    return {"Authorization": "Basic " + token}


def pal_rest(path, method="GET", body=None, timeout=5):
    data = None
    headers = basic_auth_header()
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(f"http://127.0.0.1:8212/v1/api{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", errors="replace")
            return {"ok": True, "status": r.status, "json": json.loads(raw) if raw else None, "raw": raw}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def system_stats():
    stats = {}
    try:
        meminfo = Path("/proc/meminfo").read_text().splitlines()
        parsed = {}
        for line in meminfo:
            k, rest = line.split(":", 1)
            parsed[k] = int(rest.strip().split()[0]) * 1024
        total = parsed.get("MemTotal", 0)
        avail = parsed.get("MemAvailable", 0)
        stats["memory"] = {
            "total": total,
            "available": avail,
            "used": max(total - avail, 0),
            "usedPct": round((total - avail) / total * 100, 1) if total else 0,
        }
    except Exception:
        stats["memory"] = None
    try:
        stats["load"] = list(os.getloadavg())
    except Exception:
        stats["load"] = None
    try:
        usage = shutil.disk_usage(str(ROOT))
        stats["disk"] = {"total": usage.total, "used": usage.used, "free": usage.free, "usedPct": round(usage.used / usage.total * 100, 1)}
    except Exception:
        stats["disk"] = None
    temps = []
    for hw in Path("/sys/class/hwmon").glob("hwmon*"):
        try:
            chip = (hw / "name").read_text().strip()
        except Exception:
            chip = hw.name
        for inp in hw.glob("temp*_input"):
            try:
                idx = inp.name.replace("temp", "").replace("_input", "")
                label_path = hw / f"temp{idx}_label"
                label = label_path.read_text().strip() if label_path.exists() else f"temp{idx}"
                temps.append({"label": f"{chip}: {label}", "c": round(int(inp.read_text().strip()) / 1000, 1)})
            except Exception:
                pass
    stats["temps"] = temps
    return stats


def service_active():
    p = run(["systemctl", "is-active", "palworld.service"], timeout=10)
    return p["out"].strip() == "active"


def status_payload(role="admin"):
    players = pal_rest("/players")
    info = pal_rest("/info")
    metrics = pal_rest("/metrics")
    inspect = run(["docker", "inspect", "palworld-server"], timeout=10)
    docker_state = None
    if inspect["rc"] == 0:
        try:
            docker_state = json.loads(inspect["out"])[0].get("State")
        except Exception:
            docker_state = None
    public_ip = run(["curl", "-s", "--max-time", "5", "https://api.ipify.org"], timeout=8)["out"].strip()
    tailscale_ip = run(["tailscale", "ip", "-4"], timeout=8)["out"].strip()
    stats = system_stats()
    backups = []
    for p in sorted((ROOT / "backups").glob("palworld-saved-*.tar.gz"), key=lambda x: x.stat().st_mtime, reverse=True)[:8]:
        st = p.stat()
        backups.append({"name": p.name, "size": st.st_size, "mtime": st.st_mtime})
    launch = read_launch()
    payload = {
        "ok": True,
        "role": role,
        "capabilities": CAPABILITIES.get(role, CAPABILITIES["operator"]),
        "active": service_active(),
        "dockerState": docker_state,
        "serverInfo": info.get("json") if info.get("ok") else None,
        "players": (players.get("json") or {}).get("players", []) if players.get("ok") else [],
        "playersError": None if players.get("ok") else players.get("error"),
        "metrics": metrics.get("json") if metrics.get("ok") else None,
        "publicIp": public_ip,
        "externalPort": int(launch["port"]),
        "lanIp": "192.168.100.127",
        "tailscaleIp": tailscale_ip,
        "launch": launch,
        "backups": backups,
        **stats,
        "now": time.time(),
    }
    if role != "admin":
        payload.pop("temps", None)
    return payload


class Handler(BaseHTTPRequestHandler):
    server_version = "palctl/1"

    def end_headers(self):
        origin = self.headers.get("Origin")
        if origin == ALLOWED_ORIGIN:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Access-Control-Max-Age", "600")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def auth_role(self):
        ip = self.client_address[0]
        now = time.time()
        bucket = rate.setdefault(ip, [])
        rate[ip] = [t for t in bucket if now - t < 60]
        if len(rate[ip]) > 90:
            return None
        rate[ip].append(now)
        header = self.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return None
        supplied = header.split(" ", 1)[1].strip()
        for token, role in TOKENS.items():
            if hmac.compare_digest(supplied, token):
                return role
        return None

    def json(self, code, obj):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def body(self):
        n = int(self.headers.get("Content-Length") or "0")
        return json.loads(self.rfile.read(n).decode("utf-8") or "{}") if n else {}

    def require(self):
        if self.path == "/api/health":
            return True
        role = self.auth_role()
        if not role:
            self.json(401, {"ok": False, "error": "unauthorized"})
            return False
        self.role = role
        return True

    def require_admin(self):
        if getattr(self, "role", None) != "admin":
            self.json(403, {"ok": False, "error": "forbidden"})
            return False
        return True

    def do_GET(self):
        try:
            if not self.require():
                return
            if self.path == "/api/health":
                return self.json(200, {"ok": True, "service": "palctl"})
            if self.path == "/api/status":
                return self.json(200, status_payload(getattr(self, "role", "operator")))
            if self.path.startswith("/api/logs"):
                n = 200
                m = re.search(r"[?&]n=(\d+)", self.path)
                if m:
                    n = max(20, min(1000, int(m.group(1))))
                p = run(["docker", "compose", "logs", "--tail", str(n), "palworld-server"], timeout=20)
                return self.json(200, {"ok": p["rc"] == 0, "logs": p["out"] or p["err"], "rc": p["rc"]})
            if self.path == "/api/settings":
                role = getattr(self, "role", "operator")
                return self.json(200, {"ok": True, **build_settings_payload(role), "launch": read_launch(), "capabilities": CAPABILITIES.get(role, CAPABILITIES["operator"])})
            self.json(404, {"ok": False, "error": "not found"})
        except Exception as e:
            log(f"GET {self.path} ERROR {e}")
            self.json(500, {"ok": False, "error": str(e)})

    def do_POST(self):
        try:
            if not self.require():
                return
            data = self.body()
            if self.path == "/api/action":
                action = data.get("action")
                allowed = CAPABILITIES.get(getattr(self, "role", "operator"), CAPABILITIES["operator"])["actions"]
                if action not in allowed:
                    return self.json(403, {"ok": False, "error": "forbidden"})
                if action == "start":
                    p = run(["sudo", "-n", "/usr/bin/systemctl", "start", "palworld.service"], timeout=90)
                elif action == "stop":
                    p = run(["sudo", "-n", "/usr/bin/systemctl", "stop", "palworld.service"], timeout=90)
                elif action == "restart":
                    p = run(["sudo", "-n", "/usr/bin/systemctl", "restart", "palworld.service"], timeout=120)
                elif action == "backup":
                    p = run([str(BACKUP_SCRIPT)], timeout=120)
                elif action == "save":
                    rest = pal_rest("/save", method="POST", timeout=10)
                    return self.json(200, {"ok": rest.get("ok"), "result": rest})
                elif action == "update":
                    p1 = run(["sudo", "-n", "/usr/bin/systemctl", "stop", "palworld.service"], timeout=120)
                    p2 = run(["docker", "compose", "pull"], timeout=1800)
                    p3 = run(["sudo", "-n", "/usr/bin/systemctl", "start", "palworld.service"], timeout=120)
                    return self.json(200, {"ok": p1["rc"] == p2["rc"] == p3["rc"] == 0, "steps": [p1, p2, p3]})
                else:
                    return self.json(400, {"ok": False, "error": "bad action"})
                return self.json(200, {"ok": p["rc"] == 0, **p})
            if self.path == "/api/settings":
                if not self.require_admin():
                    return
                settings = data.get("settings", {})
                default_order, defaults, order, values = load_settings()
                known = set(order) | set(default_order)
                for k, v in settings.items():
                    if k not in known:
                        return self.json(400, {"ok": False, "error": f"unknown setting: {k}"})
                    meta = FIELD_META.get(k, {"type": infer_type(defaults.get(k, values.get(k, "")))})
                    values[k] = to_raw(k, v, meta, values.get(k, defaults.get(k, "")))
                    if k not in order:
                        order.append(k)
                stamp = time.strftime("%Y%m%d-%H%M%S")
                if CONFIG_PATH.exists():
                    config_backup_dir = ROOT / "backups/config"
                    config_backup_dir.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(CONFIG_PATH, config_backup_dir / f"PalWorldSettings.ini.bak-{stamp}")
                CONFIG_PATH.write_text(serialize_config(order, values), encoding="utf-8")
                if data.get("restart"):
                    run(["sudo", "-n", "/usr/bin/systemctl", "restart", "palworld.service"], timeout=120)
                return self.json(200, {"ok": True, "settings": build_settings_payload("admin")})
            if self.path == "/api/launch":
                if not self.require_admin():
                    return
                launch = write_launch(data.get("launch", {}))
                # Keep config values aligned with startup args where appropriate.
                _, _, order, values = load_settings()
                for k, v in {"ServerPlayerMaxNum": str(launch["players"]), "PublicPort": str(launch["port"])}.items():
                    values[k] = v
                    if k not in order:
                        order.append(k)
                CONFIG_PATH.write_text(serialize_config(order, values), encoding="utf-8")
                if data.get("restart"):
                    run(["sudo", "-n", "/usr/bin/systemctl", "restart", "palworld.service"], timeout=120)
                return self.json(200, {"ok": True, "launch": launch})
            self.json(404, {"ok": False, "error": "not found"})
        except Exception as e:
            log(f"POST {self.path} ERROR {e}")
            self.json(500, {"ok": False, "error": str(e)})

    def log_message(self, fmt, *args):
        log(f'{self.client_address[0]} "{self.requestline}" {fmt % args}')


if __name__ == "__main__":
    API_ROOT.mkdir(parents=True, exist_ok=True)
    os.chdir(ROOT)
    log(f"starting on {HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
