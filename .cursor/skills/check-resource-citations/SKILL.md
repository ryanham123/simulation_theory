---
name: check-resource-citations
description: >-
  Audit LaTeX citations and bibliography entries in The Simulation Question.
  Validates \\cite keys against backmatter/references.tex, finds orphans and
  undefined keys, and reviews whether cited sources support nearby claims.
  Use when checking references, citations, bibliography, source accuracy,
  research notes, or before publishing/revising manuscript claims.
---

# Check Resource Citations

## Quick start

From the project root, run the structural checker first:

```bash
python3 scripts/check_citations.py
python3 scripts/check_citations.py --verbose
```

Fix **undefined** and **duplicate** keys before doing deeper review. Orphan `\bibitem` entries are warnings unless the user wants them kept for future use.

## Project conventions

- Bibliography lives in `backmatter/references.tex` as manual `\bibitem{key}` entries inside `\begin{thebibliography}`.
- Manuscript files cite with `\cite{key}` or `\cite{key1,key2}`.
- Keys use lowercase author-year slugs (e.g. `bostrom2003simulation`).
- Research callouts use `\begin{researchnotebox}...\end{researchnotebox}`; safety claims may use `\begin{safetynotebox}`.
- This book distinguishes **well supported**, **promising but limited**, and **exploratory** claims. Citations must match that confidence level.

## Workflow

Copy this checklist and track progress:

```text
Citation audit:
- [ ] Run scripts/check_citations.py
- [ ] Fix undefined / duplicate keys
- [ ] Decide what to do with orphan bibitems
- [ ] Review high-stakes claims against sources
- [ ] Check research-note wording vs evidence strength
- [ ] Re-run checker and build PDF if needed
```

### Step 1: Structural validation

Run `python3 scripts/check_citations.py`.

| Result | Action |
|--------|--------|
| Undefined key | Add `\bibitem{key}` to `backmatter/references.tex` or fix the typo in `\cite{...}` |
| Duplicate `\bibitem` | Remove or rename the duplicate entry |
| Orphan `\bibitem` | Remove it, cite it somewhere relevant, or leave intentionally (note why) |

When adding a source, match existing formatting in `references.tex`: author, year, title, journal/book, volume/pages. Place it in the appropriate group (core evidence, review articles, pilot studies, historical context).

### Step 2: Locate claims that need sources

Search for passages that make empirical, medical, or quantitative claims:

```bash
rg -n 'Research note|study|research|evidence|meta-analysis|found that|suggests|percent|trial|fMRI|REM' chapters backmatter --glob '*.tex'
rg -n '\\cite\{' chapters backmatter --glob '*.tex'
```

Prioritize:

1. `\begin{researchnotebox}` blocks
2. Statistics, success rates, and “studies show” language
3. Medical/safety claims (sleep meds, supplements, trauma, sleep loss)
4. Technology accuracy claims (wearables, apps, cues)
5. Historical attributions (Aristotle, Tibetan sources, etc.)

### Step 3: Claim-to-source fit

For each cited passage, verify:

1. **Relevance** — the source actually discusses the claim’s topic
2. **Strength match** — do not cite a pilot study as if it were settled consensus; do not cite a review when a primary study is needed for a specific number
3. **Scope match** — lab findings are not automatically home-practice guarantees; athlete samples are not general-population proof
4. **Recency/fit** — prefer the book’s existing grouped “core beginner evidence” when supporting core methods (MILD, WBTB, recall, incidence)

Flag mismatches as:

- **Critical**: claim overstates what the cited paper supports
- **Suggestion**: citation is directionally fine but vague, outdated, or better replaced
- **Missing citation**: strong factual claim with no `\cite{...}` nearby

### Step 4: Orphans and missing coverage

- **Orphan bibitems**: either cite them where relevant or remove dead entries
- **Missing citations**: add `\cite{key}` near the claim and a matching `\bibitem`
- **Uncited paraphrases**: if a paragraph clearly depends on one paper, cite it

### Step 5: Report format

Return findings in this structure:

```markdown
## Citation audit summary

**Structural check:** pass / fail
**Files reviewed:** ...

### Critical
- [file:line] Claim ... — issue ... — suggested fix ...

### Suggestions
- ...

### Orphans / cleanup
- ...

### Passed spot-checks
- ...
```

## Common issues in this repo

- Citing a **survey** for a narrow numeric claim — verify the survey actually contains the number, or cite the primary source.
- Mixing **tentative** sources with beginner-facing certainty — soften prose or move the claim to an optional chapter.
- **Physics clues** must stay tied to the specific result being discussed, not to a pixel metaphor.
- **Probability figures** must stay attached to their reference class and assumptions.
- **Historical and fictional sources** are context, not empirical proof — wording should say so.

## Adding a new source

1. Choose a unique key: `authorYYYYshorttopic`
2. Add `\bibitem{key}` to `backmatter/references.tex` in the right section
3. Add `\cite{key}` beside the claim in the chapter `.tex` file
4. Re-run `python3 scripts/check_citations.py`
5. If references are exported to TTS, re-export only if the user asks — references are skipped by default in `export_tts_text.py`

## Do not

- Invent DOIs, page numbers, or study results
- Replace missing citations with vague “research shows” language
- Delete orphan bibitems that the user may be about to cite without confirming
- Treat extracurricular chapters as exempt from evidence standards — they still need accurate sourcing

Related skill: [humanize-book-voice](../humanize-book-voice/SKILL.md) (prose voice and readability).
