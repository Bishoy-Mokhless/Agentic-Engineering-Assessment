# AI usage

How I used AI tools on this assessment: what they did, the prompts that steered them, what I decided, what I rejected or changed, how
outputs were verified, what went wrong, and what risk remains. The full record of every decision is in
[`docs/decision_log.md`](docs/decision_log.md); its entries marked **"AI_USAGE note"** are the sources for
this page. No full transcripts are included.

## 1. Tools

| Tool | Used for |
|---|---|
| **Claude Code** (Anthropic, Claude models) | The coding agent: analysing the brief and data, proposing options, implementing each step, writing tests, running the pipeline and the browser checks. |
| **ChatGPT** | Explanations and second opinions on concepts (e.g. statistics terms, study approach). **No code and no data were shared**; only questions and confirmations. |
| **Web search** (Stack Overflow, GeeksforGeeks) | General data-handling topics (pandas, dates, CSV handling). |
| **Provider websites** | Checking licences, dataset codes and publication behaviour directly at Eurostat and the World Bank. |

**Sensitive information:** none was sent. The workforce data is synthetic and fictional; the external data is
public; no secrets or credentials exist in the project.

## 2. My operating loop

1. **Decomposition.** The agent analysed the brief and proposed a full plan. I did not accept its defaults
   silently: I required **every part as a multiple-choice question that I decide** (D-00), in rounds of up
   to four questions (Rounds 0–8: stack, data quality, metric definitions, sources, time alignment,
   analysis, structure, reliability).
2. **Evidence before decisions.** For data choices I required the **actual problem rows**, not only counts
   (D-06). This exposed the key pattern of the dataset: 12 of 13 exits with a blank type are **exactly 90
   days** after hire (D-10).
3. **Everything recorded.** Each decision is logged with the options, the agent's recommendation, my
   choice and the reason (D-15), so I can defend it and so this page is traceable.
4. **One step at a time.** Implementation ran in 9 steps; after each step the agent recapped what was built
   and linked the code to decision numbers (D-52). Commits happened only after my OK (D-53, later D-81).
5. **Critical review.** After the first step I reviewed the whole design and issued superseding
   instructions (Round 10, D-54…D-63).
6. **Delegation with a record.** For the API, dashboard and UI tests (Steps 6–8) I let the agent build
   without per-step questions, but every small choice it made was logged as an "agent choice" with the
   alternatives, so I could review or reverse it (D-82).
7. **Audit.** Before finishing, the agent ran a browser sweep of 198 dashboard states; I decided which
   findings to fix (Step 9 audit, D-90…D-93).

## 3. Representative prompts

Short versions of instructions that shaped the work (the full wording is in the decision log's "What I said"
lines). They are task descriptions and corrections, not one-shot "build it" requests.

| What I asked | What it controlled | Decision |
|---|---|---|
| "The plan is good, but I want every part presented as a multiple-choice question so I make the decision." | Decisions stay mine; the agent proposes options with a recommendation | D-00 |
| "Before each data decision, show me the actual rows or examples so I can decide." | Evidence before choices; exposed the 90-day exit pattern | D-06, D-10 |
| "Record each decision … with the available choices, what I chose, and any custom answers." | A traceable log for review, this page and the presentation | D-15 |
| "No GitHub Actions, only local tests run manually. CI is over-engineering at this stage." | Scope control within the timebox | D-64 |
| "Check and test each step on its own, make sure everything works, and commit and push each step separately." | A verification gate per step when I delegated Steps 6–8 | D-82 |
| "The old design is better … keep the old one but have the sections split by colours and add more descriptions." | Rejecting agent output after seeing it running | D-85 |
| "The segment filter should allow filtering on several fields together … without adding 4–5 more dropdowns." | A usability requirement stated by me, built test-first | D-86 |
| "Make the senior levels a setting … Only the setting: no dashboard filter." | An open business assumption made configurable, scope kept small | D-94 |

## 4. Which tasks the agent did, which decisions stayed mine

| The agent did | I decided |
|---|---|
| Profiled the data and proposed options for each question | Every metric definition, cleaning rule, source, lag rule, analysis method and scope cut (the ✅ choices in the log) |
| Wrote the code, SQL, tests and dashboard | The emphasis, the stack, the architecture shape, the statistical framing and the wording rules |
| Fetched and parsed the provider APIs; measured publication lags | Which indicators represent which "lens", and the lag rule (D-24…D-29) |
| Ran the pipeline, tests and browser checks; proposed fixes | Which findings to fix and how (D-90…D-94), and when to revert (D-85) |

## 5. Suggestions I rejected or materially changed

