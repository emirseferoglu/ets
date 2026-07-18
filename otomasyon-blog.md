# How I’m Using Claude AI to Build a Fully Autonomous Etsy Empire (And You Can Steal the Entire Blueprint) | by Charles Ross | Medium

# How I’m Using Claude AI to Build a Fully Autonomous Etsy Empire (And You Can Steal the Entire Blueprint)

[

![Charles Ross](https://miro.medium.com/v2/resize:fill:64:64/1*NtgFdhW-ialgq3sTUYjhog.png)

](/@charles-ross?source=---byline--bd9bebc3dd1c---------------------------------------)

[Charles Ross](/@charles-ross?source=---byline--bd9bebc3dd1c---------------------------------------)

Follow

18 min read

·

May 8, 2026

111

3

Listen

Share

More

A complete, step-by-step guide to architecting an AI agent system that researches niches, generates designs, writes listings, handles customer service, runs marketing, and tracks performance — all while you sleep.

![](https://miro.medium.com/v2/resize:fit:1400/1*RD-akVw8K1XmYK8tV0Pffg.png)

## Table of Contents

1.  [The Core Premise](https://claude.ai/chat/8dc44cad-0a0d-4218-9d48-203e5b655dac#the-core-premise)
2.  [Step 1 — Locking In the Strategy](https://claude.ai/chat/8dc44cad-0a0d-4218-9d48-203e5b655dac#step-1--locking-in-the-strategy)
3.  [Step 2 — The Agent Roster](https://claude.ai/chat/8dc44cad-0a0d-4218-9d48-203e5b655dac#step-2--the-agent-roster)
4.  [Step 3 — The Image Generation Decision](https://claude.ai/chat/8dc44cad-0a0d-4218-9d48-203e5b655dac#step-3--the-image-generation-decision)
5.  [Step 4 — The Complete MCP Stack](https://claude.ai/chat/8dc44cad-0a0d-4218-9d48-203e5b655dac#step-4--the-complete-mcp-stack)
6.  [Step 5 — Per-Agent MCP Assignments](https://claude.ai/chat/8dc44cad-0a0d-4218-9d48-203e5b655dac#step-5--per-agent-mcp-assignments)
7.  [Step 6 — Local Infrastructure & Folder Structure](https://claude.ai/chat/8dc44cad-0a0d-4218-9d48-203e5b655dac#step-6--local-infrastructure--folder-structure)
8.  [Step 7 — Accounts You Need Before Building](https://claude.ai/chat/8dc44cad-0a0d-4218-9d48-203e5b655dac#step-7--accounts-you-need-before-building)
9.  [Step 8 — The Execution Sequence](https://claude.ai/chat/8dc44cad-0a0d-4218-9d48-203e5b655dac#step-8--the-execution-sequence)
10.  [Step 9 — Realistic Expectations](https://claude.ai/chat/8dc44cad-0a0d-4218-9d48-203e5b655dac#step-9--realistic-expectations)
11.  [Step 10 — Handing Off to Claude Code](https://claude.ai/chat/8dc44cad-0a0d-4218-9d48-203e5b655dac#step-10--handing-off-to-claude-code)
12.  [The Final Truth](https://claude.ai/chat/8dc44cad-0a0d-4218-9d48-203e5b655dac#the-final-truth)

## The Core Premise

I’m building an Etsy print-on-demand store, but I’m not running it myself. I’m building an army of Claude-powered AI agents that handle the entire operation — research, design, listing, SEO, customer service, marketing, analytics. My role is Sovereign: I make the strategic calls, approve the niche, lock in the brand, and let the agents execute.

The whole thing runs on three principles, which I keep referring to as my Claude Code workflow:

1.  **Give goals, not tasks.** Don’t tell agents what to do step-by-step. Tell them the outcome to optimize for.
2.  **Give them a way to verify their own work.** MCP servers — especially Playwright — let agents actually open browsers, navigate sites, and confirm their work was done correctly.
3.  **Tell them not to return control until the goal is met.** Let them iterate to perfection on their own.

This guide walks through every decision and every component. By the end, you’ll have the full architecture and you’ll know exactly what to paste into Claude Code to build it.

## Step 1 — Locking In the Strategy

Before any architecture, you have to be brutally honest about what you’re trying to accomplish. I went through this myself and had to course-correct.

**The questions that actually matter:**

What’s the real goal — profit in the first week, or a working system that compounds? Most people answer “both” and lie to themselves. The truth is, new Etsy shops are algorithmically sandboxed for 2–4 weeks. You will not make meaningful money in week 1 unless you’re running aggressive paid ads. Set the right expectation.

What’s the budget actually look like? Be honest. If it’s $0, you can still build the entire system — but you need to delay launch until you have at least $35–50 for Etsy listing fees, one product sample for photography, and some breathing room. You can architect everything for free, then launch when the money lands.

Which product category? Print-on-demand only is the smart move when starting lean — Printify has zero upfront cost since products only get made when someone orders. Candles require sample purchases ($15–30 each) which eats budget fast. Start with POD, add candles later when you have data.

**My calls:**

-   **Goal:** Build a foundation. Profit comes in weeks 4–8.
-   **Budget:** Build now while waiting on funds. Launch when $35–50 is ready.
-   **Products:** POD only for the first run. Candles later.
-   **Niche:** Let the research agent decide based on live Etsy data — but with strict guardrails so it doesn’t pick something un-winnable.
-   **Branding:** Persona brand. Invent a fictional designer character (e.g., “Maya” the indie artist). Etsy is cracking down on shops that feel inhuman; a persona with a story and an “About” section that reads human survives the crackdown and converts better.

The most important decision here is the persona brand. Etsy’s enforcement specifically targets anonymous AI-feeling shops. A persona-driven shop has a story, a voice, a face, and an aesthetic. It survives.

## Step 2 — The Agent Roster

Eight agents total — one human (me), one commander, six specialists. Lean by design. More agents means more places for the system to break.

SOVEREIGN (you — final approval, niche selection, strategic calls)  
   │  
   └── OVERSEER (commander — coordinates everyone)  
         │  
         ├── ORACLE (research — finds what sells)  
         ├── MUSE (designer — generates artwork)  
         ├── SCRIBE (listings — writes Etsy SEO)  
         ├── SENTINEL (compliance — prevents shop bans)  
         ├── HERALD (customer service — handles messages)  
         ├── LEDGER (analytics — tracks performance)  
         └── EVANGEL (marketing — runs Pinterest + TikTok)

## OVERSEER — The Commander

**Goal:** Run daily and weekly operations autonomously. Coordinate the others. Escalate to me only when human decision is genuinely required.

**MCPs:** Filesystem, Memory, Gmail (for status notifications)

**Self-verification:** Maintains a daily log file. End-of-cycle check confirms every delegated task has a status. Failed tasks retry once or escalate.

**Skills:** Daily standup routine, weekly war room review, escalation protocol, delegation patterns.

**Schedule:** 8 AM standup, 6 PM review, Sunday 5 PM weekly war room.

## ORACLE — The Research Agent

**Goal:** Identify the highest-probability winning niche and product opportunities, based on live Etsy data, and feed validated opportunities to Muse with full creative briefs.

**MCPs:** Filesystem, Memory, Playwright (the critical one — lets Oracle actually navigate Etsy and capture screenshots), Web fetch.

**Self-verification:** Every research output must include direct screenshots and URLs from real Playwright sessions. No verifiable sources, no acceptance.

**Niche selection guardrails (non-negotiable):**

-   Top-10 listings in the niche must average 500+ sales (proven demand)
-   Top 3 shops cannot be mega-stores with brand IP (we need to be able to compete)
-   Designs must be achievable via image generation without copyright risk
-   Average price point must be ≥$15 (margin must exist after Printify costs)
-   Niche must have ≥3 sub-themes for design variation

These guardrails prevent Oracle from picking something theoretically trendy but practically un-winnable.

**Skills:** Etsy bestseller scout method, niche validator, design brief writer, trend monitor, persona naming.

## MUSE — The Designer

**Goal:** Generate Etsy-ready product designs that match Oracle’s briefs and are statistically likely to convert.

**MCPs:** Filesystem, Memory, Playwright (for image generation — see Step 3 for the full decision).

**Self-verification:** Three-gate quality check before any design moves from drafts to approved:

1.  Visual quality check (no artifacts, properly cropped, design feels intentional)
2.  Brief adherence check (does it match what Oracle asked for?)
3.  Originality check (Sentinel-driven reverse image search)

If any gate fails, regenerate. Do not return until all three pass.

**Skills:** Design generation prompts, Printify pipeline, mockup quality check, design variant spinner (once a design works, generate 5–10 variations — color shifts, slight wording changes, holiday versions; this is how solo Etsy shops scale).

## SCRIBE — The Listings Agent

**Goal:** Write Etsy listings that rank in search AND convert browsers to buyers.

**MCPs:** Filesystem, Memory, Playwright (for Etsy listing publish, since Etsy’s API is too restrictive), Web fetch (for keyword research).

**Self-verification:** Pre-publish checklist:

-   Title 120–140 characters, highest-volume keyword front-loaded
-   All 13 tags filled with multi-word phrases
-   Description has the keyword in the first sentence
-   Photos uploaded in correct order (lifestyle hero first, white background second, detail shots after)
-   Pricing is profitable (≥30% margin after Printify cost + Etsy fees)

Skip any of these and the listing fails to publish.

**Skills:** Etsy SEO formula, listing templates per product type, keyword research from competitor listings, the publish flow, pricing strategy.

## SENTINEL — The Compliance Agent

**Goal:** Catch problems before they reach Etsy. Prevent shop suspension, copyright strikes, and listing-quality issues that would tank conversion or get the store banned.

**MCPs:** Filesystem, Memory, Playwright (USPTO trademark search, reverse image search via Google Lens), Web fetch (Etsy policy pages).

**Self-verification:** Sentinel produces pass/fail with specific reasons. Failed items go back to Muse or Scribe with the exact issue. Sentinel maintains a running blocklist of flagged terms, brands, characters, and visual styles to avoid.

**Hard rejection triggers (auto-fail):**

-   Text matches a USPTO live trademark
-   Visual reverse-image score above similarity threshold
-   Niche has been flagged by Etsy policy in the last 90 days
-   Design contains any recognizable real person, sports logo, copyrighted character, brand name, or song lyric

Sentinel is the agent most setups miss. It’s the difference between a shop that lasts and a shop that gets banned in month 3.

## HERALD — The Customer Service Agent

**Goal:** Handle every customer message and review within 4 hours. Maintain 5-star service rating. Escalate only genuinely complex issues.

**MCPs:** Filesystem, Memory, Playwright (Etsy messages access), Gmail.

**Self-verification:** Drafts every response to a log file. In the early weeks, I approve before send. After 30 days of clean approvals, Herald can autonomously send tier-1 messages (shipping/sizing only). Complex messages always require my approval indefinitely.

**Skills:** Customer message templates, review response protocol (5-star: brief warm thanks; 4-star: ask what could be improved; 3-star: apologize and offer fix; 1–2 star: always escalate), Maya’s tone of voice, complaint handling, custom request decline framework.

## LEDGER — The Analytics Agent

**Goal:** Quantify what’s working and what’s not, with specific recommendations for what to change.

**MCPs:** Filesystem, Memory, Playwright (Etsy stats and Printify dashboard), SQLite.

**Self-verification:** Every report includes raw data screenshots and SQL query outputs. No claims without evidence. Discrepancies between Etsy stats and Printify orders flagged for my review.

**Schedule:** Daily 7 PM metrics pull, Sunday 4:30 PM weekly performance review.

**Database tables:** listings, daily\_metrics, orders, pinterest\_pins, agent\_logs.

## EVANGEL — The Marketing Agent

**Goal:** Build and execute the off-Etsy traffic strategy (Pinterest primary, TikTok secondary) without violating any platform’s self-promotion rules.

**MCPs:** Filesystem, Memory, Playwright (Pinterest, TikTok automation), Web fetch.

**Self-verification:** Every pin publishes through Playwright with a confirmation screenshot. Daily log of pins posted, time, board, target listing. Weekly impression and click numbers reconciled against Pinterest analytics.

**Initial scope is intentionally limited:**

-   Set up Pinterest business account
-   Claim domain if I registered one
-   Create 3–5 boards based on niche
-   Schedule 3–5 pins per day from initial listings
-   DO NOT yet aggressively engage, comment on others, or run heavy automation — Pinterest’s algorithm sandboxes new accounts using automation

Pinterest is a 30–90 day game. The early phase is about establishing trust with the platform.

## Step 3 — The Image Generation Decision

This is the single most important infrastructure decision in the build. Get it wrong and you either burn money or break autonomy.

**The reality:** Claude doesn’t generate raster images natively. Claude Pro plans don’t come with image generation that fits POD design needs. I had to choose how Muse generates designs.

**Three real options I considered:**

**Option A — Manual via my ChatGPT Pro account:** Muse generates the prompt, I paste into ChatGPT, save the image, drop it back into the system. Costs $0 extra. Costs me ~2 hours per week of manual work and breaks autonomy.

**Option B — OpenAI API directly:** Muse calls GPT-image-2 via the OpenAI API. Truly autonomous. Costs roughly $3–17/week depending on volume and quality tier. ChatGPT Pro does NOT include API access — that’s a separate billing system that uses prepaid credits. You add $10–20 to an OpenAI developer account, and that funds the image generation. Setup is 15 minutes and TOS-compliant.

**Option C — Playwright drives ChatGPT.com using my Pro session:** Muse opens a real browser, logs in as me, types prompts, downloads images. Costs $0 extra. Has three real risks:

-   TOS violation (OpenAI prohibits programmatic extraction and using ChatGPT to power third-party services)
-   Brittleness (ChatGPT’s UI changes every 2–4 weeks; selectors break; maintenance burden)
-   Slow and resource-heavy (30–60 seconds per image vs. 5–15 seconds for the API)

**My choice:** Option C. I accept the risks because I want to keep the cash spend at zero for the first run, and I’m willing to wear the maintenance burden.

**Safeguards I’m baking in:**

-   Generate no more than 1 image every 60–90 seconds (mimic human pacing)
-   No parallel browser sessions
-   Verify session validity before each generation; if logged out, pause and notify Overseer
-   Use semantic selectors with fallbacks (button text, aria labels) over brittle CSS paths
-   Confirm image actually downloaded at correct resolution before marking complete
-   Quarterly architecture review — if my account survives and the system is stable, great; if it breaks, the data drives the next call

**Honest recommendation if you’re following along:** Option B is the cleaner path. $10–20/month for full autonomy and TOS compliance is genuinely a good deal. I went C because of zero-budget constraints, not because it’s the better architecture.

## Step 4 — The Complete MCP Stack

## Tier 1 — Core Infrastructure (every agent uses these)

**Filesystem MCP** (Anthropic official) — Read/write to project files. How agents share state, write reports, store designs, log decisions. Built into Claude Code.

**Memory MCP** (Anthropic official) — Persistent knowledge graph that survives across sessions. Agents remember decisions, customer preferences, what worked, what failed. Built into Claude Code.

## Tier 2 — Self-Verification Critical

**Playwright MCP** (Microsoft official) — THE most important MCP. Six of eight agents need it. Lets agents control a real browser — open pages, click, fill forms, screenshot, scrape. This is the self-verification layer for almost everything. Install: `npx @playwright/mcp@latest`.

**Puppeteer MCP** (community, backup) — Same category as Playwright with stealth plugins for sites that detect automation. Etsy can be tricky for heavy Playwright automation; Puppeteer is the fallback.

## Tier 3 — External Service Integrations

**Printify MCP** (community) — Direct API access for design upload, product configuration, order management. Several community versions exist on GitHub.

**Etsy access** — No usable official MCP. Etsy’s official API requires manual approval that takes weeks. Workaround: Playwright drives the Etsy seller dashboard. Slower than API but works immediately. Apply for Etsy API access in parallel as a future upgrade.

**Pinterest access** — Playwright-driven. Pinterest’s API doesn’t support marketing automation well.

**TikTok access** — Playwright-driven. TikTok’s API is locked down for marketing.

**Gmail MCP** (community, OAuth-based) — For Herald primarily. OAuth flow once, agent has access from then on.

**USPTO trademark search** — No MCP needed. Web fetch + Playwright against the USPTO TESS database. Free, public.

**Reverse image search** — Playwright-driven. Drives Google Lens or TinEye to catch accidental copying of existing listings or copyrighted artwork.

## Tier 4 — Local Infrastructure

**SQLite** — Ledger’s analytics database. No MCP needed, just Python or Node. Stores listings, designs, performance metrics, customer data, decisions, agent logs. Memory MCP handles unstructured knowledge; SQLite handles structured data. Both are needed.

**Cron / Node-based scheduler** — Triggers Overseer’s morning standup, Ledger’s evening pull, Evangel’s pin scheduler. Without scheduling, the system only runs when manually triggered.

## Step 5 — Per-Agent MCP Assignments

Agent MCPs OVERSEER Filesystem, Memory, Gmail, Cron ORACLE Filesystem, Memory, Playwright, Web fetch MUSE Filesystem, Playwright (ChatGPT image gen), Memory SCRIBE Filesystem, Memory, Playwright (Etsy publish), Web fetch (keywords) SENTINEL Filesystem, Memory, Playwright (USPTO + reverse image), Web fetch HERALD Filesystem, Memory, Playwright (Etsy messages), Gmail LEDGER Filesystem, Memory, Playwright (stats + Printify), SQLite EVANGEL Filesystem, Memory, Playwright (Pinterest + TikTok), Web fetch

## Step 6 — Local Infrastructure & Folder Structure

I’m running this on my local machine for the first run. Free, simple, validates the system before I pay for hosting. VPS migration comes later once the system has proven itself ($5–10/month on DigitalOcean or Hetzner).

**Local machine realities:**

The machine has to be on for agents to run. When the laptop sleeps, Muse stops generating. When Claude Code closes, scheduled tasks pause.

Mitigations:

-   Set the machine to never sleep on AC power
-   Keep Claude Code running in a dedicated terminal window
-   Run agents on a schedule that matches waking hours — don’t try to run a 3 AM task while the laptop is asleep
-   Batch overnight tasks into the morning standup

Internet needs to be stable. Playwright opens real browser sessions; a dropped connection mid-listing-publish leaves a half-finished listing on Etsy. Mitigations: stable connection windows, Sentinel checks every Playwright task completed cleanly, retries on next cycle if not.

Specs barely matter. Anything from the last 4–5 years handles Playwright + Claude Code + a few Node processes fine.

**Folder structure:**

maya-shop/  
├── MASTER\_SPEC.md              \# Source of truth document  
├── .env                        \# Credentials (gitignored)  
├── .gitignore  
├── config.json                 \# System-wide settings  
├── package.json                \# Node dependencies  
├── requirements.txt            \# Python dependencies  
│  
├── agents/                     \# One file per agent's instructions  
│   ├── overseer.md  
│   ├── oracle.md  
│   ├── muse.md  
│   ├── scribe.md  
│   ├── sentinel.md  
│   ├── herald.md  
│   ├── ledger.md  
│   └── evangel.md  
│  
├── skills/                     \# Custom Claude skills, one folder per agent  
│   ├── overseer/  
│   ├── oracle/  
│   ├── muse/  
│   ├── scribe/  
│   ├── sentinel/  
│   ├── herald/  
│   ├── ledger/  
│   └── evangel/  
│  
├── memory/  
│   ├── shared/  
│   ├── sentinel-blocklist.json  
│   ├── persona.json  
│   └── shop-config.json  
│  
├── designs/  
│   ├── drafts/  
│   ├── approved/  
│   ├── published/  
│   └── rejected/  
│  
├── listings/  
│   ├── drafts/  
│   └── published/  
│  
├── research/  
│   └── \[date\]/  
│       ├── niche-analysis.md  
│       └── sources/  
│  
├── analytics/  
│   ├── maya-shop.db  
│   └── reports/  
│       ├── daily/  
│       └── weekly/  
│  
├── content/  
│   └── pinterest/  
│       ├── pins/  
│       └── calendar.md  
│  
├── logs/  
│   ├── overseer-daily.log  
│   ├── agent-actions.log  
│   └── errors.log  
│  
└── scripts/  
    ├── scheduler.js  
    ├── setup.sh  
    └── health-check.js

This structure matters because every agent needs to know exactly where to read from and write to. Clean folder hygiene = clean agent behavior.

## Step 7 — Accounts You Need Before Building

All free at setup. The only money is for Etsy’s small temporary verification hold (refunded automatically) and the optional domain.

Service Cost Purpose Gmail (dedicated to the persona) Free Persona email, OAuth root for everything Etsy seller account Free + $1 verification hold Shop platform Printify Free POD fulfillment Pinterest business account Free Primary off-Etsy traffic TikTok account Free Secondary traffic, future expansion OpenAI / ChatGPT Pro Already subscribed Image generation (via Playwright) Domain (optional) ~$10/year Pinterest claim, brand cohesion

**Process:**

1.  Create dedicated Gmail (e.g., `[shopname].studio@gmail.com` — final name comes after the niche is selected, use placeholder for now)
2.  Set up Bitwarden or another password manager
3.  Enable 2FA on the Gmail
4.  Create Printify, Pinterest, TikTok accounts using that Gmail
5.  Install Claude Code (covered by Max plan)
6.  Install Chrome and log into ChatGPT, check “stay signed in”
7.  Install Node.js and Python (Claude Code can guide you)
8.  Open the Etsy seller account when funds are ready (Etsy requires a payment method for the verification)
9.  Optionally register a domain on Namecheap or Cloudflare (~$10/year)

## Step 8 — The Execution Sequence

This is the hand-off. You build the architecture in chat (with Claude.ai), then you deploy it in Claude Code.

**Stay in chat for:**

-   Agent roster design and naming
-   Each agent’s goal, MCP requirements, skill list
-   Shop positioning, niche strategy, brand identity decisions
-   Design strategy and best practices research
-   Drafting the master spec document

**Move to Claude Code when:**

-   Building the agent system files
-   Setting up MCPs (Playwright, Printify, image generation)
-   Writing the custom skills as actual SKILL.md files
-   Creating automation scripts and scheduled workflows
-   Testing the full pipeline end-to-end with self-verification

The reasoning: Claude Code is built for execution and iteration; the chat is better for strategic thinking and pushback. Doing strategy in Claude Code wastes its agentic loop on conversation. Doing the build in chat wastes time on something Code does better.

**The sequence:**

**Step 1 — Architecture (in chat):** All decisions locked, accounts list compiled, master spec drafted.

**Step 2 — Account setup (you, ~2 hours):** Create accounts, install Claude Code, set up the project folder, install Chrome and log into ChatGPT, install Node.js and Python.

**Step 3 — Funding (when ready):** Funds land. Etsy account opens. Optionally register the domain.

**Step 4 — System build (Claude Code, 1–3 hours):** Open Claude Code, paste the master prompt, walk away. Claude Code reads the spec, installs everything, builds eight agent configurations, builds 40–50 skill files, sets up the SQLite database, runs a smoke test, has Oracle do its first niche research.

**Step 5 — Niche selection (you):** Oracle delivers 3 niche options with persona name candidates. You pick. Persona is finalized — name, age, backstory, aesthetic, brand voice, shop bio.

**Step 6 — First designs (Muse):** Generate 5–8 designs in the chosen niche. Each goes through Sentinel approval. You review the approved set, kill anything you don’t like.

**Step 7 — First listings live (Scribe + Sentinel):** Scribe drafts and publishes 8–10 listings via Playwright on Etsy. Goes slowly — 1 listing every 10–15 minutes to avoid automation pattern detection.

**Step 8 — Marketing live (Evangel):** Pinterest business account claimed, 3 boards created, 5 pin templates built, first week of pins scheduled.

**Step 9 — Volume expansion (Muse + Scribe):** Second design batch focused on variations of any early winners. Listings expand to 16–20 total.

**Step 10 — First review (Ledger + Overseer + you):** Ledger compiles the first report (visits, favorites, conversion, Pinterest impressions). Overseer runs the war room with all agents reporting what worked. You decide what to scale, what to kill, what to test next.

**End-of-first-run deliverable:** Operational system, 20+ live listings, baseline data, plan for the next cycle.

## Step 9 — Realistic Expectations

I’m being straight with you about this because too many people quit after the first week thinking the system failed.

**Likely outcome of the first run: 0–3 sales.** New Etsy shops get heavily sandboxed by Etsy’s algorithm — they show your listings to almost no one for the first 2–4 weeks while they evaluate quality. Even with strong listings and good designs, early organic Etsy traffic will be 5–20 visits per listing, which converts to 0–1 sales per listing across the shop.

**Pinterest is the wildcard.** A single pin can go viral and drive 1000+ visits in a day. More likely: pins build up impressions slowly, real traffic kicks in around weeks 3–4. Don’t expect Pinterest to save the first run.

**The win condition for the first run is NOT sales. It’s a fully operational system.** If at the end you have 20+ live listings, agents running on schedule, baseline analytics flowing, and a plan for the next cycle — that’s success. Sales come from compounding this for 4–8 weeks.

**Realistic revenue arc:**

-   Weeks 1–2: $0
-   Weeks 3–4: First trickle of organic sales, maybe $50–200
-   Weeks 5–8: Pinterest traffic compounds, niche optimization based on data, $300–1000/month range
-   Months 3+: Real scaling decisions, possible ad budget reinvestment, $1000+/month range if niche is right

The hardest part is psychological. Around the time you have 10 listings live and zero sales, you’ll feel like the system isn’t working. It is. Trust the process and let Ledger’s data drive the decisions.

## Step 10 — Handing Off to Claude Code

The Day 3 master prompt is short by design. Goal-based, verification-driven, autonomy-respecting. Here’s the structure of what you’d paste into Claude Code:

**The instruction tells Claude Code:**

1.  **The goal:** Pass the smoke test defined in the master spec. The system is “done” when all smoke test criteria are verifiably met, not when the code looks complete.
2.  **The verification mechanism:** Use Playwright MCP throughout the build to confirm each agent actually works end-to-end. Don’t write code that should work — drive the actual flows and confirm them. For each agent, Playwright is the honesty mechanism: navigate to the real site, capture screenshots as evidence, confirm the action completed.
3.  **The autonomy directive:** Don’t return control until all smoke test criteria pass. If you hit a genuine blocker that requires human input (OAuth confirmation, CAPTCHA, account verification), pause and ask. For everything else — debugging, re-architecting, retrying failed approaches, installing missing dependencies — work through it yourself.
4.  **The order of operations:** Read the spec, set up the folder structure, install all MCPs, set up `.env` with credentials, build agents in dependency order (Overseer → Sentinel → Oracle → Muse → Scribe → Ledger → Herald → Evangel), configure skills directories, set up the scheduler, run the smoke test, have Oracle do its first niche research.
5.  **The constraints:** Image generation is Playwright-driven ChatGPT (TOS risks accepted). No paid actions during build. Sentinel gates all designs and listings. Herald drafts only — I approve before send.

**The smoke test (definition of done):**

1.  Overseer can delegate a test task to each agent and receive completion confirmation
2.  Oracle can navigate Etsy and scrape a top-seller’s listings via Playwright
3.  Muse can drive ChatGPT to produce one test image and download it
4.  Scribe can produce a complete listing draft from a test design
5.  Sentinel can run trademark + reverse image checks on a test design
6.  Ledger can connect to the Etsy seller dashboard
7.  Evangel can authenticate to the Pinterest business account
8.  Herald can monitor the Etsy messages page
9.  All schedules registered in cron with correct next-run times
10.  Each agent has written at least one log line

**What to expect during the build:**

Claude Code runs for 1–3 hours. Reads the spec, installs Node and Python packages, installs MCP servers, opens Chrome via Playwright and asks you to confirm authentication for ChatGPT/Etsy/Pinterest/Gmail (these are the genuine human-in-loop moments), builds 8 agent configuration files, builds 40–50 skill files, sets up the SQLite database, runs the smoke test, has Oracle do its first niche research.

**When Claude Code asks you something:** Only answer what’s asked. If it asks for credentials, give that one credential. If it asks for OAuth, do that one OAuth flow. Don’t volunteer extra context — the spec already has it.

**If Claude Code seems stuck:** Wait at least 10 minutes. Long verification loops are common. If you do intervene, ask “what’s your current goal and what’s blocking it?” — don’t tell it what to do, ask where it is.

**If the smoke test fails:** That’s fine. The failed item is data. The most likely cause is a credential or environmental issue. Provide the missing piece and tell it to continue from where it stopped.

**If Claude Code goes off-spec:** Stop it, point it back to the master spec, remind it the goal is passing the smoke test. The spec is intentionally specific so deviation is correctable.

## The Final Truth

You have to be a good Sovereign for this to work.

Make the niche call when Oracle delivers — don’t agonize for days, the data will tell you in the next cycle. Set the persona — name her, give her a backstory, write her bio yourself if you have to. Kill bad listings without sentimentality — Ledger will tell you which ones are dead. Resist the urge to micromanage the agents — they execute better without me hovering.

The technical system is robust. The agent roster is more complete than what most people building these run with — specifically because Sentinel (compliance) and Scribe (proper SEO) are the two roles most setups skip, and they’re the ones that determine whether your shop survives past month 3.

The real risk isn’t the architecture. It’s me losing patience around week 2 when sales are still zero. The architecture works. The math compounds. The system needs time, not more tinkering.

If you’re following this guide to build your own version, the most important thing I can tell you is this: **the build is the easy part.** Claude Code can do the build in a single session. The hard part is having the discipline to let the system run for 4–8 weeks before judging it.

That’s the whole guide. Build well, sovereign well, and let the agents do the work.

## Embedded Content

---