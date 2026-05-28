# Chicago City Intelligence — Claude Code Project Prompt

## Project Overview

Build a **RAG-powered chat interface** that lets users ask natural language questions about the city of Chicago. The system combines live data from the Chicago Data Portal (via Socrata API) with semantic search over embedded municipal documents (zoning codes, city ordinances) to answer questions about public safety, neighborhood conditions, building activity, 311 complaints, and local regulations.

The killer use case is a unified address query: a user types something like _"What's going on near 2400 N Milwaukee Ave?"_ and receives a synthesized response covering recent crime patterns, open 311 service requests, active building permits, and the applicable zoning code — all from a single prompt.

---

## Tech Stack

### Backend
- **Language:** Python
- **Framework:** FastAPI
- **LLM:** Anthropic Claude API (claude-sonnet-4-20250514)
- **Vector DB:** Qdrant (self-hosted via Docker for local dev; Qdrant Cloud free tier for live demo deployment)
- **Embeddings:** OpenAI `text-embedding-3-small` or a local model via `sentence-transformers`
- **Async HTTP:** `aiohttp` for parallel Socrata API calls
- **Env management:** `python-dotenv`

### Frontend
- **Framework:** React (Vite)
- **Styling:** Tailwind CSS
- **Chat UI:** Custom component — no off-the-shelf chat library
- **Map (optional, stretch goal):** Leaflet.js or Mapbox GL for visualizing geographic results

### Infrastructure
- **Containerization:** Docker + Docker Compose (one service each for: FastAPI backend, Qdrant, optional Postgres)
- **Document pipeline:** Standalone Python scripts (not part of the API server) for ingesting and embedding municipal documents

---

## Architecture: Three-Layer RAG Pipeline

### Layer 1 — Live Structured Data (Socrata API)
Real-time queries to the Chicago Data Portal using SoQL. No embeddings — results are fetched at query time and injected directly into the LLM context.

### Layer 2 — Static Document Embeddings (Qdrant Vector Search)
Chicago Municipal Code and zoning ordinances are chunked, embedded, and stored in Qdrant. Retrieved via semantic similarity search at query time.

### Layer 3 — LLM Router + Synthesizer (Claude)
An LLM-based router parses the user message, produces a retrieval plan, and dispatches parallel queries to Layers 1 and 2. A second LLM call synthesizes all retrieved context into a final response.

---

## Data Sources

### Priority Socrata Datasets (Chicago Data Portal)

All datasets are accessed via the Socrata REST API at `https://data.cityofchicago.org/resource/{dataset_id}.json` using SoQL query parameters.

**1. Crimes — 2001 to Present**
- Dataset ID: `ijzp-q8t2`
- Key fields: `date`, `primary_type`, `description`, `location_description`, `arrest` (bool), `domestic` (bool), `beat`, `district`, `ward`, `community_area`, `latitude`, `longitude`, `iucr`, `fbi_code`
- Update cadence: Daily (excludes most recent 7 days — always surface this lag to users)
- Primary use: Crime trend queries, neighborhood safety assessments, address-level incident lookups
- Notes: Join with IUCR lookup table (`c7ck-438e`) to translate 4-digit codes to plain English. Use `community_area` (integer 1–77) for neighborhood aggregations. `primary_type` has ~35 categories; map user language like "violent crime" to relevant types (HOMICIDE, ASSAULT, BATTERY, ROBBERY, CRIMINAL SEXUAL ASSAULT) in the router.

**2. 311 Service Requests**
- Dataset ID: `v6vf-nfxy`
- Key fields: `sr_number`, `sr_type` (107 distinct types), `owner_department`, `status` (Open / Closed / Canceled / Open - Dup), `created_date`, `closed_date`, `street_address`, `ward`, `community_area`, `police_district`, `latitude`, `longitude`
- Update cadence: Near real-time
- Primary use: Neighborhood quality-of-life queries, response time analysis, open issue lookups
- Notes: Filter out `Open - Dup` records before aggregating counts. The `created_date` → `closed_date` delta gives city response time — a useful derived metric. Group `sr_type` values by `owner_department` for cleaner LLM reasoning. Notable SR types: `Noise - Residential`, `Rodent Baiting/Rat Complaint`, `Pothole in Street`, `Abandoned Vehicle`, `Graffiti Removal`, `Building Violation`.

**3. Building Permits**
- Dataset ID: `ydr8-5enu`
- Key fields: `permit_`, `permit_type`, `work_description`, `application_start_date`, `issue_date`, `street_number`, `street_direction`, `street_name`, `community_area`, `latitude`, `longitude`, `estimated_cost`
- Primary use: Property development queries, neighborhood construction activity

