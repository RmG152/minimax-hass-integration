# Changelog

All notable changes to the MiniMax integration are listed here.

## 1.5.2 — 2026-10-26

### Fixed

- **Setting up the integration works again on recent Home Assistant versions.** Home
  Assistant changed the set of libraries it ships with in its 2026.9 and 2026.10
  releases, and the integration was relying on one that is no longer included. The
  symptom was an `Error setting up entry MiniMax for minimax` message and an
  integration that never finished loading. Updating to this release fixes it on
  Home Assistant 2026.9 and newer — nothing to do on your side, just update.
- **The voice assistant no longer returns empty answers with the new model.** The new
  default model always reasons before it replies, and that reasoning is counted
  against the same reply limit, which could leave the answer truncated or empty.
  The reply budget has been raised so there is room for both.

### Changed

- **MiniMax-M3.1-Flash is now the default chat model.** It is MiniMax's newest model:
  faster and cheaper than the previous ones, with a 1,000,000-token context window,
  so long conversations keep their full history. `MiniMax-M3` remains available as an
  alternative if you prefer it.
- **Chat models that MiniMax has retired are gone from the list.** MiniMax-M2,
  MiniMax-M2.1, MiniMax-M2.5 and MiniMax-M2.7 (and their `-highspeed` variants) are
  no longer offered to new accounts and stop working for pay-as-you-go accounts on
  18 November 2026. If you were using one of them, open the conversation
  configuration and pick MiniMax-M3.1-Flash — the form now suggests it for you
  automatically instead of showing the retired model.

### Unchanged

- Text-to-speech models, the voice list and image generation are untouched. The voice
  list keeps refreshing itself from MiniMax in the background, as usual.
