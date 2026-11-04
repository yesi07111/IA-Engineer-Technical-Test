# 6. Security and Error Handling

## 6.1 Security and privacy

| Concern | Control |
|---|---|
| Personal data (LGPD) | Order tools require the order number **and** the e-mail or phone used in the purchase. A wrong contact and a non-existent order receive the same neutral message, so orders can not be enumerated. No tool lists customer data. |
| Prompt injection | The prompt treats customer messages and tool results as data. The evaluation includes an injection attempt that asks for another customer's e-mail; no data was leaked. |
| Invented discounts or rules | Prices and rules come only from tools. Requests such as "give me 50% off" are refused while the official price is shown. |
| Secrets | API keys are read from a local `.env` file excluded from version control. An automated test fails if any tracked file contains a key pattern. |
| Web API exposure | Inputs are validated (session id format, message length). Provider errors return HTTP 503 without internal details. The web chat is meant for local demonstration and has no authentication. |

## 6.2 Error handling

Errors are handled in the layer that can act on them, and the customer never receives a stack trace.

| Situation | Behaviour |
|---|---|
| Invalid or incomplete configuration, or a missing API key | Detected at startup, with an explanation of the setting to fix. |
| Missing or corrupted data file | `DataLoadError` with file and line; `emporio check` validates without calling the model. |
| Invalid tool arguments from the model | Rejected by the tool schema; the model receives the message and corrects the call. |
| Valid but meaningless requests (unknown category, inverted price range, invalid ticket contact) | Structured error with guidance, for example the list of valid categories. |
| Unexpected failure inside a tool | Logged; the model is told not to guess and to offer the store contacts. |
| Ambiguous or unknown product | Candidates or closest names are returned so the agent can ask. |
| Order not found or contact does not match | Same neutral message in both cases, for privacy. |
| Tool-calling loop | Stopped after a configurable number of steps with a polite reply. |
| Provider errors (network, quota, temporary unavailability) | Automatic retries; then a short message while the conversation stays open, or HTTP 503 in the API. |
| Free tier rate limit | Avoided by the client-side limiter, which queues the calls. |
| Empty or excessively long message | Rejected before reaching the model (HTTP 422 in the API). |
| Corrupted ticket file | `emporio tickets` reports the broken line instead of crashing. |
| Ctrl+C or end of input | The chat closes cleanly and the conversation stays saved. |
