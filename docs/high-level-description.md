# MiniMax Home Assistant Integration

The MiniMax integration connects Home Assistant to the MiniMax AI cloud
service and exposes three voice/AI pipelines and one general-purpose
data task pipeline as Home Assistant entities:

- **Conversation** - LLM-powered conversation agent. Can be selected as
  the assist pipeline's conversation agent and supports calling Home
  Assistant services (lights, switches, climate, scripts, etc.) as
  tools, plus an optional long-term memory store.
- **Speech-to-Text (STT)** - transcribes microphone audio captured by
  the assist pipeline into text.
- **Text-to-Speech (TTS)** - synthesizes speech from text, both via the
  classic REST endpoint (returns an MP3) and via a WebSocket streaming
  endpoint that yields audio chunks per sentence for low-latency
  responses.
- **AI Task** - generates free-form text, structured (JSON-schema)
  data, or images for use in automations and scripts.

The integration only talks to the cloud on demand. There is no
background polling - every request is initiated by a user, a script, an
automation, or the assist pipeline. Authentication is by API key, and
the same key is used for all four platforms. A single config entry can
contain any combination of Conversation/STT/TTS/AI Task subentries, so
multiple agents with different prompts or models can coexist.

## Network and credentials

- All traffic uses HTTPS to `api.minimax.io`.
- The API key is stored in the config entry's `data` and is never
  written to logs (it is redacted from debug output).
- The integration uses Home Assistant's shared `aiohttp` client session
  for REST calls and an `httpx.AsyncClient` (wrapped inside the
  `anthropic` SDK) for the LLM chat endpoint.

## Related documentation

- [Installation](installation.md)
- [Removal](removal.md)
- [Quality scale rules](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/)
