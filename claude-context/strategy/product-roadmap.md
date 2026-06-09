# Product Roadmap — UrbanLayer

## What's Built and Deployed

| Capability | Status |
|-----------|--------|
| RAG over Municipal Code (14,535 chunks) | Production |
| LLM Router + Synthesizer (Sonnet + Haiku) | Production |
| Property / Regulatory / Incentives / Neighborhood domains | Production |
| Crime / 311 / Permits / Violations / Business / Vacant / Food Inspections | Production |
| Interactive Map (Mapbox + deck.gl) | Production |
| Conversation Persistence + Shareable Links | Production |
| Auth (Google OAuth) + Rate Limiting + Stripe Payments | Production |
| Property Scorecard (non-AI instant dashboard) | Production |
| Site Explorer / Property Finder | Production |
| PDF Report v3 (premium development feasibility) | Production |
| Investigate Buttons (dashboard → chat) | Production |
| Landing Page (site feasibility positioning, Developer/Architect/Attorney personas) | Production |
| Multi-language (Spanish) | Production |
| Mobile UX (bottom sheet, 3-tab) | Production |
| Admin Dashboard + Eval Suite (93% coverage) | Production |
| CSV Data Export (Scorecard, Explorer, Analytics) | Production |

## Revenue Features (Shipped)

| Feature | Revenue Model |
|---------|--------------|
| Property Scorecard | Free: 3/day, Pro: unlimited |
| Site Explorer | Pro only ($99/mo) |
| PDF Reports | Pro only |
| Chat | Free: 3/day, Pro: unlimited |

## Pricing Model

| Tier | Price | Includes |
|------|-------|---------|
| **Free** | $0 | 3 scorecard/day, 3 chat/day, map view |
| **Pro** | $99/mo ($1,089/yr) | Unlimited scorecard, PDF reports, Explorer, chat, municipal code RAG, PTAXSIM, Spanish |
| **Enterprise** | $249/mo ($2,749/yr) | Everything + team seats, CSV/GIS export, zoning alerts, contractor lead gen, API access. **Deferred.** |

## Remaining Opportunities

### High Value (not yet built)
- **Contractor Intelligence / Lead Gen** — Parse `contact_X_type` fields from permits to identify projects missing specific trades. Subcontractors pay for these leads.
- **Zoning & Municipal Code Update Alerts** — Cron diffing the municipal code HTML. Paid users watch chapters or areas. Email alerts on changes.
- **Property Tracker Alerts** — Watch addresses for new violations/permits/assessment changes. Email notifications.
- **Pending Zoning Changes** — LLM-based PDF extraction from Legistar portal. High effort, high value.
### Infrastructure
- **Advanced context management** — Beyond existing TurnSummary + sliding window.
- **Latency reduction** — 2 items remain: vector tiles, model routing for simple queries.
- **GPU acceleration** — Embedding/reranker on CPU only. Not applicable to current server (x86, no GPU).

## Target Customer Personas (Priority Order)

1. **Zoning & Land Use Attorneys** — $300–$600/hr, spend hours manually searching municipal code. *"WestLaw for Chicago zoning."*
2. **Commercial Real Estate Developers** — Need consolidated site due diligence. *"Your entire due diligence checklist in one search."*
3. **Subcontractors & Construction Service Providers** — Want permit-based leads. *"Find projects that need you before your competitors do."*
4. **Commercial Brokers & Lenders** — Need comps, tax history, violation audits. *"Collateral due diligence in 30 seconds."*
5. **Community Organizations & Nonprofits** — Lower individual willingness to pay, potential grant-funded licenses.

## Open Strategic Questions

1. **Build vs. Buy for property ownership data?** Licensing bulk deed data adds recurring cost but unlocks major feature gap.
2. **PDF parsing for pending zoning changes?** LLM extraction possible but labor-intensive to maintain accuracy.
3. **When to expand beyond Chicago?** Entire pipeline is Chicago/Cook County-specific. Replication is essentially a rebuild.
4. **Freemium conversion rate assumptions?** Need to model token costs per query against subscription revenue at 3 free/day.
5. **Enterprise sales vs. self-serve?** High-touch enterprise or optimize self-serve conversion?
