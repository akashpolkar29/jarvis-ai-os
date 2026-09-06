# Job-search scoping notes — LinkedIn/Indeed, investigated, then resolved

**Status: research written 2026-09-06 (no decision, nothing built at
that point); resolved the same day — see "Resolution" at the bottom.**
No code was written for the original research pass — no port, no
adapter, no application module, no capability, no ADR. Mirrors
`m7-scoping-notes.md`'s own precedent exactly: a real investigation of
a genuine, previously-named capability gap, options laid out for the
user's own decision.

## The one finding that matters more than anything else below

**Both LinkedIn and Indeed's own real, current Terms of Service
explicitly and unconditionally prohibit automated scraping/bot access
to their job-search surfaces, full stop — not "unless for personal,
non-commercial use," not "unless rate-limited politely."** Both sites'
own `robots.txt` independently corroborates this for the exact paths a
job-search capability would need. Neither site offers a realistic
official API path for an individual, non-commercial tool either —
this isn't a case of "ToS says no, but there's a sanctioned API
instead." **Building `job_search.search` as a scraper against either
site's live, rendered pages would mean shipping a capability whose
only real implementation method contradicts both platforms' own
governing terms.** This is stated first, prominently, because burying
it under a neutral options list would misrepresent how one-sided the
real finding actually is. See "The ToS/robots.txt investigation, in
full" below for the verbatim clauses this conclusion rests on.

This does not by itself mean "never build this" — see "What this
finding does and doesn't foreclose" below — but it does mean the
straightforward reading of M7-style "reuse `BrowserAutomationPort`,
same as M6a's own research conclusion" does not survive contact with
the real terms governing these two specific sites, unlike the general
open-a-URL-and-read-it research capability M6a's own design already
covers for arbitrary other pages.

## 1. What `browser.*` can already do, versus what job-board search would need

### The real, current `BrowserAutomationPort` surface

Checked directly against `ports/browser_automation.py` and
`kernel/browser.py`'s own real registrations — four capabilities
exist, no others:

| Capability | Effect | What it does |
| --- | --- | --- |
| `browser.open_page` | `EXECUTE` | Launch a dedicated, headless, CDP-controlled page, navigated to a URL |
| `browser.screenshot` | `EGRESS_LOCAL` | Capture a real PNG of the page's current rendered content |
| `browser.inspect_dom` | `EGRESS_LOCAL` | Return the outer HTML of the first element matching a CSS selector, live against the current DOM |
| `browser.close_page` | `EXECUTE` | Terminate the page's real subprocess |

**Real, load-bearing gap: there is no clicking, form-filling, or
typing-into-a-page capability anywhere in this port.** `query_dom` is
read-only; nothing in `BrowserAutomationPort` can submit a search form,
click a "Next page" link, or type into a search box. This mirrors
`m5-scoping-notes.md`'s own already-recorded LSP/code-context gap in
shape: a real, structural absence, not an oversight to route around
quietly.

### What a minimal job-board search could reuse as-is, versus what it genuinely needs

**Reusable as-is, if built at all**: `open_page`/`inspect_dom`/
`close_page` are sufficient for a *URL-parameter-driven* search — both
LinkedIn (`/jobs/search/?keywords=...&location=...`) and Indeed
(`/jobs?q=...&l=...`) support real, documented GET-based search URLs
that return a fully rendered results page with no form interaction
required. A minimal implementation could construct the search URL
directly from the caller's real search terms, `open_page` it,
`inspect_dom` the results container, and `close_page` when done — no
new port method needed for the *search* step itself.

**Genuinely missing, and would need new `BrowserAutomationPort`
surface**: pagination beyond the first results page (Indeed's own
`robots.txt` specifically disallows `/*&start=` for general crawlers —
see below — so this is doubly relevant), and anything requiring a
logged-in session (see "The authenticated-session complication" below).
`query_dom`'s own "first matching element only" shape would also need
either a new "all matching elements" method or N sequential calls with
increasingly specific selectors to extract a full result list — a real
API-shape decision, not resolved here.

## 2. The ToS/robots.txt investigation, in full

