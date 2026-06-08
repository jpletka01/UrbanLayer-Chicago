# Design Guidelines — UrbanLayer

## The Hybrid Model: Dashboard + Chat

The chat and the structured dashboard must not feel like two separate features (the "conjoined twins" problem). They must behave as a single coordinated system.

### Dashboard → Chat ("Investigate" Buttons)
- Every data card, map point, and grid row should have a chat icon that pre-populates a contextual question.
- Example: User sees a zoning label `RT-4` on a property card. Clicking it opens the chat with: "What are the setbacks, height limits, and allowed uses for RT-4?"
- Example: User sees a contractor name on a permit row. Clicking "Investigate" opens: "What is [Contractor Name]'s permit history and violation rate in Chicago?"

### Chat → Dashboard ("Visual Commands")
- When the user asks a location-based question, the chat response should drive the map (zoom, draw boundaries, highlight points).
- When the user asks a comparison question, the frontend should split-screen two property cards side-by-side.
- The SSE stream already sends map payloads alongside text tokens — extend this pattern to drive dashboard state.

### Division of Labor
- **Dashboard & Map (The "What" and "Where"):** Fast, deterministic, structured facts. No LLM latency. No hallucination risk. Zero API cost.
- **Chat Copilot (The "Why" and "How"):** Legal interpretation, regulatory exceptions, cross-source synthesis, plain-English explanations of complex zoning rules.

## When to Use Chat vs Tools

| Use Case | Best Interface | Rationale |
|----------|---------------|-----------|
| Bulk prospecting / lead gen | Data grid with filters | Speed, export, deterministic results |
| Single-address due diligence | Structured dashboard (scorecard) | Instant load, no LLM cost |
| Zoning interpretation / legal questions | Chat (RAG over Municipal Code) | Requires reasoning over legal text |
| "Explain this data" follow-ups | Chat with dashboard context hand-off | AI excels at synthesis and explanation |
| Comparing two properties | Chat driving split-screen dashboard | Needs both structured data and narrative |
| Contractor background check | Chat with permit database queries | Requires cross-referencing multiple datasets |
| Monitoring / alerts | Automated email notifications | Async, no user interaction needed |

## UX Principles

1. **Speed over spectacle.** Power users will choose a 200ms database query over a 5-second LLM response every time for routine lookups. Reserve the LLM for tasks that genuinely require reasoning.
2. **Every data point should be actionable.** If a data card shows a zoning class, it should link to an explanation. If a permit row shows a contractor, it should link to their profile. Dead-end data is wasted screen space.
3. **Export everything.** Enterprise users expect CSV/PDF export on every data view. This is table stakes for B2B SaaS.
4. **The chat should feel like a colleague, not a chatbot.** It should reference the data the user is already looking at, not ask them to re-explain their context.
5. **Disclaimers are non-negotiable.** Every AI-generated zoning interpretation must carry a disclaimer that it is not legal advice. Every data point must cite its source and freshness date. In commercial real estate, a wrong answer can cost millions.
