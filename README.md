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
| Photo | Converted to URL, caption extracted |
| Other | "Unsupported content" response |

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
│       └── image_utils.py          # Image processing helpers
├── main.py
└── pyproject.toml
```

## Dependencies

- `aiogram` - Telegram Bot API framework
- `gspread` - Google Sheets integration
- `oauth2client` - Google API authentication
- `common_utils` - Shared schemas, allowed models, logging
