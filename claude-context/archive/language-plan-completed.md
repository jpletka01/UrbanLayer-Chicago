# Multi-Language Support (i18n) — Implementation Plan

## Context

UrbanLayer currently operates entirely in English. To serve Chicago's multilingual population (Spanish, Polish, Chinese communities are among the city's largest), we're adding support for 5 languages: English (default), Spanish, Polish, Simplified Chinese, and Traditional Chinese.

**Core design principle**: Backend stays English-only — database, Qdrant vector index, and city API payloads are never translated. Translation happens at two boundaries: (1) the LLM synthesizer outputs in the user's language, and (2) the React frontend localizes static UI strings.

This avoids duplicating the entire retrieval layer per language while giving users a fully localized experience.

---

## Architecture Overview

```
User (Spanish) ──→ Frontend (localized UI) ──→ Backend
                                                  │
                                         ChatRequest.language = "es"
                                                  │
                                    ┌─────────────┴──────────────┐
                                    │  Conversation Synthesis     │
                                    │  (Haiku — rewrite to EN)   │
                                    └─────────────┬──────────────┘
                                                  │ English query
                                    ┌─────────────┴──────────────┐
                                    │  Router (Sonnet)            │
                                    │  (search_query always EN)   │
                                    └─────────────┬──────────────┘
                                                  │ RetrievalPlan
                                    ┌─────────────┴──────────────┐
                                    │  Retrieval (all English)    │
                                    │  Socrata + Qdrant + ArcGIS │
                                    └─────────────┬──────────────┘
                                                  │ ContextObject (EN)
                                    ┌─────────────┴──────────────┐
                                    │  Synthesizer (Sonnet)       │
                                    │  System prompt += language  │
                                    │  instruction → streams in   │
                                    │  target language             │
                                    └─────────────┬──────────────┘
                                                  │ Spanish response
                                         ◄────────┘
```

**Key insight**: No explicit pre-translation step is needed. Claude Sonnet natively understands all 5 target languages. The router will correctly parse "Que esta pasando en Logan Square?" into the right RetrievalPlan. The `search_query` output is already English because the system prompt requests JSON with English field values. We just need to add an explicit instruction to the router prompt to reinforce this for edge cases, and tell the synthesizer to output in the target language.

---

## Phase 1: Backend — Language Plumbing

### 1.1 ChatRequest model (`backend/models.py:433`)

Add `language` field with validation:

```python
class ChatRequest(BaseModel):
    message: str = Field(max_length=2000)
    history: list[Message] = Field(default_factory=list, max_length=20)
    conversation_id: str | None = None
    upload_ids: list[str] = Field(default_factory=list)
    language: Literal["en", "es", "pl", "zh-CN", "zh-TW"] = "en"
```

### 1.2 Settings (`backend/config.py`)

Add translation model config:

```python
translation_model: str = "claude-haiku-4-5-20251001"
translation_max_tokens: int = 2000
supported_languages: list[str] = ["en", "es", "pl", "zh-CN", "zh-TW"]
```

### 1.3 Database migration — schema v7 (`backend/db.py`)

Add `language` column to `conversations` table:

```sql
ALTER TABLE conversations ADD COLUMN language TEXT NOT NULL DEFAULT 'en'
```

- Bump `_SCHEMA_VERSION` to 7
- Add `_migrate_v7(db)` function, add the `if version < 7` block in `init_db()`
- Update `create_conversation()` to accept and store `language` parameter
- Update `list_conversations()` and `get_conversation()` to return `language`
- Add `language TEXT` column to `request_logs` table for analytics

### 1.4 Thread language through SSE pipeline (`backend/main.py:818-980`)

In `_event_stream()`:
- Extract `req.language` at the top of the function
- Pass `language=req.language` to `synthesize_query()` (line 851)
- Pass `language=req.language` to `stream_answer()` (line 937)
- Pass `language` to `_save_request_log()` (lines 862, 880, 890, 908, 976)

In conversation creation endpoint (line 332-338):
- Accept `language` field from the POST body
- Pass to `db.create_conversation()`

In get conversation endpoint (line 341-348):
- Return `language` field so frontend can restore the setting when loading a conversation

---

## Phase 2: Backend — Prompt & Synthesis Changes

### 2.1 Conversation synthesis (`backend/conversation.py:146`)

Update `synthesize_query()` to accept `language: str = "en"`:

- When `language != "en"` and there is history, **always force synthesis** (bypass `needs_synthesis()` heuristic). Reason: the English-based heuristics (pronoun detection, follow-up patterns) won't match non-English text reliably.
- Append to the `CONVERSATION_SYNTHESIS` system prompt: `"The user may write in a non-English language. Always rewrite the synthesized query in English, regardless of the user's input language."`
- First messages (no history) still skip synthesis regardless of language, matching current behavior.

