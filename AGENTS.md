# AGENTS.md - MiniMax Home Assistant Integration

This is a custom Home Assistant integration for MiniMax AI (chat, TTS, STT).

## Project Overview

- **Domain**: `minimax`
- **Type**: Custom integration (service, cloud polling)
- **Platforms**: Conversation, STT, TTS
- **Config Flow**: Yes (with subentries for conversation, TTS, STT)
- **Inspiration**: https://github.com/home-assistant/core/tree/dev/homeassistant/components/google_generative_ai_conversation

## Repository Structure

```
minimax-homeassistant-integration/
├── __init__.py          # Integration entry point, async_setup_entry
├── config_flow.py       # Config flow + LLMSubentryFlowHandler for subentries
├── conversation.py      # ConversationEntity implementation
├── stt.py               # SpeechToTextEntity implementation
├── tts.py               # TextToSpeechEntity implementation
├── websocket_client.py  # WebSocket client for streaming TTS
├── const.py             # Constants, voice IDs, recommended options
├── manifest.json        # Integration manifest
├── strings.json         # (legacy) English translations
└── translations/
    └── en.json          # English translations (preferred format)
```

## Build/Lint/Test Commands

**Always run before every commit:**

```bash
# 1. Lint with ruff (fix all issues):
python -m ruff check .

# 2. Format with ruff:
python -m ruff format .

# 3. Run tests with coverage:
python -m pytest tests/ --cov --cov-branch --cov-report=xml
```

Aim for 100% patch coverage on new/modified lines.

Additional commands:

```bash
# Verify Python syntax only:
python3 -m py_compile __init__.py const.py config_flow.py conversation.py stt.py tts.py

# For type checking:
python -m mypy .
```

## Running tests on Windows

`pytest-homeassistant-custom-component` (transitive dep) imports `fcntl` /
`resource` / `pwd` / `grp` at collection time, which fails on Windows because
those modules don't exist. A small stub is required before pytest loads.

**Preferred:** use the helper script (it auto-installs the stub):

```powershell
# Run the full suite:
.\scripts\run_tests.ps1

# Run a single file:
.\scripts\run_tests.ps1 -Path "tests/test_memory.py"

# Run a single test with verbose output, no coverage:
.\scripts\run_tests.ps1 -Path "tests/test_ai_task.py::TestSchemaHelpers::test_format_object_schema_property_with_enum" -NoCoverage -VerboseOutput
```

**Manual** (equivalent commands, paste into PowerShell):

```powershell
# One-time: install the fcntl/resource/pwd/grp stub at user-site so any pytest run finds it
$userSite = python -c "import site; print(site.getusersitepackages())"
New-Item -ItemType Directory -Path $userSite -Force | Out-Null
@'
import sys, types
for _n in ("fcntl", "resource", "pwd", "grp"):
    if _n in sys.modules: continue
    m = types.ModuleType(_n)
    if _n == "fcntl":
        m.LOCK_EX, m.LOCK_SH, m.LOCK_NB, m.LOCK_UN = 2, 1, 4, 8
        m.flock = lambda *a, **k: 0
        m.ioctl = lambda *a, **k: 0
    elif _n == "resource":
        m.RLIMIT_CPU, m.RLIMIT_NOFILE = 0, 7
        m.getrlimit = lambda *a, **k: (0, 0)
        m.setrlimit = lambda *a, **k: None
    elif _n == "pwd":
        m.getpwnam = lambda *a, **k: types.SimpleNamespace(pw_uid=0)
        m.getpwuid = lambda *a, **k: types.SimpleNamespace(pw_name="root")
    elif _n == "grp":
        m.getgrnam = lambda *a, **k: types.SimpleNamespace(gr_gid=0)
        m.getgrgid = lambda *a, **k: types.SimpleNamespace(gr_name="root")
    sys.modules[_n] = m
'@ | Set-Content -LiteralPath (Join-Path $userSite "sitecustomize.py") -Encoding UTF8

# Then run pytest with plugin auto-load disabled and only the plugins we need:
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = "1"
python -m pytest tests/ `
    --no-header --tb=line --confcutdir=. `
    -p asyncio --asyncio-mode=auto `
    -p pytest_cov -p pytest_timeout -p pytest_aiohttp
```

**Why the flags are needed:**
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` prevents pytest from auto-loading
  `pytest-homeassistant-custom-component` (which would crash on the fcntl
  import).
- The explicit `-p asyncio / pytest_cov / pytest_timeout / pytest_aiohttp`
  flags are required because the auto-loader is off.
- `--asyncio-mode=auto` lets async test functions run without explicit
  `@pytest.mark.asyncio` markers.
- `--confcutdir=.` makes sure `tests/conftest.py` is the one used (it stubs
  `turbojpeg` and patches `aiohttp` clients).