Checked directly against each site's own real, current, live text
(fetched today, not recalled from training data) — not assumed either
way, per this task's own explicit instruction.

### LinkedIn

**`robots.txt`** (`https://www.linkedin.com/robots.txt`) disallows,
among others, exactly the paths a job-search capability would need:

```
Disallow: /jobs?runSearch*
Disallow: /search*
Disallow: /jsearch*
Disallow: /job-apply/
Disallow: /jobs-guest/
Disallow: /api/jobPostings/jobs*
```

`LinkedInBot` (LinkedIn's own first-party crawler) gets `Allow: /`;
every other user-agent, including a generic CDP-driven browser with no
special user-agent string, is denied the search paths above.

**User Agreement** (`https://www.linkedin.com/legal/user-agreement`,
Section 8.2) — quoted verbatim:

> 8.2(2): "Develop, support or use software, devices, scripts, robots
> or any other means or processes (such as crawlers, browser plugins
> and add-ons or any other technology) to scrape or copy the Services"
>
> 8.2(13): "Use bots or other unauthorized automated methods to access
> the Services, add or download contacts, send or redirect messages,
> create, comment on, like, share, or re-share posts, or otherwise
> drive inauthentic engagement"
>
> 8.2(4): "Copy, use, display or distribute any information (including
> content) obtained from the Services, whether directly or through
> third parties (such as search tools or data aggregators or brokers),
> without the consent of the content owner"

No carve-out for personal, non-commercial, individual use appears
anywhere in these clauses.

**Official API**: LinkedIn's Job Posting API exists for the opposite
direction (employers/ATS vendors distributing job postings *to*
LinkedIn, via a Partner Onboarding Form requiring a business
development contact) — not for reading/searching listings *from*
LinkedIn as an individual. General data-extraction API access has not
been granted to new third parties since 2018; a developer-program
application naming "search job listings" or "job search automation" as
its use case is a named, explicitly rejected category, not merely an
unlikely approval.

### Indeed

**`robots.txt`** (`https://www.indeed.com/robots.txt`) disallows the
entire job-search/view surface for general-purpose crawlers:

```
Disallow: /jobs
Disallow: /job/
Disallow: /viewjob
Disallow: /q-
Disallow: /l-
Disallow: /*radius=
Disallow: /*&start=
```

A named, narrower allowance exists for specific search-engine/AI
crawlers (Googlebot, Bingbot, Claude-SearchBot, DuckDuckBot get
`Allow: /`; GPTBot/CCBot/ClaudeBot/anthropic-ai get a narrow
`Allow: /*&start=0&` through `/*&start=90&` window only) — none of
these apply to a CDP-driven browser automation tool acting on a
JARVIS user's own behalf, which presents no such recognized crawler
identity. `Scrapy` (a well-known scraping framework) and several other
generic bots are disallowed entirely (`Disallow: /`).

**Terms of Service** (`https://www.indeed.com/legal`) — quoted
verbatim: "You agree not to use any robot, spider, scraper, or other
automated means to access the Indeed site for any purpose without
Indeed's express written permission." A separate, narrower clause also
specifically prohibits automating the Indeed Apply flow outside
Indeed's own official vendors — directly reinforcing, not
contradicting, this project's own already-decided M6b "no auto-apply"
structural boundary (ADR-0058); that boundary was the right call for a
reason beyond just this project's own charter.

**Official API**: Indeed's own Developer Agreement
(`https://docs.indeed.com/legal-terms/developer-agreement`) requires
written pre-approval for any Integration/Application, states no
guaranteed response timeframe, and can reject "for any or no reason."
It explicitly forbids using the API to "scrape, build databases or
otherwise create permanent copies of any content of End Users or Job
Seekers, except as required for the purpose of the Integration," and
forbids competitive-analysis/competing-product use cases. Nothing in
the agreement names individual, non-commercial, read-only job search
as an accepted use case; realistically, this requires contacting
Indeed's Partner team directly with no stated path or timeline for a
personal project.

### Real, honest limits of this specific investigation