| Decision | The agent suggested | What I did instead | Why |
|---|---|---|---|
| **D-01** Emphasis | Data emphasis | **Software** emphasis | It matches my background and what the company asked for |
| **D-04** Dashboard | Streamlit | **Plain HTML + JS + Chart.js** | Closest to the brief's "HTML"; full control over accessibility |
| **D-05** Data feed | Static JSON files | **A small FastAPI service** | Filters can be combined freely; a real service boundary to test |
| **D-10** 90-day exits | Treat them as placeholders ("statistically impossible") | **Quarantine** them and test their impact | Suspicious is not proof; delete nothing, guess nothing |
| **D-12** Blank "regretted" | Count unknown as "not regretted" in the main number | Keep **UNKNOWN**; count only TRUE; worst case as sensitivity | A blank is not a "no" |
| **D-35** Which objectives to test | Test only new-hire retention | Test **all three**, with a clear primary / secondary hierarchy | Show the limitations with data, not only state them |
| **D-36** Senior grain | Year only | Year **and** the quarterly view shown as descriptive | Make the noise visible |
| **Round 10** Statistics | 8-test Holm families (pooled + within-country) | **4 formal within-country tests** per objective; pooled only descriptive; strict associative wording | Mixing countries mostly measures country differences |
| **D-51 / D-60 / D-64** CI | Add GitHub Actions | Deferred; added, then **reversed** on scope | A deliberate timebox; tests run locally |
| **D-65** HR files | Copy and keep the original | Move into `data/raw/hr/` with checksum verification | One copy, verified |
| **D-84 → D-85** Dashboard look | A distinctive redesign (from a design guideline) | **Rejected after seeing it running**; kept only the content improvements | For reviewers, familiar and clear beat distinctive |

## 6. How outputs were verified

- **Tests.** 186 tests: unit, API (FastAPI's TestClient on data built by the real offline pipeline) and
  Playwright in a real browser. In Steps 2–8 tests were written alongside each step; for all later dashboard
  and data changes (D-84 onwards) tests were written **first and seen failing** before the code.
- **Tests that can fail.** Two deliberate breakages of the dashboard were introduced to confirm the UI
  tests catch them (1 and 5 tests failed), then restored (Step 8).
- **Independent recomputation.** Preview statistics were always labelled "preliminary" until the real
  pipeline reproduced them. This caught a wrong preview number (C-01, below).
- **Source evidence, not memory.** Licences were checked on the providers' own pages; the publication lags
  were **measured** from what each API actually returned (D-29); the agent's **guessed** job-vacancy code `JOBRATE`
  returned HTTP 200 with zero values; listing the dataset's real dimensions gave `JVR` (D-26). "HTTP 200 with
  no observations" is now treated as a failure in code.
- **Reconciliation and contracts.** 2,407 HR rows reconcile to 2,400 employees; every table passes a schema
  contract before it is written; every layer has a lineage record with checksums.
- **Looking at the real page.** Dashboard issues were found by opening the running page and by an automated
  sweep of 198 states, not only by tests.

## 7. Failures and manual corrections (not hidden)

- **C-01, a wrong statistic from the agent.** A preview showed Romania's 2021 regretted turnover above the
  target; the real pipeline, with correct window boundaries, gave 6.6%, not 8.3%. The candidate finding was
  **withdrawn** and boundary tests were added.
- **A wrong test expectation.** A market-context test claimed unemployment "fell in 6 of 6 countries"; checking
  the data showed Romania **rose** (6.0 → 6.1). The test and the page were corrected ("5 of 6").
- **Bugs found in the running product:** a segment with no hires returned HTTP 500; a FastAPI parameter object
  shared between `year_from` and `year_to` made a reversed range return 200; the year filter did not reach the
  headline number and one sentence mixed two time ranges (Step 9 audit). All fixed with regression tests.
- **A reverted design.** The D-84 redesign was rolled back (D-85); dark mode was removed (D-83).
- **Tooling problems:** a silent `pip install` hang (re-run with visible output); schema contracts stopping
  runs on wrong integer types from DuckDB (fixed in SQL); Windows line endings breaking an edit script; a slow
  statistics call found by profiling and cached.

## 8. Remaining risk

- **Most code was written by the agent.** I am new to this Python stack (D-00). My mitigation: every
  behaviour-defining choice was mine and is logged; tests pin the rules; I reviewed each step's recap and
  studied the code file by file with plain-language walkthroughs before the interview.
- **Assumptions not confirmed by the business** (senior definition, `Sr Mgmt`, the 90-day exits, the
  population since 2020). They are documented and, where possible, shown not to change the verdicts
  (D-10 sensitivity, D-94).
- **Statistics on small, dependent samples;** today's APIs return revised values, not historical vintages
  (see the README's limitations).

**Effort:** about 30 hours over 4 days.