### 2.2 Router prompt (`backend/prompts.py:8-64`)

Add one rule to `ROUTER_SYSTEM_TEMPLATE`:

```
- The user's query may be in any language. Parse it normally. Always write search_query in English regardless of the input language.
```

No changes to `router.py` — Claude Sonnet handles multilingual input natively.

### 2.3 Synthesizer language instruction (`backend/synthesizer.py`)

Add a language map and instruction template:

```python
LANGUAGE_NAMES = {
    "es": "Spanish", "pl": "Polish",
    "zh-CN": "Simplified Chinese", "zh-TW": "Traditional Chinese",
}

LANGUAGE_INSTRUCTION = """
IMPORTANT: Respond entirely in {language_name}.
Translate all prose, headers, and explanations into {language_name}.
You MUST preserve these elements exactly as-is (do NOT translate them):
- Citation markers: [1], [2], [3], etc.
- Data source markers: [data:crime], [data:311], [data:permits], [data:violations], [data:business], [data:vacant_buildings], [data:food_inspections]
- Proper nouns: Chicago neighborhood names, street names, park names
- Official program names: TIF, ARO, SBIF, TOD, SSA, PMD, etc.
- Legal section numbers: § 17-2-0207, etc.
- PIN numbers, zone codes (B1-2, RT-4, etc.), and URLs
- Statistical values, currency amounts, dates
"""
```

Update `stream_answer()` signature to accept `language: str = "en"`.

When `language != "en"`, use `SYNTHESIZER_SYSTEM + LANGUAGE_INSTRUCTION.format(...)` as the system prompt. The existing `_enable_prompt_caching()` in `llm.py` will create separate cache entries per language — this is fine since English (the majority of traffic) is unaffected.

### 2.4 Clarification translation (`backend/main.py:887-893`)

When `plan.intent == "clarification_needed"` and `language != "en"`, the clarification text from the router is in English. Use the translation endpoint (Phase 3) to translate it before emitting:

```python
if plan.intent == "clarification_needed" and plan.clarification:
    text = plan.clarification
    if req.language != "en":
        text = await translate_text(text, req.language, request_group)
    yield _sse(ChatChunk(type="token", text=text, ...))
```

---

## Phase 3: Backend — Translation Endpoint

### 3.1 New module (`backend/translate.py`)

```python
async def translate_text(text: str, target_language: str, request_group: str = "") -> str:
```

- Uses Haiku via `tracked_create()` with system prompt: "Translate the following text into {language_name}. Preserve all legal references, section numbers (§), formatting, and proper nouns. Return only the translated text."
- Cache layer: `TTLCache(ttl_seconds=86400, maxsize=4096, name="translation")` keyed by `sha256(text + target_language)`
- Used for: (1) on-demand source chunk translation from the frontend, (2) clarification message translation

### 3.2 API endpoint (`backend/main.py`)

```python
class TranslateRequest(BaseModel):
    text: str = Field(max_length=10000)
    target_language: Literal["es", "pl", "zh-CN", "zh-TW"]

@app.post("/api/translate")
async def translate_endpoint(req: TranslateRequest, ...) -> dict:
    translated = await translate_text(req.text, req.target_language, ...)
    return {"translated": translated, "language": req.target_language}
```

Rate-limit with existing `check_rate_limit()`.

---

## Phase 4: Frontend — i18n Infrastructure

### 4.1 Install dependencies

```bash
npm install i18next react-i18next
```

No `i18next-http-backend` — all translations bundled at build time for instant locale switching.

### 4.2 Locale file structure

```
frontend/src/locales/
  en/
    common.json      # Nav, buttons, errors, labels
    chat.json        # Chat UI, activity labels, placeholders
    sidebar.json     # Data card headers, source labels
    landing.json     # Splash page copy, suggestions
  es/
    common.json
    chat.json
    sidebar.json
    landing.json
  pl/
    ...
  zh-CN/
    ...
  zh-TW/
    ...
```

Key namespaces:
- **common**: `nav.history`, `nav.newChat`, `actions.copy`, `actions.copied`, `errors.connectionLost`, `errors.messageLimitReached`, `language.en`, `language.es`, etc.
- **chat**: `placeholder` ("Ask about Chicago..."), `activities.analyzing`, `activities.located` (with `{{area}}` interpolation), `sourceLabels.crime_api`, etc.
- **sidebar**: `tabs.data`, `tabs.sources`, `tabs.map`, `sections.property`, `sections.violations`, etc.
- **landing**: `hero.subtitle`, `suggestions[]`, `stats.dataSources`, `stats.codeSections`, etc.

