"""Config flow for MiniMax integration."""

import importlib
import logging
from typing import Any

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TemplateSelector,
    TextSelector,
)

from .api import MiniMaxApiClient, MiniMaxApiClientError
from .const import (
    CHAT_MODELS,
    CONF_API_KEY,
    CONF_CHAT_MODEL,
    CONF_CONVERSATION_EXPIRY_MINUTES,
    CONF_CONVERSATION_MAX_TOKENS,
    CONF_CONVERSATION_TTS_ENABLED,
    CONF_LANGUAGE_BOOST,
    CONF_MEMORY_ENABLED,
    CONF_MEMORY_EXPIRY_DAYS,
    CONF_MEMORY_MAX_COUNT,
    CONF_PITCH,
    CONF_PROMPT,
    CONF_RECOMMENDED,
    CONF_SPEED,
    CONF_STREAMING_FORMAT,
    CONF_TTS_MODEL,
    CONF_VOL,
    DEFAULT_AI_TASK_NAME,
    DEFAULT_CONVERSATION_EXPIRY_MINUTES,
    DEFAULT_CONVERSATION_MAX_TOKENS,
    DEFAULT_CONVERSATION_NAME,
    DEFAULT_CONVERSATION_TTS_ENABLED,
    DEFAULT_LANGUAGE_BOOST,
    DEFAULT_MEMORY_ENABLED,
    DEFAULT_MEMORY_EXPIRY_DAYS,
    DEFAULT_MEMORY_MAX_COUNT,
    DEFAULT_PITCH,
    DEFAULT_SPEED,
    DEFAULT_STREAMING_FORMAT,
    DEFAULT_TITLE,
    DEFAULT_VOL,
    DOMAIN,
    RECOMMENDED_AI_TASK_OPTIONS,
    RECOMMENDED_CHAT_MODEL,
    RECOMMENDED_CONVERSATION_OPTIONS,
    RECOMMENDED_STT_OPTIONS,
    RECOMMENDED_TTS_MODEL,
    RECOMMENDED_TTS_OPTIONS,
    STREAMING_FORMATS,
    TTS_MODELS,
)

_LOGGER = logging.getLogger(__name__)


def _schema_library() -> Any:
    """Return the schema library used by the running Home Assistant version.

    Home Assistant 2026.10 replaced voluptuous with probatio in its config flow
    API, so the config flow must build schemas with the library that matches
    the Home Assistant release it runs on.
    """
    version = tuple(int(part) for part in HA_VERSION.split(".")[:2])
    preferred = "probatio" if version >= (2026, 10) else "voluptuous"
    fallback = "voluptuous" if preferred == "probatio" else "probatio"

    for name in (preferred, fallback):
        try:
            return importlib.import_module(name)
        except ImportError:
            continue

    raise ImportError("Neither voluptuous nor probatio is available")


vol = _schema_library()

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
    }
)


class InvalidAuthError(Exception):
    """Invalid API key or authentication error."""