**4. Building Violations**
- Dataset ID: `22u3-xenr`
- Key fields: `violation_date`, `violation_description`, `violation_status`, `property_group`, `street_number`, `street_name`, `community_area`, `latitude`, `longitude`
- Primary use: Landlord accountability, property condition queries
- Notes: Cross-reference with the Building Code Scofflaw List for high-value queries ("is my landlord on the scofflaw list?")

**5. Business Licenses — Current Active**
- Dataset ID: `uupf-x98q`
- Key fields: `legal_name`, `doing_business_as_name`, `license_description`, `business_activity`, `address`, `ward`, `community_area`, `latitude`, `longitude`, `expiration_date`
- Primary use: Neighborhood character queries, restaurant/bar lookups, business verification

**Supporting / Geographic Datasets**
- Community Area Boundaries: `igwz-8jzy` — maps integer (1–77) to name (e.g. 24 = "West Town")
- Ward Boundaries (2023–): `sp34-6z76`
- Zoning Districts (current): `p8va-airx` — spatial join to resolve address → zoning classification
- IUCR Codes: `c7ck-438e` — lookup table for crime code translation

---

## The Router

The router is an LLM call (Claude) that runs before any retrieval. It receives the raw user message and returns a structured retrieval plan as JSON.

### Router Output Schema
```json
{
  "sources": ["crime_api", "311_api", "vector_search"],
  "location": {
    "raw": "Milwaukee and North",
    "type": "intersection | address | neighborhood | community_area | none",
    "resolved_community_area": 24,
    "resolved_address": "2400 N Milwaukee Ave"
  },
  "intent": "neighborhood_overview | incident_lookup | legal_question | event_query | trend_analysis",
  "time_range_days": 90,
  "requires_disclaimer": true
}
```

### Router Behavior Rules
- `requires_disclaimer: true` whenever `sources` includes `vector_search` AND `intent` is `legal_question` — zoning and code responses must carry a "consult a professional" disclaimer
- Location resolution is critical: neighborhood names like "Wicker Park" or "Logan Square" must be mapped to their `community_area` integer before API calls. Embed a static lookup table of all 77 community area names → integers in the router's system prompt.
- If no location is present and the query requires one, the router should set `location.type = "none"` and the system should ask the user for clarification rather than guessing.
- Router is iterative-capable: after initial retrieval, it can issue a follow-up retrieval plan if the first results are insufficient (agentic loop, 2 iterations max to control latency).

---

## Parallel Retrieval

After the router produces a plan, all source queries fire simultaneously using `asyncio.gather()`.

### SoQL Query Patterns

**Crime — aggregated by type (neighborhood-level)**
```
GET /resource/ijzp-q8t2.json
  ?$where=community_area='{ca}' AND date > '{date_90d_ago}'
  &$group=primary_type
  &$select=primary_type,count(*) as count,sum(case(arrest='true',1,0)) as arrests
  &$order=count DESC
  &$limit=10
```

**Crime — recent incidents (address/block-level)**
```
GET /resource/ijzp-q8t2.json
  ?$where=block='{block}' AND date > '{date_30d_ago}'
  &$order=date DESC
  &$limit=20
```

**311 — open requests by neighborhood**
```
GET /resource/v6vf-nfxy.json
  ?$where=community_area='{ca}' AND status='Open'
  &$group=owner_department,sr_type
  &$select=owner_department,sr_type,count(*) as count
  &$order=count DESC
  &$limit=15
  &$having=sr_type != 'Open - Dup'
```

**311 — response time (closed requests)**
```
GET /resource/v6vf-nfxy.json
  ?$where=community_area='{ca}' AND status='Closed'
    AND created_date > '{date_90d_ago}'
  &$select=sr_type,avg(date_diff_d(closed_date,created_date)) as avg_days
  &$group=sr_type
  &$order=avg_days DESC
  &$limit=10
```

---

## Context Assembler

The context assembler merges all retrieval results into a single structured JSON object before the LLM synthesis call. This function should be built and unit-tested independently of the LLM layer.

### Output Shape
```json
{
  "community_area": 24,
  "community_area_name": "West Town",
  "data_as_of": "2025-05-20",
  "data_lag_note": "Crime data excludes the most recent 7 days.",
  "crime_last_90d": {
    "total": 143,
    "arrest_rate": 0.18,
    "by_type": {
      "THEFT": 61,
      "BATTERY": 28,
      "CRIMINAL DAMAGE": 19,
      "ASSAULT": 14,
      "NARCOTICS": 11
    }
  },
  "open_311_requests": {
    "total": 37,
    "oldest_open_days": 94,
    "by_department": {
      "Streets & Sanitation": 19,
      "CDOT": 11,
      "Buildings": 7
    },
    "top_types": ["Pothole in Street", "Rodent Baiting/Rat Complaint", "Graffiti Removal"]
  },
  "code_chunks": [
    {
      "text": "...",
      "source_document": "Chicago Municipal Code",
      "section": "17-2-0100",
      "section_title": "Residential districts — permitted uses",
      "score": 0.91
    }
  ]
}
```

