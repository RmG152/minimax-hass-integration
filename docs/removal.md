# Removal

To remove the MiniMax integration:

1. Go to **Settings -> Devices & Services**.
2. Locate the **MiniMax** entry in the integrations list.
3. Click the three-dot menu on the entry and choose **Delete**.
   Confirm in the dialog. Deleting the entry automatically unloads the
   Conversation, STT, TTS and AI Task platforms, removes their
   entities, and discards the API key from the config entry.
4. If `MiniMax Conversation` was selected as your assist pipeline's
   conversation agent (or `MiniMax STT` / `MiniMax TTS` for speech),
   pick a different agent in
   **Settings -> Voice assistants** before or after removal.
5. If the long-term memory store was enabled, the file
   `core.minimax_memory_<entry_id>` in the Home Assistant storage
   directory (`<config>/.storage/`) is left behind after the integration
   is deleted. Remove it manually if you want to wipe stored user facts.

## Removing the custom component completely

- **HACS users** - open **HACS -> Integrations**, find **MiniMax**, and
  click **Remove**. Restart Home Assistant.
- **Manual install** - delete the folder
  `<config>/custom_components/minimax/` and restart Home Assistant.

There are no devices created in the device registry by this integration,
so no extra cleanup of devices is required.
