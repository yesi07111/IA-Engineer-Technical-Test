# 9. Limitations and Roadmap

## 9.1 Known limitations

- Holidays and special opening hours are not modelled.
- BM25 is lexical, so synonyms that do not appear in the manual may miss the relevant section.
- Return deadlines rely on the estimated delivery date, because the real date is not recorded.
- Shipping costs can not be calculated: postal code, weight and dimensions are not in the data.
- The agent does not place orders, take payments or approve returns. It explains the rules and opens a ticket.
- Conversation history grows without limit within a session.
- The Gemini free tier (20 requests per day per project) suits evaluation, not production traffic.
- The web chat has no authentication.

## 9.2 Recommended next steps

| Priority | Item |
|---|---|
| High | WhatsApp integration, the store's main channel, reusing the existing chat session. |
| High | A PostgreSQL database with live stock behind the existing repository interfaces, and a ticket workflow with status and assignee. |
| Medium | A larger evaluation set with an LLM-as-judge for tone, run on a schedule in CI. |
| Medium | Hybrid retrieval (BM25 plus embeddings) for the policy manual. |
| Medium | Observability with LangSmith or OpenTelemetry: traces, latency and cost per conversation. |
| Low | Conversation summarization for long sessions, a holiday calendar, a container image and API authentication. |
