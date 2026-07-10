# Palworld One-Shot 1.0 Update Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run one guarded Palworld image update at 07:00 Asia/Riyadh and create a fresh world only if a newer official image is available.

**Architecture:** A Python updater isolates registry/version and INI merge logic from deployment orchestration. A one-shot systemd timer invokes it as root so Docker-owned saves can be archived safely; journald retains execution output.

**Tech Stack:** Python 3 standard library, Docker Compose, systemd, GHCR Registry HTTP API

## Global Constraints

- Never expose or modify API tokens or passwords.
- Do not stop or alter the active server when no newer image exists.
- Preserve current INI values and append only keys introduced by the new image.
- Archive the test world and create a fresh world only after backup and image pull succeed.
- The schedule runs once at `2026-07-10 07:00:00 Asia/Riyadh`.

---

### Task 1: Tested updater

**Files:**
- Create: `ops/palworld_one_shot_update.py`
- Test: `ops/test_palworld_one_shot_update.py`

**Interfaces:**
- Produces: `version_tuple(tag)`, `select_newest(tags)`, `parse_fields(body)`, `merge_settings(active, defaults)`, and `main()`.
- Consumes: `/home/moha/palworld/compose.yaml`, the active INI, GHCR tags, Docker, and the existing backup script.

- [ ] **Step 1: Write failing unit tests**

Test that version tags sort numerically, unrelated tags are ignored, nested tuple commas do not split values, missing defaults are appended, and existing values are preserved.

- [ ] **Step 2: Verify tests fail because the updater does not exist**

Run: `python -m unittest ops/test_palworld_one_shot_update.py -v`
Expected: import failure for `palworld_one_shot_update`.

- [ ] **Step 3: Implement the updater**

Use the anonymous GHCR token endpoint and tags API. On update: run the existing backup, pull the selected image, read `/pal/Package/DefaultPalWorldSettings.ini`, prepare merged settings, stop Compose, archive `SaveGames`, atomically replace Compose/INI, recreate the container, and verify it remains running. On deployment failure, restore Compose, INI, and the archived world before restarting the old image.

- [ ] **Step 4: Verify unit tests and syntax**

Run: `python -m unittest ops/test_palworld_one_shot_update.py -v` and `python -m py_compile ops/palworld_one_shot_update.py`.
Expected: all tests pass and compilation exits zero.

- [ ] **Step 5: Commit**

Commit the tested updater and test files without credentials.

### Task 2: Deploy one-shot timer

**Files:**
- Create remotely: `/home/moha/palworld/scripts/one-shot-1.0-update.py`
- Create remotely: `/etc/systemd/system/palworld-1.0-update.service`
- Create remotely: `/etc/systemd/system/palworld-1.0-update.timer`

**Interfaces:**
- Consumes: updater from Task 1.
- Produces: one execution at 07:00 with logs in `journalctl -u palworld-1.0-update.service`.

- [ ] **Step 1: Install the updater and root-owned systemd units**

Set the service to `Type=oneshot` and the timer to `OnCalendar=2026-07-10 07:00:00` with `Persistent=true`.

- [ ] **Step 2: Reload systemd and enable the timer**

Run: `systemctl daemon-reload` and `systemctl enable --now palworld-1.0-update.timer`.

- [ ] **Step 3: Verify without changing the world**

Run the updater with `--dry-run`; it must print the configured and newest tags and explicitly state whether it would update. Verify `systemctl list-timers` reports 07:00 and the active world files are unchanged.

- [ ] **Step 4: Verify service security and schedule**

Run `systemd-analyze verify` on both units, confirm the script is root-owned and not group/world writable, and confirm the server remains running.