class CannotConnectError(Exception):
    """Cannot connect to MiniMax API."""


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Validate the user input allows us to connect."""
    _LOGGER.debug("Validating API key")
    api_key = data[CONF_API_KEY]

    client = MiniMaxApiClient(
        api_key=api_key,
        session=async_get_clientsession(hass),
    )

    if not await client.async_verify_connection():
        raise CannotConnectError("Failed to connect to MiniMax API")


def _default_subentries() -> list[dict[str, Any]]:
    """Return the default subentries created together with a new config entry."""
    return [
        {
            "subentry_type": "conversation",
            "data": RECOMMENDED_CONVERSATION_OPTIONS,
            "title": DEFAULT_CONVERSATION_NAME,
            "unique_id": None,
        },
        {
            "subentry_type": "tts",
            "data": RECOMMENDED_TTS_OPTIONS,
            "title": "MiniMax TTS",
            "unique_id": None,
        },
        {
            "subentry_type": "stt",
            "data": RECOMMENDED_STT_OPTIONS,
            "title": "MiniMax STT",
            "unique_id": None,
        },
        {
            "subentry_type": "ai_task_data",
            "data": RECOMMENDED_AI_TASK_OPTIONS,
            "title": DEFAULT_AI_TASK_NAME,
            "unique_id": None,
        },
    ]


def _is_auth_error(err: Exception) -> bool:
    """Return True when an API error was caused by an invalid API key."""
    err_str = str(err).lower()
    return "invalid api key" in err_str or "401" in err_str


def _masked_input(user_input: dict[str, Any]) -> dict[str, Any]:
    """Return the user input with the API key masked, so it can be logged."""
    return {k: ("***" if k == CONF_API_KEY else v) for k, v in user_input.items()}


def _api_client_error_key(err: Exception) -> str:
    """Return the config flow error key of an API client error."""
    if _is_auth_error(err):
        _LOGGER.warning("Invalid auth during config flow: %s", err)
        return "invalid_auth"
    _LOGGER.warning("Cannot connect during config flow: %s", err)
    return "cannot_connect"


class MiniMaxConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MiniMax."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input:
            _LOGGER.debug(
                "async_step_user called with input: %s", _masked_input(user_input)
            )
        else:
            _LOGGER.debug("async_step_user called with no input")
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match(user_input)
            try:
                await validate_input(self.hass, user_input)
            except InvalidAuthError:
                _LOGGER.warning("Invalid auth during config flow")
                errors["base"] = "invalid_auth"
            except CannotConnectError as err:
                _LOGGER.warning("Cannot connect during config flow: %s", err)
                errors["base"] = "cannot_connect"
            except MiniMaxApiClientError as err:
                errors["base"] = _api_client_error_key(err)
            else:
                _LOGGER.info("Config flow validation successful, creating entry")
                return self._create_or_update_entry(user_input)
        _LOGGER.debug("Showing user form")
        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    def _create_or_update_entry(self, user_input: dict[str, Any]) -> ConfigFlowResult:
        """Create the config entry, or update it during a re-auth flow."""
        if self.source == SOURCE_REAUTH:
            _LOGGER.debug("Re-auth flow, updating entry")
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(),
                data=user_input,
            )
        return self.async_create_entry(
            title=DEFAULT_TITLE,
            data=user_input,
            subentries=_default_subentries(),
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle re-authentication."""
        return await self.async_step_user()

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {
            "conversation": LLMSubentryFlowHandler,
            "tts": LLMSubentryFlowHandler,
            "stt": LLMSubentryFlowHandler,
            "ai_task_data": LLMSubentryFlowHandler,
        }


def _recommended_options(subentry_type: str) -> dict[str, Any]:
    """Return the recommended options of a subentry type."""
    if subentry_type == "tts":
        return RECOMMENDED_TTS_OPTIONS.copy()
    if subentry_type == "stt":
        return RECOMMENDED_STT_OPTIONS.copy()
    if subentry_type == "ai_task_data":
        return RECOMMENDED_AI_TASK_OPTIONS.copy()
    return RECOMMENDED_CONVERSATION_OPTIONS.copy()


