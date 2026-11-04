# 8. Operations

## 8.1 Requirements

- Python 3.11 or newer.
- An API key for the chosen model provider. A free Gemini key can be created in Google AI Studio: **Get API key → Create API key**.
- Google Chrome or Microsoft Edge, only to build the documentation PDF.

## 8.2 Installation

```bash
git clone https://github.com/yesi07111/IA-Engineer-Technical-Test.git
cd IA-Engineer-Technical-Test
python -m venv .venv
.venv\Scripts\Activate.ps1          # Windows. On Linux/macOS: source .venv/bin/activate
pip install -e ".[google,web,mcp,dev]"
cp .env.example .env                # then set GEMINI_API_KEY
emporio check
```

## 8.3 Commands

| Command | Purpose |
|---|---|
| `emporio chat --show-tools` | Interactive chat; `--session ID` resumes a conversation |
| `emporio serve` | Web chat and HTTP API on http://127.0.0.1:8000 (API docs at `/docs`) |
| `emporio mcp` | MCP server over stdio for MCP-compatible assistants |
| `emporio check` | Validates the data files and the configuration |
| `emporio audit` | Lists data inconsistencies by severity |
| `emporio tickets` | Lists the cases forwarded to the store team |
| `python scripts/evaluate_agent.py` | Runs the behavioural evaluation |
| `python scripts/generate_examples.py` | Regenerates the example conversations |
| `python scripts/build_docs_pdf.py` | Builds the documentation PDF from the README and `docs/` |

## 8.4 Configuration

| Variable | Default | Description |
|---|---|---|
| `EMPORIO_MODEL` | `google_genai:gemini-3.5-flash` | Model in `provider:model` format |
| `GEMINI_API_KEY` | — | Provider key (also `GOOGLE_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`) |
| `EMPORIO_REQUESTS_PER_MINUTE` | empty | Client-side rate limit; 5 for the Gemini free tier |
| `EMPORIO_MAX_AGENT_STEPS` | 25 | Maximum reasoning steps per message |
| `EMPORIO_TEMPERATURE` | empty | Empty keeps the provider default |
| `EMPORIO_DATA_DIR` | `data` | Folder with the CSV files and the manual |
| `EMPORIO_MEMORY_DB` | `.memory/conversations.sqlite` | Conversation memory |
| `EMPORIO_TICKETS_FILE` | `.memory/handoff_tickets.jsonl` | Tickets for the store team |
| `EMPORIO_TIMEZONE` | `America/Campo_Grande` | Store time zone |

## 8.5 Using the MCP server

To use the store tools from an MCP client such as Claude Desktop, add this configuration:

```json
{
  "mcpServers": {
    "emporio-da-musica": {
      "command": "emporio",
      "args": ["mcp"],
      "cwd": "/path/to/IA-Engineer-Technical-Test"
    }
  }
}
```