### Assembler Rules
- Cap `by_type` crime breakdown to top 5 to control context window size
- Filter `Open - Dup` from 311 counts before aggregating
- Always include `data_lag_note` when crime data is present
- Cap `code_chunks` to top 5 by relevance score
- Each chunk must carry its `section` and `section_title` metadata — this is what gets cited in the response

---

## Vector Search (Qdrant) — Document Ingestion Pipeline

This is a separate offline pipeline, not part of the API server. Run it once to populate Qdrant, and re-run when source documents update.

### Document Sources (to be located and downloaded)
- **Chicago Municipal Code:** Available at `https://library.municode.com/il/chicago` — large structured document, ~4,000+ sections
- **Chicago Zoning Ordinance:** Title 17 of the Municipal Code — the most relevant section for land use queries
- **Aldermanic Zoning Amendment Summaries:** Available via the City Clerk's Legistar portal

### Chunking Strategy — Critical Design Decision
Do **not** chunk by character count. The municipal code uses a hierarchical section structure that must be preserved:

```
Title 17 (Zoning)
  → Chapter 17-2 (Residential Districts)
    → Section 17-2-0100 (Permitted Uses)
      → Subsection (a), (b), (c)...
```

Chunk at the **subsection level**. Each chunk = one subsection, never split across subsections. If a subsection is very long (>800 tokens), split at paragraph boundaries within it, and duplicate the section header in each sub-chunk.

### Metadata Schema (per chunk — stored in Qdrant payload)
```json
{
  "source_document": "Chicago Municipal Code",
  "title_number": 17,
  "title_name": "Zoning",
  "chapter": "17-2",
  "section": "17-2-0100",
  "section_title": "Residential districts — permitted uses",
  "subsection": "a",
  "effective_date": "2024-01-01",
  "cross_references": ["17-2-0200", "17-9-0100"],
  "text": "..."
}
```

### Cross-Reference Handling
The municipal code frequently references other sections ("see Section 17-9-0100 for exceptions"). When a retrieved chunk contains cross-references, the assembler should attempt to fetch those referenced sections from Qdrant by section ID (exact match, not semantic search) and include them as secondary context. This prevents the LLM from missing critical qualifications or exceptions.

### Qdrant Collection Setup
```python
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

client = QdrantClient("localhost", port=6333)
client.create_collection(
    collection_name="chicago_municipal_code",
    vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
)
# Also create a separate collection for zoning if you want independent filtering:
client.create_collection(
    collection_name="chicago_zoning",
    vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
)
```

---

## LLM Synthesis Prompt Structure

### System Prompt
```
You are a Chicago city information assistant. You have access to real-time city data and official municipal documents. Your job is to answer questions about Chicago clearly and accurately.

Rules:
1. Always cite your sources. For API data, cite the dataset name and date range. For document chunks, cite the section number and title.
2. Always surface data freshness. If crime data is present, note the 7-day lag.
3. For any question that touches on legal rights, zoning compliance, permit requirements, or ordinance interpretation, add this disclaimer: "This information is based on official city documents but does not constitute legal advice. Please consult a licensed attorney or contact the relevant city department for official guidance."
4. Never fabricate statistics. If the data doesn't answer the question, say so.
5. Be concise. Lead with the direct answer, then supporting detail.
```

### User Prompt Template
```
Context data (retrieved from Chicago city databases):
{context_object_as_json}

User question: {user_message}

Answer the question using only the context data above. Cite sources inline.
```

---

## Response Format

Responses to the user should follow this structure:

1. **Direct answer** — 1–3 sentences answering the question
2. **Supporting data** — key stats, formatted as readable prose (not raw JSON)
3. **Source citations** — inline, e.g. "according to CPD crime data (last 90 days, excluding most recent 7 days)"
4. **Legal disclaimer** — appended automatically when `requires_disclaimer: true`
5. **Data freshness note** — when crime data is included

---

## Project File Structure

