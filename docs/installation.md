# Installation

The MiniMax integration is a **custom integration**. It is not part of
Home Assistant Core and must be installed separately.

## Prerequisites

- A running Home Assistant installation (Core, OS, Container or
  Supervised) on a version that ships Python 3.13 or later.
- A MiniMax account and API key. Sign up at the MiniMax console and
  create a key with permission to use the chat / TTS / STT / image
  endpoints.

## Install via HACS (recommended)

1. Open **HACS -> Integrations** in Home Assistant.
2. Click the three-dot menu in the top right and choose
   **Custom repositories**.
3. Add `https://github.com/RmG152/minimax-hass-integration` as a
   repository of type **Integration**.
4. Search for "MiniMax" in the HACS integration list and click
   **Download**.
5. Restart Home Assistant.

## Install manually

1. Download or clone the repository.
2. Copy the entire `custom_components/minimax/` folder into your
   Home Assistant config directory at
   `<config>/custom_components/minimax/`.
3. Restart Home Assistant.

## Configure the integration

1. Go to **Settings -> Devices & Services -> Add Integration**.
2. Search for **MiniMax** and select it.
3. Paste your API key into the **API Key** field and submit.
   The integration calls the MiniMax `/v1/get_voice` endpoint to verify
   the key before creating the entry; an invalid key returns the
   `invalid_auth` error and a network failure returns `cannot_connect`.
4. Four subentries are created with recommended defaults:
   - Conversation: `MiniMax Conversation`
   - TTS: `MiniMax TTS`
   - STT: `MiniMax STT`
   - AI Task: `MiniMax AI Task`
5. Select each subentry to fine-tune the prompt, model, voice, etc.
   The **Recommended** toggle hides advanced options; turn it off to
   reveal model selection, token limits, memory tuning, streaming
   format, etc.

## Wire the entities into the Assist pipeline

Open **Settings -> Voice assistants** and create or edit a pipeline:

- **Conversation agent** -> `MiniMax Conversation`
- **Speech-to-text** -> `MiniMax STT`
- **Text-to-speech** -> `MiniMax TTS` (select a voice for the chosen
  language)

The AI Task entity is available from automation editors and from the
`ai_task.generate_data` and `ai_task.generate_image` service calls.

## Troubleshooting

- Enable debug logging from
  **Settings -> System -> Logs -> Enable debug logging** for the
  `custom_components.minimax` logger.
- If the config flow shows "invalid_auth", regenerate the API key in
  the MiniMax console and re-enter it.
- If "cannot_connect" appears, verify that Home Assistant can reach
  `api.minimax.io` (no firewall blocking outbound HTTPS).