### 4.3 Initialize i18n (`frontend/src/lib/i18n.ts`)

```typescript
import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
// import all locale JSON files

i18n.use(initReactI18next).init({
  resources: { en: { ... }, es: { ... }, pl: { ... }, "zh-CN": { ... }, "zh-TW": { ... } },
  lng: localStorage.getItem("urbanlayer-language") || "en",
  fallbackLng: "en",
  interpolation: { escapeValue: false },
  ns: ["common", "chat", "sidebar", "landing"],
  defaultNS: "common",
});
```

Import as side-effect in `main.tsx`.

### 4.4 LanguageSelector component

New file: `frontend/src/components/LanguageSelector.tsx`

- Globe icon button that opens a dropdown with 5 options (English, Espanol, Polski, 简体中文, 繁體中文)
- On selection: `i18n.changeLanguage(code)` + `localStorage.setItem("urbanlayer-language", code)`
- Placed in the header bar (right side, between share/export and user menu)
- Also shown on the splash/landing page header

### 4.5 Thread language to chat API

**`frontend/src/lib/api.ts`**:
- Add `language?: string` param to `chatStream()`
- Include in POST body: `if (language && language !== "en") body.language = language;`
- Add `translateText(text: string, targetLanguage: string): Promise<string>` calling `POST /api/translate`

**`frontend/src/lib/useChat.ts`**:
- Accept `language?: string` in `UseChatOptions`
- Pass through to `chatStream()`
- Replace `SOURCE_LABELS` with `t()` calls from `useTranslation("chat")`

**`frontend/src/App.tsx`**:
- Get current language from `useTranslation()` hook: `const { i18n } = useTranslation()`
- Pass `language: i18n.language` to `useChat()`

### 4.6 String extraction (~90+ strings across ~25 files)

Replace hardcoded English strings with `t("namespace:key")` calls. Priority order:
1. ChatInput — placeholder
2. useChat.ts — SOURCE_LABELS, activity messages, errors
3. HistorySidebar — "History", "No conversations yet", date labels
4. MessageBubble — "Copy message"
5. SourceDetailDrawer — "Municipal Code", "Loading section..."
6. SidebarHeader — tab labels "Data", "Sources", "Map"
7. DataView — section headers "Property", "Violations", etc.
8. ShareModal, ExportReport
9. Landing page components (can be deferred to a follow-up)

---

## Phase 5: Source Translation UI

### 5.1 SourceDetailDrawer (`frontend/src/components/SourceDetailDrawer.tsx`)

When `language !== "en"`:
- Show a "Translate" button next to the "Copy full text" button in the header
- On click: call `translateText(chunk.text, language)` from api.ts
- Show loading spinner during translation
- Display translated text (toggle between original/translated with a button)
- Cache translation in component state by section ID to avoid re-translating

### 5.2 SourceCitation (`frontend/src/components/SourceCitation.tsx`)

When expanded and `language !== "en"`:
- Small translate icon button in the expanded content area
- Same translate/toggle/cache pattern

---

## Phase 6: Term Definitions

**File**: `frontend/src/lib/termDefinitions.ts` (~300 entries: 256 zones + overlays + incentives + flood zones)

**Strategy**: Create separate JSON files per language, not inline i18next keys (these are domain-specific terms requiring curated translations).

```
frontend/src/locales/
  en/terms.json     # Extracted from current termDefinitions.ts
  es/terms.json     # Translated
  pl/terms.json
  zh-CN/terms.json
  zh-TW/terms.json
```

Update `getTermInfo(key)` to accept a `language` parameter and load from the appropriate file. `InfoTooltip` passes current language from `useTranslation()`.

**Initial release**: English definitions serve as fallback for all languages. Translated term files can be filled incrementally — the tooltip just shows English when a translation isn't available yet. Zone codes (`R1`, `B3-2`, `DX-5`) are universal and don't need translation; only the `description` and `bullets` fields do.

---

## Phase 7: Conversation Language Persistence

- Language is stored per conversation in the DB (Phase 1.3)
- When creating a new conversation, store the current global language preference
- When loading a conversation from history, restore the stored language (`i18n.changeLanguage(conv.language)`)
- **Language is locked per conversation** — switching the global language applies to the *next* new conversation, not the current one. This avoids mixed-language history confusion.

---

## Latency Impact