This is a documentation-level ToS/robots.txt read, not a legal
opinion — whether robots.txt is independently enforceable (it
generally isn't, on its own, in most jurisdictions) versus the ToS
clauses (which are a real, binding contract a user accepts by using
the site) is a real distinction this document does not resolve
definitively; both point the same direction here regardless, which is
why the finding above is stated as plainly as it is. Account-level
enforcement risk (a personal LinkedIn/Indeed account getting banned
for ToS-violating automated access) was not separately investigated
beyond what's already implied by the clauses above.

## 3. The authenticated-session complication (a real, additional finding, not asked for but load-bearing)

Beyond the ToS question: LinkedIn in particular gates most meaningful
job-search functionality (full listing details, "Easy Apply" metadata,
personalized results) behind a real, authenticated session — an
anonymous, logged-out request returns a materially degraded result set
and is far more aggressively bot-detected/CAPTCHA-walled than a
logged-in one. A real implementation that wanted useful results would
likely need the user's own real, personal LinkedIn session (cookies or
credentials) flowing through `BrowserAutomationPort` — a fundamentally
different, larger risk surface than the current four capabilities'
own "no credential, no session state, anonymous CDP page" shape. This
would add real `Effect.CREDENTIAL` exposure on top of the ToS question
above, not instead of it. Indeed's own public search results are
somewhat more usable anonymously, but the `robots.txt`/ToS findings
above apply regardless of authentication state.

## 4. What a minimal `job_search.search` capability's shape would look like, if built anyway

Laid out as options, not a recommendation — the ToS finding above is
the real reason this section is hedged rather than concrete.

- **Inputs**: real search criteria (job title/keywords, location,
  possibly salary range or remote-work preference) — likely
  `Classification.PERSONAL` at minimum (this describes the user's own
  career situation), `Classification.SENSITIVE` if criteria include
  something like current employer (to exclude) or salary
  expectations, matching `application/communications/classification.py`'s
  own existing PERSONAL/SENSITIVE distinction rather than inventing a
  new one.