- The user-site `sitecustomize.py` stub is harmless on Linux/macOS (it just
  registers modules that already exist and are left alone).

## Deployment

**Home Assistant VM:** SSH `root@10.0.100.61` | HA runs Alpine Linux HAOS in KVM

**Custom components path:** `/homeassistant/custom_components/minimax/`

**Workflow:** Update via HACS (Home Assistant Community Store). For manual deployment:

```bash
# Create translations directory if needed:
ssh root@10.0.100.61 'mkdir -p /homeassistant/custom_components/minimax/translations'

# Deploy translations:
scp translations/en.json root@10.0.100.61:/homeassistant/custom_components/minimax/translations/

# Deploy all Python files:
scp __init__.py const.py config_flow.py conversation.py stt.py tts.py manifest.json root@10.0.100.61:/homeassistant/custom_components/minimax/

# Verify on server:
ssh root@10.0.100.61 'python3 -m py_compile /homeassistant/custom_components/minimax/*.py && echo "OK"'

# Restart HA:
ssh root@10.0.100.61 'ha core restart'
# Wait ~65 seconds for HA to restart

# Check logs (debug logging for custom_components.minimax must be enabled in HA UI):
ssh root@10.0.100.61 'tail /homeassistant/homeassistant.log | grep -i minimax'
```

**Important:** 
- For HACS updates: commit to GitHub, create a new release, then use HACS to redownload
- After deploying, always restart HA with `ha core restart` and wait ~65 seconds
- Verify files compile with `python3 -m py_compile` before restarting
- manifest.json must include: `version`, `config_flow`, `requirements:[]`, `dependencies:[]`
- Logger name: `custom_components.minimax`
- Log file location: `/homeassistant/homeassistant.log` (not `ha core logs`)

## Code Style Guidelines

### General

- Follow Home Assistant's integration guidelines: https://developers.home-assistant.io/docs/integration_format/
- Use async/await for all I/O operations
- Always import from `homeassistant` packages, not assume availability

### Type Annotations

- Use type aliases for complex types:
  ```python
  type MiniMaxConfigEntry = ConfigEntry[dict[str, Any]]
  ```
- Use `type: ignore` sparingly and only when absolutely necessary

### Imports

Order imports as:
1. Standard library (`logging`, `re`, etc.)
2. Third-party (`httpx`, `voluptuous`, `aiohttp`)
3. Home Assistant core (`homeassistant.*`)
4. Local relative imports (`.const`, `.config_flow`)

```python
import logging
from typing import Any

import httpx
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.core import HomeAssistant

from .const import DOMAIN, LOGGER
```

### Naming Conventions

- **Modules**: `snake_case.py`
- **Classes**: `PascalCase`
- **Functions/variables**: `snake_case`
- **Constants**: `UPPER_SNAKE_CASE`
- **Types**: `PascalCase` (for type aliases and generics)
- **Private members**: `_prefixed_with_underscore`

### Logging

- Get logger via `from .const import LOGGER` or `import logging` then `logging.getLogger(__name__)`
- Use appropriate log levels:
  - `LOGGER.debug()` for detailed debugging info
  - `LOGGER.warning()` for recoverable issues
  - `LOGGER.error()` for errors that don't prevent operation
  - `LOGGER.exception()` for errors with tracebacks

### Error Handling

Use Home Assistant's config entry exceptions:
- `ConfigEntryAuthFailed` - Invalid API key or authentication error
- `ConfigEntryError` - General configuration/connection errors
- `ConfigEntryNotReady` - Service not available (e.g., timeout)

```python
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError, ConfigEntryNotReady

try:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(...)
except httpx.HTTPStatusError as e:
    if e.response.status_code == 401:
        raise ConfigEntryAuthFailed("Invalid API key") from e
    raise ConfigEntryError(f"HTTP error: {e.response.status_code}") from e
except httpx.TimeoutException as e:
    raise ConfigEntryNotReady("Timeout connecting to MiniMax API") from e
```

### Config Flow

- VERSION = 1, MINOR_VERSION = 1 for new integrations
- Use voluptuous schemas for data validation
- ConfigSubentryFlow for managing subentries (conversation, TTS, STT each have own subentry)
- Always handle errors gracefully with user-friendly messages

### Entity Implementation

- Entity classes inherit from appropriate Home Assistant base classes
- Set `_attr_name` and `_attr_unique_id` in `__init__`
- Use `@property` for supported features/languages/etc.
- Call `async_set_agent` / `async_unset_agent` in `async_added_to_hass` / `async_will_remove_from_hass`

### API Calls

