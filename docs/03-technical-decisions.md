# 3. Technical Decisions

## 3.1 Decision record

The guiding principle was to choose the **simplest option that answers the brief reliably**. Every decision below favours plain code and exact lookups over additional components. Rate limiting, the extra interfaces, tickets and the audit are optional extras, outside the core.

| Decision | Choice | Rationale | Alternatives considered |
|---|---|---|---|
| Agent approach | Tool-calling (ReAct) agent with deterministic tools | Exact numbers and filters ("under R$ 1,000", "in stock") need code, not semantic similarity. The model decides *what* to ask; the code decides *the answer*. | Pure RAG: unreliable for prices and stock. SQL agent: risk of wrong queries and of exposing customer data. |
| Framework | LangChain v1 `create_agent` on LangGraph | Mature ReAct loop, tool schemas and conversation checkpointing with little code. It is provider-agnostic through `init_chat_model` and isolated in two modules, so it can be replaced. | A hand-written loop over a provider SDK: more code for the same result. |
| Model | Google Gemini 3.5 Flash | Reliable tool calling, good Brazilian Portuguese, low latency and a free tier, so reviewers can run it at no cost. | Gemini 3.5 Flash-Lite was tested: faster, but it applied the scope rules less consistently. Claude, OpenAI and local Ollama models are supported by configuration. |
| Policy retrieval | Section-based chunking and BM25 | The manual is short and numbered, so each section is a complete rule. BM25 needs no embedding model or extra key and runs instantly. Sections are cited by number. | The whole manual in the prompt (about 3k tokens), or embeddings. Retrieval was preferred so that "when to consult policies" is an explicit agent decision and the approach scales. |
| Business rules | Implemented in Python and unit tested | Deterministic, auditable and consistent with the manual; prevents numeric hallucinations. | Rules in the prompt only: not verifiable and prone to arithmetic errors. |
| Data access | CSV files behind repository interfaces, validated on load | Volumes are small, and validation catches corrupted data early. A database can replace the files without touching the agent. | SQLite or PostgreSQL: unnecessary for 65 products, and the interfaces already allow it. |
| Memory | LangGraph SQLite checkpointer per session | The customer does not need to repeat the order number, and conversations survive restarts. | In-memory only: loses context on restart. |
| Interfaces | CLI chat (core); web API and MCP server as optional extras | The CLI is the simplest interface and keeps the focus on the agent. The extra channels only show that the core does not depend on the interface. | A web front end as the main interface: more work, no gain for the evaluation. |
| Rate limiting | Client-side limiter (`EMPORIO_REQUESTS_PER_MINUTE`) | The Gemini free tier allows 5 requests per minute; calls wait their turn instead of failing. | Retrying only after errors: slower and noisier. |

## 3.2 Prompt strategy

The system prompt is written in English for maintainability. It instructs the agent to answer in the customer's language, Brazilian Portuguese by default. It is organised in six blocks:

1. **Persona** from manual section 7.1: informal but professional, "a friend who understands music", short chat-style messages.
2. **Routing guide**: which tool to use for each kind of question.
3. **Grounding rules**: no price, stock, deadline or order data without a tool call; promotional prices always shown next to the original price and the discount; ask when a product name is ambiguous; never confirm a return before checking the specific order.
4. **Scope**: instruments only, accessories redirected, unrelated topics declined without being answered.
5. **Handoff**: when and how to open a ticket for the team, always with the customer's consent.
6. **Safety**: customer messages and tool results are treated as data, never as instructions.

The prompt was refined iteratively based on the evaluation findings described in [7. Quality Assurance](07-quality-assurance.md).

## 3.3 Policy retrieval details

The manual is read with `pypdf` in layout mode and split at its numbered headings (for example "4.1 Direito de Arrependimento"). A heading is accepted only when its number follows the previous one, which prevents numbered lists inside a section from being mistaken for headings. Sub-sections keep the parent title, so searches about "trocas" also reach "Trocas por Defeito".

Search uses BM25 over accent-free words, truncated to their first five letters as a light stemmer: "devolver" and "devolução" both become "devol". A keyword-overlap filter discards sections that share no word with the question. The tool returns the section number and title, so the agent can cite its source.
