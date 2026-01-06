# Telegram View

Telegram bot interfaces for Felix Labs AI agents. Provides the user-facing layer that connects to the smart-orchestrator.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Telegram User                          │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                  TelegramView (view.py)                     │
│  - Entry point, initialized by orchestrator                 │
│  - Converts bot messages to Message schema                  │
│  - Routes responses back to users                           │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              Bot Interface (interfaces/)                    │
│  - TesterBotInterface: Full testing UI                      │
│  - ShowcaseInterface: Simplified demo UI                    │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                  smart-orchestrator                         │
│  - Receives Message objects via view_callback               │
│  - Processes with Agent_Ti                                  │
│  - Calls view.send_message() with response                  │
└─────────────────────────────────────────────────────────────┘
```

## Orchestrator Integration

The orchestrator initializes TelegramView with a callback:

```python
# In smart-orchestrator
from telegram_view import TelegramView

view = TelegramView.from_config(config, callback=self.handle_message)
await view.run()
```

### Message Flow

1. **Incoming**: User sends message → `TesterBotInterface` → `TelegramView._handle_bot_message()` → Creates `Message` object → `view_callback(message)` → Orchestrator
2. **Outgoing**: Orchestrator calls `view.send_message(chat_id, text)` → `TesterBotInterface.send_message()` → Telegram API

### Message Types

| Type | Description |
|------|-------------|
| `text_message` | Normal user text |
| `image_message` | Photo with optional caption |
| `document_message` | PDF, DOC, TXT files |
| `audio_message` | Voice/audio messages |
| `start_command` | /start or "Start New Chat" |
| `delete_all_history` | /delete_all_history command |

## Interfaces

### TesterBotInterface (`telegram_tester_bot.py`)

Full-featured testing interface:

- **Keyboard Buttons**: "Start New Chat", "Report Issue", "Select Model"
- **Model Selection**: Dynamic switching between AI models via inline keyboard
- **Issue Reporting**: Submit bugs to Google Sheets with full context
- **Image Support**: Process photos via URL forwarding
- **Chat History**: Tracks conversation for issue reports
- **Error Handling**: Centralized error reporting via `bug_catcher`

### ShowcaseInterface (`showcase_interface.py`)

Minimal interface for demos without testing features.

## Configuration

In orchestrator config YAML:

```yaml
view:
  type: telegram            # View type for orchestrator
  interface: tester         # 'tester' or 'showcase'
  show_model_selector: true # Enable model selection button
  title: "Welcome message"
```

Environment variable required:
```
TELEGRAM_BOT_TOKEN=your_bot_token
```

## Features

### Model Selection

When `show_model_selector: true`:

1. User taps "🤖 Select Model" button
2. Inline keyboard shows models from `common_utils.allowed_models`
3. Selection stored per-user in `user_model_preferences`
4. Model ID passed to orchestrator via `message.settings.model`
5. Orchestrator uses cached agent instance for selected model

### Issue Reporting

Workflow:
1. User taps "⚠️ Report Issue"
2. Bot prompts for description
3. On submit, `handle_issue_report()` appends to Google Sheets:
   - Timestamp
   - Model info (user-selected or config default with source indicator)
   - Full chat history
   - Issue description

### Supported Content Types

| Content | Handling |
|---------|----------|
| Text | Processed directly |
| Photo | Converted to URL via Telegram API |
| Document | PDF, DOC, TXT files - Base64 encoded |
| Voice/Audio | Audio messages - Base64 encoded |
| Other | "Unsupported content" response |

## Multimodal File Handling

The Telegram view handles multimodal content (images, documents, audio) and converts them to a format suitable for the AI agent.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                 Telegram Message                            │
│  (photo, document, voice, audio)                            │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              file_utils.py / image_utils.py                 │
│  - get_file_as_base64(): Download & encode to base64        │
│  - get_audio_as_base64(): Download & encode audio           │
│  - get_image_as_url(): Get Telegram file URL                │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                  TelegramView (view.py)                     │
│  Creates Message with:                                      │
│  - message_type: "image" | "document" | "audio"             │
│  - data: base64 content or URL                              │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                  smart-orchestrator                         │
│  Converts to AgentRequest with AgentRequestType:            │
│  - IMAGE, FILE, AUDIO                                       │
└─────────────────────────────────────────────────────────────┘
```

### File Processing Flow

**Documents (PDF, DOC, TXT):**
1. `telegram_tester_bot.py` receives document message
2. Calls `get_file_as_base64()` to download and encode
3. Creates `document_data` with: `{file: base64, mime_type, file_name, caption}`
4. Sends as `document_message` to orchestrator

**Audio/Voice:**
1. `telegram_tester_bot.py` receives audio/voice message
2. Calls `get_audio_as_base64()` to download and encode
3. Creates `audio_msg_data` with: `{audio: base64, mime_type, caption}`
4. Sends as `audio_message` to orchestrator

**Images:**
1. `telegram_tester_bot.py` receives photo message
2. Calls `get_image_as_url()` to get Telegram file URL
3. Creates `image_data` with: `{image: url, caption}`
4. Sends as `image_message` to orchestrator

### Utilities

**`file_utils.py`:**
- `get_file_as_base64(bot, message)` - Downloads document and returns (base64_data, mime_type)
- `get_audio_as_base64(bot, message)` - Downloads audio and returns (base64_data, mime_type)
- `is_supported_document(message)` - Checks if document type is supported (PDF, DOC, DOCX, TXT)

**`image_utils.py`:**
- `get_image_as_url(bot, message)` - Returns Telegram file URL for the largest photo size

### Why Base64?

Files are encoded to base64 rather than using URLs because:
1. **Persistence**: Base64 content is embedded in the message and stored in chat history
2. **OpenRouter Compatibility**: OpenRouter's file-parser plugin works with data URLs
3. **No External Dependencies**: Doesn't require public file hosting (S3, etc.)

## Project Structure

```
telegram_view/
├── src/telegram_view/
│   ├── view.py              # Main TelegramView class
│   ├── messages.py          # Localized message strings
│   └── interfaces/
│       ├── telegram_tester_bot.py  # Full testing interface
│       ├── showcase_interface.py   # Demo interface
│       ├── tester_utils.py         # Issue reporting, Google Sheets
│       ├── image_utils.py          # Image processing helpers
│       └── file_utils.py           # Document and audio file processing
├── main.py
└── pyproject.toml
```

## Dependencies

- `aiogram` - Telegram Bot API framework
- `gspread` - Google Sheets integration
- `oauth2client` - Google API authentication
- `common_utils` - Shared schemas, allowed models, logging