```
chicago-rag/
├── backend/
│   ├── main.py                  # FastAPI app, /chat endpoint
│   ├── router.py                # LLM router — parses user message → retrieval plan
│   ├── retrieval/
│   │   ├── crime.py             # Socrata crime API queries (async)
│   │   ├── three11.py           # Socrata 311 API queries (async)
│   │   ├── buildings.py         # Socrata building permits/violations (async)
│   │   ├── vector_search.py     # Qdrant semantic search
│   │   └── geo.py               # Address → community_area resolution helpers
│   ├── assembler.py             # Context assembler — merges all retrieval results
│   ├── synthesizer.py           # LLM synthesis call — builds final response
│   ├── models.py                # Pydantic models for all request/response shapes
│   └── config.py                # Env vars, API keys, dataset IDs
│
├── ingestion/
│   ├── download_docs.py         # Script to fetch/download municipal PDFs
│   ├── chunk.py                 # Section-aware chunking logic
│   ├── embed_and_store.py       # Embed chunks and upsert into Qdrant
│   └── data/                    # Raw downloaded documents (gitignored)
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── ChatInterface.jsx
│   │   │   ├── MessageBubble.jsx
│   │   │   ├── SourceCitation.jsx
│   │   │   └── DisclaimerBanner.jsx
│   │   ├── App.jsx
│   │   └── main.jsx
│   └── ...
│
├── docker-compose.yml           # FastAPI + Qdrant services
├── .env.example
└── README.md
```

---

## Build Order (Recommended Sequence)

Build in this order so each layer is testable before the next depends on it:

1. **Qdrant setup** — Docker Compose, confirm connection, create collections
2. **Ingestion pipeline** — download, chunk, embed, store a small slice of the municipal code first (just Title 17, Chapter 17-2) to validate the pipeline end-to-end
3. **Socrata API wrappers** — `crime.py`, `three11.py` as standalone async functions with hardcoded test inputs, confirm real data returns
4. **Geo resolution helpers** — `geo.py`, load community area lookup table, confirm address → community_area mapping works
5. **Context assembler** — unit test with mock API responses, confirm JSON shape is correct before any LLM involvement
6. **LLM router** — prompt engineer and test with 10–15 representative user messages, confirm retrieval plans are accurate
7. **LLM synthesizer** — test with manually assembled context objects, tune system prompt
8. **FastAPI `/chat` endpoint** — wire all layers together
9. **React frontend** — build chat UI against the working API

---

## Key Design Decisions (Summary)

| Decision | Choice | Reason |
|---|---|---|
| Vector DB | Qdrant | Free self-hosted, good metadata filtering, cloud tier for demo |
| Chunking strategy | Section-aware (subsection level) | Legal cross-references break naive character chunking |
| Chunk metadata | Section ID, title, cross-refs, effective date | Enables citations and cross-reference resolution |
| API query execution | Parallel (`asyncio.gather`) | Crime + 311 + vector search are independent; no reason to serialize |
| Router type | LLM-based | Handles ambiguous location phrasing, intent classification, iterative retrieval |
| Context window management | Assembler caps: top-5 crime types, top-5 chunks, top-15 311 types | Prevents token overflow while preserving signal |
| Legal/zoning responses | Auto-disclaimer on `requires_disclaimer: true` | Proactive, not reactive — baked into the pipeline |
| Data freshness | Always surface 7-day crime lag | Prevents misinformed decisions on stale data |
| 311 deduplication | Filter `Open - Dup` status before aggregation | Prevents inflated counts from duplicate requests |

---

## Important Constraints and Edge Cases to Handle

- **No location in query:** Router sets `location.type = "none"`, system returns a clarification request, does not attempt retrieval
- **Location is a named neighborhood not in community area list:** Router should fuzzy-match against the 77 community area names, fall back to asking for clarification if confidence is low
- **User asks about a very recent event (within 7 days):** Response must explicitly state the data lag and suggest checking CPD directly or calling 311
- **Query spans multiple neighborhoods:** Support comma-separated community areas in SoQL `$where` clause using `IN` operator
- **Municipal code cross-references:** When a retrieved chunk contains a section reference (e.g. "see Section 17-9-0100"), fetch that section from Qdrant by exact section ID match and include as secondary context
- **Rate limits:** The Chicago Data Portal uses Socrata, which throttles unauthenticated requests. Register for a free app token at `https://data.cityofchicago.org/profile/app_tokens` and include it in all requests as the `X-App-Token` header
- **Large result sets:** Always use `$limit` on all Socrata queries. Never fetch unbounded results.

---

## Stretch Goals (Do Not Prioritize Until Core Is Working)

- **Map view:** Leaflet.js layer showing crime incidents, 311 request pins, and zoning boundaries for a queried neighborhood
- **Address autocomplete:** Use the City of Chicago geocoder API to validate and autocomplete addresses as the user types
- **Additional datasets:** Food inspections (restaurant safety queries), traffic crashes (pedestrian/cyclist safety), building permits (neighborhood development activity)
- **Conversation memory:** Multi-turn chat where follow-up questions like "what about the next neighborhood over?" resolve against the prior context
- **Source transparency panel:** Expandable UI showing exactly which API calls were made and which document chunks were retrieved for each response
- **Response time display:** Show average 311 response times per SR type as a supplementary data point on quality-of-life queries