- **Output**: a real, structured sequence of listing summaries
  (title/company/location/URL, mirroring `EmailSummary`'s own shape)
  — **every returned item must be tagged `Trust.UNTRUSTED_EXTERNAL`**,
  matching `browser.screenshot`'s/`authorize_and_list_email`'s own
  established precedent for adversary-influenced content: a job
  posting's own text is written by an external, unverified party and
  should never be treated as trusted input to a later reasoning call
  (e.g. if a future capability summarized or auto-drafted a response
  based on a listing's own text) without this tag surviving the trip.
- **Effect/Tier**: the base "read already-rendered content out to the
  caller" step is analogous to `browser.inspect_dom`'s own
  `EGRESS_LOCAL`/`Tier.ALLOW` — *if* built anonymously, with no session
  credential involved. If the authenticated-session complication above
  is not avoided, `Effect.CREDENTIAL` would need to apply too,
  matching `git.push`'s own reasoning for why credential-bearing
  actions carry that effect regardless of their other classification
  — real callers would need to decide this before writing any
  `CapabilityDescriptor`, not have it decided implicitly by omission.
  The prompt's own working assumption ("almost certainly
  `EGRESS_SENSITIVE`-or-higher") does not clearly hold for the
  anonymous case specifically — `EGRESS_SENSITIVE` in this codebase's
  own existing precedent (`application/communications/classification.py`)
  describes the *sensitivity of content leaving the machine*, and a
  public job listing's own text is not the user's own sensitive data;
  the user's own *search criteria* going out to a third-party site
  (LinkedIn/Indeed) as part of the request is the more plausible
  EGRESS_SENSITIVE trigger, if any, and only if those criteria
  themselves qualify as SENSITIVE per the Inputs bullet above.

## 5. Real, named tradeoffs: scraping the rendered page vs. an official API

- **Scraping (CDP + `query_dom`, the only mechanism this codebase
  already has)**: fragile to real layout/selector changes (both sites
  redesign their result-page markup periodically, with no
  compatibility guarantee to a third party); genuinely, currently
  ToS-prohibited on both sites per the investigation above; no rate
  limits or usage terms to negotiate because there's no agreement to
  operate under, which cuts both ways — no formal quota, but no
  sanctioned standing either, and account-level enforcement risk falls
  on whichever real account/IP does the browsing.
- **Official API**: would resolve the ToS question cleanly, and
  (for a genuinely approved integration) would likely be more stable
  than scraping a rendered page — but, per the investigation above,
  **neither LinkedIn nor Indeed currently offers one an individual,
  non-commercial tool could realistically obtain approval for.** This
  isn't "harder to get, but possible" — job-search/scraping is a named,
  explicitly rejected use-case category for LinkedIn's developer
  program specifically, and Indeed's own agreement offers no
  individual/personal-project pathway at all.
- **A third, real option this investigation surfaces, not previously
  named in the prompt**: aggregator services that themselves hold a
  legitimate license/agreement with job boards (or that aggregate from
  sources with more permissive terms — many individual company career
  pages have no comparable ToS restriction at all) exist and are what
  most production job-search products actually integrate against
  instead of scraping LinkedIn/Indeed directly. Not investigated in
  depth here (out of this task's own scope, which named LinkedIn/Indeed
  specifically) but worth naming as a real alternative path if the user
  wants to revisit this.

## What this finding does and doesn't foreclose

**Does not foreclose**: building `job_search.search` (or an equivalent
capability) against sources that don't carry this same ToS
prohibition — the third option in section 5, or a site the user
separately decides is acceptable to target. It also doesn't change
anything about `job_assistance.draft`'s own existing scope (drafting
from a task description the user already provides) — that capability
never needed to search anything and remains untouched by this
investigation.

**Does foreclose, absent a new decision**: building this specific
capability as a scraper against LinkedIn or Indeed's own live pages
using this codebase's existing `BrowserAutomationPort`, without the
user first deciding this ToS finding is an acceptable risk to take —
mirroring exactly how `m6b-job-assistance.md`'s own "no auto-apply"
finding became a real, enforced structural boundary (ADR-0058) rather
than a note left to be silently routed around later.

## Resolution, 2026-09-06 — assisted browsing, not automation

The user's own real decision, following directly from this document's
own finding: JARVIS never scrapes, reads, or extracts a single byte of
listing content from either site. Instead, `job_search.open_results`
(`kernel/job_search.py`, `jarvis job-search "<keywords>" --site
linkedin|indeed [--location <loc>]`) builds a real, correct
search-results URL and opens it in the user's own, real, ordinary
Brave browser (`BravePort`/`BraveCliAdapter` — the same real,
already-live-verified mechanism `desktop.brave_open_url` uses) — a
human does the actual searching, clicking, and reading. This is
exactly the third real option this document's own section 5 gestured
toward without naming: sidestepping the scraping-vs-API tradeoff
entirely rather than choosing between its two named, ToS-conflicted
sides.

**Real, structural enforcement, not just a design intention**: this
capability's own module (`kernel/job_search.py`) never imports
`BrowserAutomationPort` and never calls any content-reading method —
mechanically proven by `tests/meta/test_job_search_no_content_reading.py`,
mirroring `test_job_assistance_no_submission.py`'s own AST-scan
precedent for ADR-0058's identically-shaped guarantee. Automated
listing extraction remains **explicitly out of scope**, not merely
deferred: this document's own "Does foreclose, absent a new decision"
paragraph above still applies in full — building a real content-reading
job-search capability later would still need to resolve the ToS
finding this document already established, not route around it via
this resolution.

**A real, additional finding made while implementing, not anticipated
by this document's own original research**: a live, one-time,
headless-CDP page load (done purely to verify the real URL
query-parameter format, not as part of the shipped capability) showed
LinkedIn's search succeeding but Indeed's request being actively
blocked ("Request Blocked") by Indeed's own bot detection — real,
concrete, runtime evidence reinforcing the ToS/robots.txt finding
above, not just a contractual concern. This is a second, independent
reason `job_search.open_results` deliberately uses the real, ordinary,
non-headless `BraveCliAdapter` rather than `kernel/browser.py`'s
headless `authorize_and_open_page` (which this task's own originating
prompt had named as the reuse target, before this finding surfaced) —
see `kernel/job_search.py`'s own module docstring for the full account
of that deviation.
