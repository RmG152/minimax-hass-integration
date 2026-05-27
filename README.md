<!-- markdownlint-disable first-line-heading -->
<!-- markdownlint-disable no-inline-html -->

<img src="https://play-lh.googleusercontent.com/hsPVehKUDPBS1LiaAkitNSmZtVNjb5-zbnlhHuNid42l5RMWWVEEiHqF5vSawdNK6ro"
     alt="MiniMax icon"
     width="35%"
     align="right"
     style="float: right; margin: 10px 0px 20px 20px;" />

[![GitHub Release](https://img.shields.io/github/release/RmG152/minimax-hass-integration.svg?style=flat-square)](https://github.com/RmG152/minimax-hass-integration/releases)
[![Build Status](https://img.shields.io/github/actions/workflow/status/RmG152/minimax-hass-integration/tests.yaml?branch=master&style=flat-square)](https://github.com/RmG152/minimax-hass-integration/actions/workflows/tests.yaml)
[![Test Coverage](https://img.shields.io/codecov/c/gh/RmG152/minimax-hass-integration?style=flat-square)](https://app.codecov.io/gh/RmG152/minimax-hass-integration/)
[![License](https://img.shields.io/github/license/RmG152/minimax-hass-integration.svg?style=flat-square)](LICENSE)
[![hacs](https://img.shields.io/badge/HACS-custom-orange.svg?style=flat-square)](https://hacs.xyz)

# MiniMax Home Assistant Integration

Provides conversation, text-to-speech (TTS), and speech-to-text (STT) capabilities powered by MiniMax AI.

## Features

- **Conversation Agent**: Natural language conversations with MiniMax AI
- **Text-to-Speech**: High-quality voice synthesis with customizable voices
- **Speech-to-Text**: Audio transcription for voice commands
- **AI Task**: Generate structured data and images using MiniMax AI for advanced automation scenarios

## Installation

Easiest install is via [HACS](https://hacs.xyz/):

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=RmG152&repository=minimax-hass-integration&category=integration)

`HACS -> Integrations -> Explore & Add Repositories -> MiniMax`

For manual installation for advanced users, copy `custom_components/minimax` to
your `custom_components` folder in Home Assistant.

## Configuration

After installation:

1. Go to **Configuration > Integrations**
2. Click **Add Integration**
3. Search for **MiniMax**
4. Enter your MiniMax API key

### Subentries

The integration creates four subentries for independent configuration:

- **Conversation**: Configure the AI model and system prompt
- **TTS**: Select voice, speed, pitch, and volume
- **STT**: Configure transcription prompt
- **AI Task**: Generate structured data and images for automations

## Requirements

- Home Assistant 2025.4.1 or later
- MiniMax API key from [MiniMax Platform](https://platform.minimax.io)

## Credits & Acknowledgments

This integration was originally created by [**double-em**](https://github.com/double-em/minimax-hass-integration). We are grateful for their foundational work, which made this project possible.

This fork, maintained by [**RmG152**](https://github.com/RmG152/minimax-hass-integration), builds on the original with the following improvements:

- **AI Task support**: Added integration with MiniMax AI Task capabilities for advanced automation scenarios
- **Ongoing maintenance & support**: Continued development, bug fixes, and compatibility updates for newer Home Assistant releases

If you'd like to use or contribute to the original version, visit [double-em/minimax-hass-integration](https://github.com/double-em/minimax-hass-integration).

## License

MIT License