- Use `httpx.AsyncClient` with explicit timeout (30s for chat, 60s for TTS/STT)
- Always set `Content-Type: application/json` for JSON APIs
- Use `response.raise_for_status()` to catch HTTP errors
- Handle all exceptions gracefully - never let exceptions propagate to HA

### Async Patterns

```python
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    for subentry in config_entry.subentries.values():
        if subentry.subentry_type != "conversation":
            continue
        async_add_entities(
            [MiniMaxConversationEntity(config_entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )
```

### File Structure for New Files

When creating new platform files:
1. Docstring with purpose
2. `from __future__ import annotations`
3. Imports (stdlib, third-party, HA, local)
4. Constants/API endpoints
5. Setup function
6. Entity class(es)

### Working with Translations

**For custom integrations, use `translations/<locale>.json` format (NOT `strings.json`):**

```
translations/
└── en.json    # English translations
```

**Translation file structure for config flow with subentries:**

```json
{
  "config": {
    "abort": { ... },
    "error": { ... },
    "step": {
      "user": {
        "title": "...",
        "description": "...",
        "data": { "api_key": "API Key", ... },
        "data_description": { "api_key": "...", ... }
      }
    }
  },
  "config_subentries": {
    "conversation": { "abort": {}, "error": {}, "initiate_flow": {}, "step": { "set_options": {} } },
    "stt": { "abort": {}, "initiate_flow": {}, "step": { "set_options": {} } },
    "tts": { "abort": {}, "initiate_flow": {}, "step": { "set_options": {} } }
  }
}
```

**Important translation rules:**
- Field names in `data` must match the voluptuous schema field names exactly
- Use `data_description` for helper text under fields
- After changing translations, hard refresh browser (Ctrl+Shift+R) to see changes
- Logger name: `custom_components.minimax`

### Comments

- Do not add comments unless explicitly required
- Code should be self-documenting through clear naming

### Constants

Define all magic numbers and strings in `const.py`:
- API endpoints
- Default values
- Configuration keys (`CONF_*`)
- Voice IDs
- Recommended options

### Testing

When adding tests:
- Place in `tests/` directory
- Use `pytest` and `pytest-asyncio`
- Mock httpx responses
- Test config flow with `config_flow.TestFlows`
- Run ruff lint and format
<!-- , then run `python -m pytest tests/ --cov --cov-branch --cov-report=xml` before every commit -->
- Aim for 100% patch coverage on new/modified lines
- Use `pytest.approx()` for floating-point comparisons to avoid SonarCloud warnings
- Use `https://` URLs in test data to avoid SonarCloud security hotspots

## Common Issues and Solutions

### Config flow "400 Bad Request" error when reconfiguring
- **Cause**: `SelectSelector` options must use `SelectOptionDict` objects with **string values**, not plain dicts or integers
- **Fix**: Use `SelectOptionDict(label="...", value="string_value")` for all select options
- **Example**:
  ```python
  # WRONG - plain dict with integer value
  {"label": "5 minutes", "value": 5}
  
  # CORRECT - SelectOptionDict with string value  
  SelectOptionDict(label="5 minutes", value="5")
  ```

### Config flow "expected str for dictionary value" error
- **Cause**: Same as above - SelectSelector doesn't accept plain dicts
- **Fix**: Import `SelectOptionDict` from `homeassistant.helpers.selector` and use it for all `SelectSelector` options

### TTS/TTS preview grayed out in Voice Assistants settings
- **Cause**: Language format incorrect (e.g., "English" instead of "en-US")
- **Fix**: Use BCP 47 language tags: `"en-US"`, `"zh-CN"`, etc.

### Conversation agent fails with IntentResponse error
- **Cause**: Wrong import `from homeassistant.components.conversation import IntentResponse`
- **Fix**: Use `from homeassistant.helpers import intent` then `intent.IntentResponse`

### async_get_supported_voices not called / voices not loading
- **Cause**: Method was declared as `async def`
- **Fix**: Use `@callback` decorator on a sync method:
  ```python
  @callback
  def async_get_supported_voices(self, language: str) -> list[Voice] | None:
  ```

### Raw field names showing in config flow UI (e.g., "api_key" instead of "API Key")
- **Cause**: Translation file missing or incorrectly formatted
- **Fix**: Create `translations/en.json` with proper structure (see Working with Translations above)

### Debug logs not appearing
- **Cause**: Debug logging not enabled in HA UI
- **Fix**: Enable debug logging in HA UI: Settings → System → Logs → click "Enable debug logging" for "custom_components.minimax"

### AI response includes thinking/reasoning text
- **Cause**: MiniMax API returns thinking content in `<think>...</think>` tags within the content field
- **Fix**: Strip with regex: `re.sub(r"<think>.*?</think>", "", response_text, flags=re.DOTALL)`