| Path | Added Latency | Notes |
|------|--------------|-------|
| English (default) | **+0ms** | No changes to any LLM call or prompt |
| Non-English, first message | **+0ms** | No conversation synthesis needed (no history) |
| Non-English, follow-up | **+300-600ms** | Forced conversation synthesis via Haiku (bypasses English heuristics) |
| Non-English, synthesis | **+100-300ms** | Language instruction adds ~100 tokens to system prompt; non-Latin tokenization ~10-20% slower |
| On-demand source translation | **+800-1500ms** | User-initiated, cached, does not block chat |

**Total per-query overhead**: ~200-600ms for non-English follow-ups, ~100-300ms for first messages. Typical queries go from 3-8s to 3.5-8.5s. Well within acceptable bounds.

**Prompt caching**: The synthesizer system prompt creates separate cache entries per language. English cache (majority of traffic) is completely unaffected. Non-English caches warm up quickly with even modest usage.

---

## Testing Plan

### Backend
- **Unit**: `ChatRequest` validates language field; invalid codes rejected
- **Unit**: Synthesizer system prompt includes language instruction when `language != "en"`, unchanged for `language == "en"`
- **Unit**: Conversation synthesis forced for non-English when history exists
- **Unit**: Translation endpoint caches by content hash, respects rate limits
- **Integration**: Spanish query → router produces valid RetrievalPlan with English `search_query`
- **Migration**: Schema v7 adds `language` column; existing conversations default to `"en"`

### Frontend
- **Type check**: `npx tsc --noEmit` passes with new language types
- **Manual**: Language selector switches UI strings in real-time
- **Manual**: Chat in Spanish → response streams in Spanish with preserved `[N]` and `[data:*]` markers
- **Manual**: Source "Translate" button works, caches result, toggles original/translated

### Eval
- Add multilingual test cases to `eval/` suite
- Test citation marker preservation in non-English output (critical regression risk)
- Test `[data:*]` marker preservation in non-English output

---

## Risks & Mitigations

1. **Citation marker corruption** — Synthesizer might translate `[data:crime]` or `[1]`. Mitigation: explicit preservation instructions in LANGUAGE_INSTRUCTION + eval test cases to catch regression.

2. **Chinese tokenization cost** — Chinese text uses ~15-25% more tokens. Mitigation: monitor via admin dashboard; absolute cost is still small (~$0.01/query).

3. **Conversation synthesis false negatives** — English-based `needs_synthesis()` heuristics won't match non-English pronouns/patterns. Mitigation: force synthesis for all non-English follow-ups (bypass heuristic entirely when `language != "en"` and history exists).

4. **Term definition translation quality** — Zoning/TIF/ARO are Chicago-specific. Mitigation: keep official program names in English per LANGUAGE_INSTRUCTION; curate term translations over time.

5. **Suggestion prompts** — Landing page suggestions ("What's going on near 2400 N Milwaukee Ave?") should be localized to actual translated questions since users send them verbatim. The backend handles multilingual input, so Spanish suggestions work naturally.

---

## Files Modified (Summary)

### Backend (8 files)
- `backend/models.py` — Add `language` to `ChatRequest`, add `TranslateRequest`
- `backend/config.py` — Add `translation_model`, `translation_max_tokens`, `supported_languages`
- `backend/db.py` — Schema v7 migration, `language` column in conversations + request_logs
- `backend/main.py` — Thread language through `_event_stream()`, add `POST /api/translate`, update conversation endpoints
- `backend/prompts.py` — Add multilingual rule to ROUTER_SYSTEM_TEMPLATE
- `backend/synthesizer.py` — Add LANGUAGE_INSTRUCTION, accept `language` param
- `backend/conversation.py` — Accept `language` param, force synthesis for non-English
- `backend/translate.py` — **New file**: `translate_text()` with TTLCache

### Frontend (new files: 3, modified: ~25)
- `frontend/src/lib/i18n.ts` — **New**: i18next initialization
- `frontend/src/components/LanguageSelector.tsx` — **New**: language dropdown
- `frontend/src/locales/**/*.json` — **New**: 5 languages x 4-5 namespaces
- `frontend/src/lib/api.ts` — Add `language` to chatStream, add `translateText()`
- `frontend/src/lib/useChat.ts` — Thread language, localize SOURCE_LABELS
- `frontend/src/App.tsx` — LanguageSelector in header, thread language to useChat
- `frontend/src/components/SourceDetailDrawer.tsx` — Translate button
- `frontend/src/components/SourceCitation.tsx` — Translate button
- `frontend/src/lib/termDefinitions.ts` — Language-aware term lookup
- ~20 other components — Replace hardcoded strings with `t()` calls
