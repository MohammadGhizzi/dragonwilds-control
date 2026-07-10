# Palworld One-Shot 1.0 Update Design

## Goal

At 07:00 Asia/Riyadh on 2026-07-10, check the official Pocketpair container registry for a Palworld image newer than the currently configured image. Only when a newer image exists, back up and archive the current test world, deploy the new image, merge newly introduced INI keys without overwriting existing configuration values, and start a fresh world.

## Update Decision

The updater reads tags from `ghcr.io/pocketpairjp/palserver`, accepts version tags matching `vN.N.N.BUILD` or `N.N.N.BUILD`, and compares their numeric components. If the highest tag is not newer than the configured Compose tag, it exits successfully without stopping the server or changing files.

## Deployment Flow

When an update is available, the updater creates a timestamped tar backup of `Saved`, pulls the selected image, and extracts its `DefaultPalWorldSettings.ini`. It merges keys present in the new default but absent from the active `OptionSettings` tuple. Existing values, including passwords, ports, and gameplay choices, remain unchanged.

After preparation succeeds, the updater stops the Compose stack, archives `Saved/SaveGames` under `backups/world-resets`, updates only the Compose image tag, and recreates the container. The old test world remains recoverable but is no longer active. The new server starts with an empty world and creates fresh save data.

## Failure Handling

Failures before shutdown leave the running server untouched. Failures after shutdown attempt to restore the previous Compose file and world directory, then restart the previous image. All output is captured by journald. The timer is one-shot and does not recur.

## Verification

Tests cover version selection, no-update behavior, and INI merging. Installation verification checks the timer timestamp, script syntax, service permissions, and a dry run that must report no update without changing the current world.
