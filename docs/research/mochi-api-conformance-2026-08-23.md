# Mochi API conformance review — 2026-08-23

Scope: every Mochi-facing call in `src/mochi_donut/server.py`, compared against Mochi's own
API reference at <https://mochi.cards/docs/api/> (fetched 2026-08-23) and Mochi's changelog at
<https://mochi.cards/changelog/> (latest entry: Version 26.8.2, August 10th, 2026).

**No live API calls were made.** Everything below is documentation reading plus the two live
observations already recorded in issues [#37](https://github.com/JoshuaOliphant/mochi_donut/issues/37)
and [#38](https://github.com/JoshuaOliphant/mochi_donut/issues/38) by the user on 2026-07-18.

---

## Verdict

Our client is substantially correct: the base URL, HTTP Basic auth scheme, endpoint paths, the
kebab-case field names (`deck-id`, `manual-tags`, `archived?`, `parent-id`), the `---` two-sided
content convention, and the multipart attachment contract all match Mochi's published docs — none
of it is folklore. Two real defects exist. First, `list_decks` ignores the documented `bookmark`
pagination on `GET /decks/` entirely, so a user with more decks than one page silently sees a
truncated list; this is the only conformance bug I found by reading alone. Second, `update_card`'s
`trashed?` is documented by Mochi but rejected by the live server with `422 disallowed key`
(issue #37) — our code follows the docs and the docs are wrong, so the fix belongs in the client
(drop the parameter or route it to a deck-level/DELETE mechanism), not in a retry. Beyond that,
the attachment filename constraint in `_sanitize_attachment_stem` is entirely undocumented (the
only authority for `[0-9a-zA-Z]{4,16}` is the live 422 body in issue #38 — a third-party Go client
claims `{8,16}`, so the exact bounds are unsettled), and we impose an image-only extension
allowlist the API does not ask for.

Confidence: high on the doc-derived findings (I read the API reference verbatim, not a summary);
medium on the "why" of the `trashed?` rejection, which only a live call can settle.

---

## Our client surface (the left-hand column)

Base URL: `MOCHI_API_BASE = "https://app.mochi.cards/api"` — `src/mochi_donut/server.py:42`.
Auth on every call: `httpx.AsyncClient(auth=(api_key, ""))` — HTTP Basic, key as username, blank
password. No explicit `Accept` header anywhere; `Content-Type: application/json` comes implicitly
from httpx's `json=` on JSON calls.

| Tool | Method + path | Request fields / params | Response fields read | `server.py` lines |
|---|---|---|---|---|
| `list_decks` | `GET /decks/` | none | `docs[].name`, `docs[].id` | 341–348 |
| `create_cards` | `POST /cards/` (one call per card, sequential) | `deck-id`, `content` (`"Q\n---\nA"`), `manual-tags` | none (body discarded; only status) | 384–392 |
| `list_cards` | `GET /cards/` | `limit` (always sent, default 100), `deck-id`, `bookmark` | `docs[].id`, `docs[].content`, `bookmark` | 425–447 |
| `get_card` | `GET /cards/{id}` | none | `id`, `deck-id`, `tags`, `manual-tags`, `content` | 468–482 |
| `update_card` | `POST /cards/{id}` | `content`, `deck-id`, `manual-tags`, `archived?`, `trashed?` (ISO 8601 or `null`) | none | 516–537 |
| `create_deck` | `POST /decks/` | `name`, `parent-id` | `name`, `id` | 556–565 |
| `update_deck` | `POST /decks/{id}` | `name`, `parent-id`, `archived?` | none | 595–608 |
| `add_attachment` | `POST /cards/{id}/attachments/{filename}` | multipart form, part name `file`, tuple `(filename, bytes, content_type)` | none | 646–667 |

Not a Mochi endpoint but worth noting for completeness: `fetch_url` hits
`https://r.jina.ai/{url}` (`server.py:41`, `313–318`) — out of scope for this review.

---

## Confirmed mismatches

### 1. `list_decks` drops documented pagination — `server.py:341-348`

We send `GET /decks/` with no `bookmark` and never look at the returned `bookmark`; we read
`docs` once and return. Mochi documents `GET /decks/` as a paginated list: "`:bookmark` optional —
string - A cursor for use in pagination. Returned from a previous list request that has additional
documents", and the example response carries a `bookmark` alongside `docs`
(<https://mochi.cards/docs/api/#list-all-decks>). The general pagination contract is at
<https://mochi.cards/docs/api/#pagination>.

Effect: an account with more decks than one server page gets a silently truncated deck list, and
`create_cards` then gets pointed at whatever deck the agent picked from the partial list. The docs
do **not** state the deck page size or expose a `limit` param for decks (`limit` is documented only
on `GET /cards`), so I cannot say from the docs where the cliff is. Note the docs also say "Not
every request that returns a bookmark has additional pages", so a fix must loop until `docs` comes
back empty (or short), not merely until `bookmark` is absent.

Severity: this is the one that will bite a real user. `list_cards` handles the same contract
correctly (`server.py:425-447`).

### 2. `update_card(trashed=...)` — docs say yes, live server says no (issue #37)

`server.py:526-529` sends `"trashed?": "<ISO 8601 with milliseconds>Z"` (or `null` to restore).
That matches the documentation exactly: under Update a card, "`trashed?` optional — timestamp -
Whether the card is in the trash or not. Timestamps should be ISO 8601 format, matching
javascript's `Date#toJSON` method" (<https://mochi.cards/docs/api/#update-a-card>), reinforced by
the Delete-a-card warning: "For a 'soft' deletion you can update a card and set its `trashed?`
property to the current time (as an ISO 8601 timestamp)"
(<https://mochi.cards/docs/api/#delete-a-card>). Our timestamp format (`2026-08-23T12:34:56.789Z`)
is what `Date#toJSON` produces, so the format is not the problem.

The live API nevertheless returns `422 {"errors": {"trashed?": ["disallowed key"]}}` (issue #37,
verified 2026-07-18). So this is a documented-but-unimplemented field, i.e. Mochi's docs are ahead
of (or behind) their card endpoint. Two supporting data points:

- The changelog's only `trashed?` API entry is deck-scoped: "Fixed an issue with the API where it
  was accepting the wrong value for the `:trashed?` property on decks" (Version 1.13.8, March 17th,
  2022 — <https://mochi.cards/changelog/>). There is no changelog entry adding or removing
  `trashed?` on cards.
- Sending `null` to untrash is our own invention: the docs type the field as a timestamp and never
  document a clearing value. Even if `trashed?` were accepted, the restore path is unverified.

Documented alternatives for removing a card, neither of which we implement:
`archived?` (boolean, documented on both create and update — and, per issue #37, accepted by the
live account on the same endpoint), and `DELETE /cards/:id`, which "Permanently deletes a card and
its attachments" and "cannot be undone" (<https://mochi.cards/docs/api/#delete-a-card>).

### 3. Attachment filename constraint is undocumented — `server.py:614-624`

`_sanitize_attachment_stem` enforces `[0-9a-zA-Z]{4,16}` by stripping non-alphanumerics, truncating
to 16, and right-padding with `0` to 4. Mochi's attachment section documents **no** filename rule
at all: it covers only the multipart requirement, the `file` form field, and the response shape
(<https://mochi.cards/docs/api/#add-an-attachment>). Every filename in Mochi's own examples happens
to be 8 alphanumeric characters (`Q9DlrByP.mp3`, `foobar03.png`), which is suggestive but not a
specification.

The `{4,16}` bound comes solely from the live 422 body captured in issue #38:
`{"errors": {"attachments": {"<name>": {"file-name": ["must match /[0-9a-zA-Z]{4,16}/"]}}}}`
(2026-07-18). The only other source I found is a third-party Go client whose `Attachment.FileName`
comment says "File name must match the regex `/[0-9a-zA-Z]{8,16}/`. E.g. `j94fuC0R.jpg`"
(<https://pkg.go.dev/github.com/leonhfr/mochi/mochi>).

**These two are not competing claims.** The `{4,16}` string is Mochi's own validator regex, quoted
back verbatim in its own 422 body — the server describing its own rule. The Go client's `{8,16}` is
one developer's comment in a third-party wrapper, and it is contradicted by the primary source. Our
`{4,16}` bound is correct; treat the Go comment as stale or mistaken, not as evidence.

The one genuine residual: issue #38 empirically exercised a 12-character stem (passes) and a
hyphenated stem (fails), but never a 4-character one, so the *lower* bound is stated-but-unexercised.
`ljust(4, "0")` only ever emits an exactly-4-character stem when the basename has 3 or fewer
alphanumerics, which is rare. Low-value to test; not a reason to distrust the current fix.

Also related, and only weakly documented: the changelog records "API: Validate that attachments
have a file extension" (Version 1.15.23, June 29th, 2023). Our extension requirement at
`server.py:648-653` is therefore justified, but see the next section for the *set* of extensions.

### 4. Image-only attachment allowlist is our restriction, not Mochi's — `server.py:46-53`

`ATTACHMENT_CONTENT_TYPES` permits png/jpg/jpeg/gif/svg/webp and rejects everything else with a
`ValueError` before any request is made. The comment on line 44–45 attributes this to "Mochi's
attachment endpoint (https://mochi.cards/docs/api/)". The docs say no such thing — their worked
example uploads `Q9DlrByP.mp3` with content type `audio/mpeg`
(<https://mochi.cards/docs/api/#add-an-attachment>), and the markdown docs state that image embed
syntax "will work for audio and video files as well"
(<https://mochi.cards/docs/markdown/basic-formatting/>). So audio and video attachments are
supported by Mochi and unreachable through our tool. This is a deliberate product narrowing, not a
protocol requirement — but the code comment citing the API docs as its authority is inaccurate.

### 5. Trailing-slash comment cites the docs for something the docs don't say — `server.py:342-343, 381-382, 562-563, 433-434`

Four comments say the trailing slash "is required: Mochi's router 404s on /api/decks but resolves
/api/decks/ (see https://mochi.cards/docs/api/)". The docs never mention this, and their own
examples use the *unslashed* form in three places: the auth example
`curl https://app.mochi.cards/api/decks -u my_api_key:`
(<https://mochi.cards/docs/api/#authentication>), and the list examples
`GET https://app.mochi.cards/api/cards?bookmark=some-bookmark` and
`GET https://app.mochi.cards/api/decks?bookmark=somebookmarkgoeshere`. The endpoint tables also
list `GET /cards` and `GET /decks` without slashes.

The behavior may well be real (it reads like something learned the hard way), but it is not
documented and the citation is wrong. Harmless in practice — we always send the slash, and the
slashed form appears in the docs' own POST examples — so this is a comment-accuracy defect, not a
runtime one.

---

## Matches

| What | Our code | Doc says | Source |
|---|---|---|---|
| Base URL | `https://app.mochi.cards/api` (`:42`) | `https://app.mochi.cards/api/` | [#authentication](https://mochi.cards/docs/api/#authentication) |
| Auth | Basic, key as username, blank password | "Provide your API key as the basic auth username value. You do not need to provide a password." | [#authentication](https://mochi.cards/docs/api/#authentication) |
| Request encoding | JSON via httpx `json=` | "accepts JSON or transit+json encoded request bodies" | [API Reference intro](https://mochi.cards/docs/api/) |
| `POST /cards/` create | `deck-id` + `content` (`:386-390`) | both required, `content` = "The markdown content of the card", `deck-id` = keyword | [#create-a-card](https://mochi.cards/docs/api/#create-a-card) |
| `manual-tags` field name | `:389`, `:522` | documented on create and update: "set of strings … Tags should not include the initial # character" | [#create-a-card](https://mochi.cards/docs/api/#create-a-card), [#update-a-card](https://mochi.cards/docs/api/#update-a-card) |
| `manual-tags` overwrite semantics | `update_card` replaces the whole list | "Setting this will overwrite whatever value for this field was already set on the card" | [#update-a-card](https://mochi.cards/docs/api/#update-a-card) |
| `---` two-sided content | `f"{q}\n---\n{a}"` (`:388`) | "The `---` separator divides the card a front and back side. Cards are not limited to two sides" | [docs/cards/](https://mochi.cards/docs/cards/) |
| One request at a time | `create_cards` loops sequentially (`:373-392`) | "API calls are limited to one concurrent request per account. You must wait for the previous request to return" | [#concurrency-limiter](https://mochi.cards/docs/api/#concurrency-limiter) |
| `GET /cards/` params | `limit`, `deck-id`, `bookmark` (`:425-429`) | exactly those three, all optional | [#list-cards](https://mochi.cards/docs/api/#list-cards) |
| `limit` range | tool docstring says 1–100, default 100 | "The limit can range from 1 and 100, and the default is 10" | [#list-cards](https://mochi.cards/docs/api/#list-cards) |
| Paginated response shape | reads `docs` + `bookmark` (`:438-447`) | "an object with a `docs` property and a `bookmark` property" | [#pagination](https://mochi.cards/docs/api/#pagination) |
| `GET /cards/{id}` fields | `id`, `deck-id`, `tags`, `content` (`:473-482`) | all present in the retrieve example response | [#retrieve-a-card](https://mochi.cards/docs/api/#retrieve-a-card) |
| `POST /cards/{id}` update path | `:537` | "The ID of the card must be passed in as part of the URL" | [#update-a-card](https://mochi.cards/docs/api/#update-a-card) |
| `archived?` on cards | `:524` | "boolean - Whether the card is archived or not" | [#update-a-card](https://mochi.cards/docs/api/#update-a-card) |
| `POST /decks/` create | `name` required, `parent-id` optional (`:556-558`) | same | [#create-a-deck](https://mochi.cards/docs/api/#create-a-deck) |
| Deck create response | reads `name`, `id` (`:567-570`) | "Returns the deck that was created, including its ID" | [#create-a-deck](https://mochi.cards/docs/api/#create-a-deck) |
| `POST /decks/{id}` update | `name`, `parent-id`, `archived?` (`:597-601`) | all three documented optional | [#update-a-deck](https://mochi.cards/docs/api/#update-a-deck) |
| Deck list response | reads `docs[].name`, `docs[].id` (`:348`) | example response `docs` entries carry `id`, `sort`, `name` | [#list-all-decks](https://mochi.cards/docs/api/#list-all-decks) |
| Attachment path | `POST /cards/{id}/attachments/{filename}` (`:664`) | same | [#add-an-attachment](https://mochi.cards/docs/api/#add-an-attachment) |
| Attachment encoding | multipart via httpx `files={"file": ...}` (`:665`) | "must be sent as form data with the content-type of form/multi-part"; curl example uses `-F file=@…`; the Python example uses `requests.post(url, files=data, auth=basic)` | [#add-an-attachment](https://mochi.cards/docs/api/#add-an-attachment) |
| `@media/` reference syntax | success message (`:670-672`) | create-a-card example content: `"New card from API. ![](@media/foobar03.png)"` | [#create-a-card](https://mochi.cards/docs/api/#create-a-card) |
| Attachments need an extension | `:648-653` | changelog: "API: Validate that attachments have a file extension" (v1.15.23, 2023-06-29) | [changelog](https://mochi.cards/changelog/) |

---

## Documented but ignored

None of these are bugs; they're the surface we've chosen not to expose. Listed so the comparison is
complete.

- **Card fields we never send**: `template-id`, `fields`, `pos`, `review-reverse?`
  ([#create-a-card](https://mochi.cards/docs/api/#create-a-card)). `pos` in particular is the
  documented way to control card order within a deck.
- **Deck fields we never send**: `sort`, `sort-by`, `cards-view`, `show-sides?`,
  `sort-by-direction`, `review-reverse?`, and `trashed?`
  ([#update-a-deck](https://mochi.cards/docs/api/#update-a-deck)). Deck-level `trashed?` is
  documented *and* has a changelog fix behind it (v1.13.8, 2022-03-17), so it is more likely to
  actually work than the card-level one — see Open questions.
- **Endpoints we don't touch**: `DELETE /cards/:id`, `DELETE /decks/:id`,
  `DELETE /cards/:id/attachments/:filename`, `GET|POST /templates`, `GET /templates/:id`,
  `GET /due`, `GET /due/:deck-id` (all in the [API reference](https://mochi.cards/docs/api/)).
  There is no way to remove an attachment through our client once uploaded.
- **Create/update response bodies**: `POST /cards/` "will return the created card"
  ([#create-a-card](https://mochi.cards/docs/api/#create-a-card)) but `create_cards` discards it
  (`server.py:392`), so callers never learn the new card IDs and can't attach media without a
  follow-up `list_cards`.
- **`Accept` header**: the docs say responses come back in "whichever encoding is specified in the
  Accept header" ([#retrieve-a-deck](https://mochi.cards/docs/api/#retrieve-a-deck)), and their
  examples always send `Accept: application/json`. We send httpx's default (`*/*`) and call
  `.json()` on the result. It evidently works today, so the server default must be JSON — but the
  docs never promise that, and transit+json would break every parse. Cheap insurance to set it.
- **429 handling**: "you might see error responses with status code 429"
  ([#rate-limits](https://mochi.cards/docs/api/#rate-limits)). We have no backoff anywhere;
  `create_cards` records the failure per card and moves on, the other tools raise. Our sequential
  loop respects the concurrency limiter, so 429s should be rare, but a burst of tool calls from the
  agent side could still trip it.
- **Error body shape**: documented as `{"errors": [...]}` or, for validation, `{"errors": {"field":
  "..."}}` ([#errors](https://mochi.cards/docs/api/#errors)). `create_cards` truncates the response
  text to 100 characters (`server.py:395`), which is enough for a flat error but will decapitate the
  nested attachment-style error seen in issue #38.

---

## Unverified / undocumented

Flagged explicitly because Mochi's docs are silent, not because I think they're wrong.

- **Attachment size limit**: not documented. The only signal is a 2022 changelog line, "Fixed an
  issue with the API where attachments larger than 100kb were failing" (v1.14.2, 2022-06-06 —
  [changelog](https://mochi.cards/changelog/)), which implies >100kb works now but names no ceiling.
  We read the whole file into memory (`server.py:659`) and check nothing.
- **Supported attachment MIME types**: not documented. Mochi's example uses `audio/mpeg`; their
  markdown docs mention image, audio and video. No allowlist is published.
- **Whether `manual-tags` is echoed back on `GET /cards/{id}`**: not documented. The retrieve
  example response shows `tags` but no `manual-tags`
  ([#retrieve-a-card](https://mochi.cards/docs/api/#retrieve-a-card)). `get_card` reads
  `card.get("manual-tags")` with an `or []` fallback (`server.py:474`), so it degrades quietly if
  the key is absent — but the "manual-tags:" line it prints may just always say `none`.
- **Deck list page size**: not documented. `limit` is documented only for cards.
- **Trailing-slash routing**: not documented; docs examples contradict our comments (see mismatch 5).
- **`null` as an untrash value for `trashed?`**: not documented (see mismatch 2).
- **An undocumented base64 attachment path may exist.** The same third-party Go client models an
  `attachments` array on the card create/update request bodies, with `data` as a "Base64 encoded
  representation of the attachment data"
  (<https://pkg.go.dev/github.com/leonhfr/mochi/mochi>). Mochi's docs describe only the multipart
  endpoint. **Unverified, non-primary** — I could not trace this back to any Mochi page. Mentioned
  only because, if real, it would let `create_cards` ship a card and its media in one request. Do
  not build on it without testing.

---

## Open questions (need a deliberate live call)

Each of these can only be settled by hitting the real API. I did not run any of them. Do them
against a throwaway deck.

1. **Does `trashed?` work on decks?** `POST /api/decks/{id}` with `{"trashed?": "<ISO>"}`. If it
   returns 2xx, deck-level soft-delete is a viable feature and issue #37 is card-specific. Issue #37
   explicitly notes this is untested.
2. **What exactly does card update accept?** Post a deliberately bogus key
   (`{"nonsense-key": 1}`) to `POST /api/cards/{id}` and read the 422 body. If Mochi echoes the
   allowed set, that resolves the card-update field list without guessing.
3. **Is the stated 4-character lower bound real?** Upload a stem of length 4 (`abcd.png`).
   Mochi's own 422 regex says `{4,16}` and that is authoritative; this only exercises a boundary
   the issue-#38 session never hit. Low value — run it if you're touching attachments anyway.
4. **Does the attachment endpoint accept non-image types?** Upload a `.mp3` (Mochi's own example
   type) to confirm before widening `ATTACHMENT_CONTENT_TYPES`.
5. **What is the deck-list page size, and does `limit` work on `/decks/`?** Needed to size the
   pagination fix in mismatch 1 and to know whether we can just ask for 100.
6. **Is `manual-tags` returned on `GET /cards/{id}`?** Create a card with tags, read it back.
   Determines whether `get_card`'s manual-tags line is dead output.
7. **Does the server honor `Accept: application/json`, and what does it return without one?**
   Confirms whether the missing header is a latent transit+json hazard.

---

## Sources

Primary (Mochi's own):

- <https://mochi.cards/docs/api/> — the current API reference. Fetched 2026-08-23 and read in full
  (raw HTML, not a summary). Established: base URL, Basic auth, JSON/transit encodings, pagination
  (`docs` + `bookmark`), error shapes, rate limits and the one-concurrent-request limiter, and the
  full parameter lists for cards, decks, templates, due and attachments. This is the single most
  load-bearing source in this document; anchors used inline: `#authentication`, `#pagination`,
  `#errors`, `#rate-limits`, `#concurrency-limiter`, `#create-a-card`, `#retrieve-a-card`,
  `#list-cards`, `#update-a-card`, `#delete-a-card`, `#add-an-attachment`, `#create-a-deck`,
  `#retrieve-a-deck`, `#list-all-decks`, `#update-a-deck`.
- <https://mochi.cards/docs/cards/> — established that the `---` separator is Mochi's documented
  multi-side card syntax, not our invention, and that cards may have more than two sides.
- <https://mochi.cards/docs/markdown/basic-formatting/> — established that the image embed syntax
  also covers audio and video attachments.
- <https://mochi.cards/changelog/> — established the dated API history: rate-limit policy change to
  one concurrent request (v1.18.12, 2025-05-04), ad-hoc tags added to the API (v1.18.3, 2024-12-27),
  `/due` endpoint added (v1.20.5, 2025-10-28), attachment file-extension validation (v1.15.23,
  2023-06-29), the >100kb attachment fix and DELETE/template endpoints (v1.14.2, 2022-06-06), the
  `deck-id` filter on `GET /cards` (v1.13.9, 2022-03-29), and the deck-only `:trashed?` fix
  (v1.13.8, 2022-03-17). Latest entry v26.8.2, 2026-08-10 — the changelog is current.
- <https://mochi.cards/api/> — 404s. There is no docs page at that path; the reference lives at
  `/docs/api/`.
- <https://app.mochi.cards/api/openapi.json> — 404s. No machine-readable spec is published.
- <https://forum.mochi.cards/> — search is not reachable by URL query (`?q=` 404s); I found no
  primary forum statement on the attachment filename rule or the `trashed?` rejection.

Non-primary, labeled as such where used:

- <https://pkg.go.dev/github.com/leonhfr/mochi/mochi> — third-party Go client. Source of the
  competing `[0-9a-zA-Z]{8,16}` filename claim and of the undocumented base64 `attachments` array.
  Treated as a lead, not evidence; I could not trace either claim back to a Mochi page.

Repo-internal observations of live behavior (the user's own, not mine):

- [Issue #37](https://github.com/JoshuaOliphant/mochi_donut/issues/37) — live `422 {"errors":
  {"trashed?": ["disallowed key"]}}` on card update, verified 2026-07-18; same account accepts
  `archived?: true` on the same endpoint.
- [Issue #38](https://github.com/JoshuaOliphant/mochi_donut/issues/38) — live `422` with
  `{"file-name": ["must match /[0-9a-zA-Z]{4,16}/"]}`, verified 2026-07-18;
  `breaker-states.png` fails, `breakerstates.png` succeeds.
