# Chat quotas: amendments to Item 120 (2026-11)

## Item 135: free clarifications are capped, and never given back to the network count (2026-11-22)

- **Status:** built on `fix/chat-clarification-quota`, gates green, not merged.
- **What happened:** the owner saw a signed-out visitor in production get "1 question left" and then keep asking. The production database (read-only, 2026-11-22) showed one visitor, seven turns between 16:35 and 16:38 Chicago time. Two were answered (`incident_lookup`, `legal_question`). Five were off-topic questions about the mayor and his clothes, which the router answered with `clarification_needed`. The visitor's counter stood at 2 and the network's at 2. No signed-out counter has ever gone past 3, so the cap itself held.
- **Cause:** Item 120 gave a clarification's question back every time. The router also uses `clarification_needed` for off-topic questions, so a visitor with one question left could ask off-topic questions forever. Each one still cost 1 or 2 model calls (8 calls for those five turns). The network's daily ceiling was given back the same way, so it didn't stop this either.
- **Decision:**
  - A failed turn still gives everything back.
  - A clarification gives back the visitor's own question (`anon:` or `user:`) only while their free clarifications last. That allowance is a counter `clar:<subject>` with the same period: all time when signed out, the Chicago month when signed in. The limit is `QUOTA_FREE_CLARIFICATIONS`, default 3. After that, a clarification counts as a question.
  - A clarification never gives back the network count. The 15-a-day signed-out ceiling per network now covers every turn that isn't a failure, so clearing cookies can't mint free clarifications either.
  - `_event_stream` sets `outcome["clarification"]`, and `/chat` passes it to `Ticket.refund(clarification=)`.
  - Counters `clar:` are pruned with the anonymous rows (90 days untouched), and `clar:user:<id>` is deleted with the account.
- **Alternatives:**
  - *Count every clarification.* Rejected: a real "which address?" is the router's uncertainty, not the visitor's question, and Item 120 chose not to charge for it.
  - *Have the router tell off-topic apart from clarification.* Not now: it's a prompt change that needs the paid router eval, and an off-topic reply still costs a model call, so it would need a cap anyway.
  - *Free only when the previous turn wasn't a clarification.* Rejected: signed-out chats aren't stored, so there's no previous turn on the server to check.
- **Worst case after the change:** a signed-out cookie gets 3 answers plus 3 free clarifications, and then it's refused. A network gets at most 15 non-failing signed-out turns a day. A free account gets 50 questions and 3 free clarifications a month.
- **Evidence:** `backend/tests/test_quotas.py` (+4: the production sequence of 2 answers then clarifications is refused after the 4th clarification; clarifications on fresh cookies meet the network ceiling; failures still give the network count back; free clarifications reset with the month). `backend/tests/test_api.py` (+1: the real stream marks a clarification). Three of the new tests fail on the old code.
- **Front end:** unchanged. `useChat` re-reads `/api/usage` after every `done`, so a clarification that counts shows up in the count and locks the box at zero.
- **Revisit if:** the router learns to label off-topic questions separately (then off-topic could always count and real clarifications always be free); people with real questions run out of free clarifications.