class LLMSubentryFlowHandler(ConfigSubentryFlow):
    """Flow for managing subentries."""

    last_rendered_recommended = False

    @property
    def _is_new(self) -> bool:
        """Return if this is a new subentry."""
        return self.source == "user"

    async def async_step_set_options(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Set subentry options."""
        if self._get_entry().state is not ConfigEntryState.LOADED:
            _LOGGER.warning(
                "Cannot modify subentry for unloaded entry: %s",
                self._get_entry().entry_id,
            )
            return self.async_abort(reason="entry_not_loaded")

        _LOGGER.debug(
            "async_step_set_options called for %s, keys: %s",
            self._subentry_type,
            list(user_input.keys()) if user_input else None,
        )
        errors: dict[str, str] = {}

        if user_input is None:
            if self._is_new:
                options = _recommended_options(self._subentry_type)
                _LOGGER.debug(
                    "New subentry, using recommended options for: %s",
                    self._subentry_type,
                )
            else:
                options = self._get_reconfigure_subentry().data.copy()
                _LOGGER.debug(
                    "Existing subentry, current options keys: %s", list(options.keys())
                )
            self.last_rendered_recommended = bool(options.get(CONF_RECOMMENDED, False))
        else:
            _LOGGER.debug("User provided input keys: %s", list(user_input.keys()))
            if user_input.get(CONF_RECOMMENDED) == self.last_rendered_recommended:
                return self._save_subentry(user_input)
            self.last_rendered_recommended = user_input.get(CONF_RECOMMENDED, False)
            options = user_input

        try:
            schema = async_minimax_option_schema(
                self._is_new, self._subentry_type, options
            )
            _LOGGER.debug("Showing form for subentry type: %s", self._subentry_type)
            return self.async_show_form(
                step_id="set_options", data_schema=vol.Schema(schema), errors=errors
            )
        except Exception:
            _LOGGER.exception("Error building schema")
            return self.async_abort(reason="unknown")

    def _save_subentry(self, user_input: dict[str, Any]) -> SubentryFlowResult:
        """Create or update the subentry with the given input."""
        if self._is_new:
            _LOGGER.info("Creating new subentry: %s", self._subentry_type)
            subentry_data = {k: v for k, v in user_input.items() if k != "name"}
            return self.async_create_entry(
                title=user_input["name"],
                data=subentry_data,
            )
        _LOGGER.info("Updating existing subentry: %s", self._subentry_type)
        return self.async_update_and_abort(
            self._get_entry(),
            self._get_reconfigure_subentry(),
            data=user_input,
        )

    async_step_reconfigure = async_step_set_options
    async_step_user = async_step_set_options


def _suggested_chat_model(options: dict[str, Any]) -> str:
    """Return the stored chat model, or the recommended one when it is retired."""
    model = options.get(CONF_CHAT_MODEL, RECOMMENDED_CHAT_MODEL)
    if any(model == chat_model["value"] for chat_model in CHAT_MODELS):
        return model
    return RECOMMENDED_CHAT_MODEL


def _default_subentry_name(subentry_type: str, options: dict[str, Any]) -> str:
    """Return the default entity name of a new subentry."""
    default_name = options.get("name")
    if default_name:
        return default_name
    if subentry_type == "tts":
        return "MiniMax TTS"
    if subentry_type == "stt":
        return "MiniMax STT"
    if subentry_type == "ai_task_data":
        return DEFAULT_AI_TASK_NAME
    return DEFAULT_CONVERSATION_NAME


def _chat_model_selector() -> SelectSelector:
    """Return the chat model selector."""
    return SelectSelector(
        SelectSelectorConfig(
            mode=SelectSelectorMode.DROPDOWN,
            options=[
                SelectOptionDict(label=m["label"], value=m["value"])
                for m in CHAT_MODELS
            ],
        )
    )


def _conversation_base_options(options: dict[str, Any]) -> dict:
    """Return the base options of a conversation subentry."""
    return {
        vol.Optional(
            CONF_PROMPT,
            description={"suggested_value": options.get(CONF_PROMPT, "")},
        ): TemplateSelector(),
        vol.Optional(
            CONF_CONVERSATION_TTS_ENABLED,
            default=options.get(
                CONF_CONVERSATION_TTS_ENABLED, DEFAULT_CONVERSATION_TTS_ENABLED
            ),
        ): BooleanSelector(),
        vol.Optional(
            CONF_MEMORY_ENABLED,
            default=options.get(CONF_MEMORY_ENABLED, DEFAULT_MEMORY_ENABLED),
        ): BooleanSelector(),
    }


def _tts_base_options(options: dict[str, Any]) -> dict:
    """Return the base options of a TTS subentry."""
    return {
        vol.Optional(
            CONF_TTS_MODEL,
            description={
                "suggested_value": options.get(CONF_TTS_MODEL, RECOMMENDED_TTS_MODEL)
            },
        ): SelectSelector(
            SelectSelectorConfig(
                mode=SelectSelectorMode.DROPDOWN,
                options=[
                    SelectOptionDict(label=m["label"], value=m["value"])
                    for m in TTS_MODELS
                ],
            )
        ),
        vol.Optional(
            CONF_LANGUAGE_BOOST,
            description={
                "suggested_value": options.get(
                    CONF_LANGUAGE_BOOST, DEFAULT_LANGUAGE_BOOST
                )
            },
        ): TextSelector(),
    }


def _stt_base_options(options: dict[str, Any]) -> dict:
    """Return the base options of an STT subentry."""
    return {
        vol.Optional(
            CONF_PROMPT,
            description={"suggested_value": options.get(CONF_PROMPT, "")},
        ): TemplateSelector(),
    }


def _base_option_schema(subentry_type: str, options: dict[str, Any]) -> dict:
    """Return the type specific base options of a subentry."""
    if subentry_type == "conversation":
        return _conversation_base_options(options)
    if subentry_type == "tts":
        return _tts_base_options(options)
    if subentry_type == "stt":
        return _stt_base_options(options)
    return {}


def _conversation_advanced_options(options: dict[str, Any]) -> dict:
    """Return the advanced options of a conversation subentry."""
    return {
        vol.Optional(
            CONF_CHAT_MODEL,
            description={"suggested_value": _suggested_chat_model(options)},
        ): _chat_model_selector(),
        vol.Optional(
            CONF_CONVERSATION_MAX_TOKENS,
            default=options.get(
                CONF_CONVERSATION_MAX_TOKENS, DEFAULT_CONVERSATION_MAX_TOKENS
            ),
        ): NumberSelector(NumberSelectorConfig(min=1000, max=32000, step=1000)),
        vol.Optional(
            CONF_CONVERSATION_EXPIRY_MINUTES,
            default=options.get(
                CONF_CONVERSATION_EXPIRY_MINUTES,
                DEFAULT_CONVERSATION_EXPIRY_MINUTES,
            ),
        ): SelectSelector(
            SelectSelectorConfig(
                mode=SelectSelectorMode.DROPDOWN,
                options=[
                    SelectOptionDict(label="5 minutes", value="5"),
                    SelectOptionDict(label="15 minutes", value="15"),
                    SelectOptionDict(label="30 minutes", value="30"),
                    SelectOptionDict(label="1 hour", value="60"),
                ],
            )
        ),
        vol.Optional(
            CONF_MEMORY_MAX_COUNT,
            default=options.get(CONF_MEMORY_MAX_COUNT, DEFAULT_MEMORY_MAX_COUNT),
        ): NumberSelector(NumberSelectorConfig(min=10, max=100, step=10)),
        vol.Optional(
            CONF_MEMORY_EXPIRY_DAYS,
            default=options.get(CONF_MEMORY_EXPIRY_DAYS, DEFAULT_MEMORY_EXPIRY_DAYS),
        ): NumberSelector(NumberSelectorConfig(min=0, max=365, step=30)),
    }


def _tts_advanced_options(options: dict[str, Any]) -> dict:
    """Return the advanced options of a TTS subentry."""
    return {
        vol.Optional(
            CONF_STREAMING_FORMAT,
            default=options.get(CONF_STREAMING_FORMAT, DEFAULT_STREAMING_FORMAT),
        ): SelectSelector(
            SelectSelectorConfig(
                mode=SelectSelectorMode.DROPDOWN,
                options=STREAMING_FORMATS,
            )
        ),
        vol.Optional(
            CONF_SPEED,
            default=options.get(CONF_SPEED, DEFAULT_SPEED),
        ): NumberSelector(NumberSelectorConfig(min=0.5, max=2.0, step=0.1)),
        vol.Optional(
            CONF_VOL,
            default=options.get(CONF_VOL, DEFAULT_VOL),
        ): NumberSelector(NumberSelectorConfig(min=0.0, max=1.0, step=0.1)),
        vol.Optional(
            CONF_PITCH,
            default=options.get(CONF_PITCH, DEFAULT_PITCH),
        ): NumberSelector(NumberSelectorConfig(min=-10, max=10, step=1)),
    }


def _ai_task_advanced_options(options: dict[str, Any]) -> dict:
    """Return the advanced options of an AI Task subentry."""
    return {
        vol.Optional(
            CONF_CHAT_MODEL,
            description={"suggested_value": _suggested_chat_model(options)},
        ): _chat_model_selector(),
    }


def _advanced_option_schema(subentry_type: str, options: dict[str, Any]) -> dict:
    """Return the type specific advanced options of a subentry."""
    if subentry_type == "conversation":
        return _conversation_advanced_options(options)
    if subentry_type == "tts":
        return _tts_advanced_options(options)
    if subentry_type == "ai_task_data":
        return _ai_task_advanced_options(options)
    return {}


def async_minimax_option_schema(
    is_new: bool,
    subentry_type: str,
    options: dict[str, Any],
) -> dict:
    """Return a schema for MiniMax options."""
    schema: dict[vol.Required | vol.Optional, Any] = {}

    if is_new:
        schema[
            vol.Required("name", default=_default_subentry_name(subentry_type, options))
        ] = str

    schema.update(_base_option_schema(subentry_type, options))

    schema[
        vol.Required(CONF_RECOMMENDED, default=options.get(CONF_RECOMMENDED, False))
    ] = bool

    if options.get(CONF_RECOMMENDED):
        return schema

    schema.update(_advanced_option_schema(subentry_type, options))

    return schema
