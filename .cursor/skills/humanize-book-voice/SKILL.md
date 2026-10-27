---
name: humanize-book-voice
description: >-
  Audit and revise LaTeX manuscript prose so it sounds human, warm, and
  professional rather than AI-generated. Covers burstiness, throat-clearing,
  false balance, generic claims, structural repetition, negative-parallelism
  templates, rhetorical scaffolding, significance inflation, callout voice,
  reader empathy, and evidence-calibrated stance. Use when humanizing voice,
  fixing AI-sounding prose, improving readability, authenticity, tone, flow,
  or editorial polish. Pair with check-resource-citations for accuracy.
---

# Humanize Book Voice

## Quick start

From the project root, run the structural tell checker first:

```bash
python3 scripts/check_ai_voice.py
python3 scripts/check_ai_voice.py --verbose
python3 scripts/check_ai_voice.py --strict
```

Then read problem passages **out loud**. If a sentence sounds like a report, a brochure, or a neutral summary — not a steady person explaining something useful — revise it.

**Core rule:** Fix rhythm, structure, and specificity before swapping synonyms. Human voice comes from *how* ideas are arranged and grounded, not from "humanizer" tools or random informality.

For before/after samples in this book's tone, see [examples.md](examples.md).

Related skill: [check-resource-citations](../check-resource-citations/SKILL.md) (accuracy and sourcing).

---

## What "human" means (and what it does not)

Human nonfiction voice is not slang, chaos, or fake imperfection. It is **recognizable judgment under uncertainty**.

Research on machine-generated text shows LLMs leave consistent **stylistic fingerprints**: predictable function-word habits, uniform sentence length, over-connected paragraphs, and filler phrases that add words but not information (McGovern et al., 2025; Bitton et al., 2025). Detectors look at **pattern density**, not one banned word — so the fix is structural, not cosmetic.

Editorial anti-cliche guides converge on a similar practical point: AI writing often gives itself away less through one "bad word" than through a **cluster of habits** — em-dash density, inflated importance framing, canned contrast formulas, forced rhetorical questions, adjective piles, and faux-spiky "sass" that the surrounding prose has not earned.

| AI habit | Human alternative |
|----------|-------------------|
| Uniform mid-length sentences | **Burstiness** — mix short punches with longer, layered lines |
| Formal glue transitions (`Moreover`, `Furthermore`) | **Echo flow** — repeat a key word/idea, or let logic bridge itself |
| Neutral summary of every side | **Calibrated stance** — say what you recommend and why |
| Abstract benefits language | **Concrete scenes** — time, place, sensation, named detail |
| Throat-clearing (`It is important to note`) | **Direct claim** — delete the frame; state the thing |
| Repeated section templates | **Varied shapes** — change openings, list lengths, box types |
| Canned contrast (`It's not X, it's Y`) | **Earned contrast** — use only when the tension matters |
| Forced rhetorical question | **Direct setup** — say the problem instead of theatrically asking |
| Stacked adjectives / inflated stakes | **One precise noun + one real modifier** |

**Human writing is often lower perplexity in word choice but higher burstiness in structure.** Advanced fluency includes confident plain words *and* uneven rhythm. Do not chase "randomness"; chase **specificity + variation + stance**.

---

## This book's target voice

Nonfiction for curious beginners who want science-based, accessible guidance — not hype, mysticism, or bro-ey intensity.

| Dimension | Target | Avoid |
|-----------|--------|-------|
| **Science** | Plain explanations of the claim, the assumptions, and the objections; evidence tiers | Lecturing, jargon stacks, false certainty |
| **Warmth** | Curious, steady, companionable | Hype, guru tone, forced jokes |
| **Evidence** | *Best supported* / *promising* / *personally meaningful* | "Proven forever," equal weight on unequal claims |
| **Concrete** | Composite reader scenarios, a worked objection, a named assumption | Abstract promises, feature lists with no scene |
| **Professional** | Natural contractions; clean sentences | Slang, meme voice, faux memoir |
| **Empathy** | Normalize slow reading, unsettled questions, and the urge to jump to a verdict | Implicit shame, "most people will decide by week X" |

**Recurring humanizing devices in this manuscript:**

- **Beginner Reality Check** — one line that names a common struggle (`Not knowing the answer yet is part of the subject.`)
- **Composite scenarios** — brief imagined readers with plausible constraints, not author autobiography
- **Worked examples** — a trilemma stated in ordinary words, a reference-class choice, an objection in one paragraph
- **Honest tradeoffs** — precision versus fragility in the probability step; depth versus a readable core path

Preserve LaTeX structure. Edit **inner text only** in callout environments (`keytakeawaybox`, `researchnotebox`, `examplebox`, `commonquestionbox`, `safetynotebox`, etc.). Do not remove citations, safety notes, or evidence tiers for smoother prose.

---

## Workflow

Copy this checklist and track progress:

```text
Voice audit:
- [ ] Run scripts/check_ai_voice.py (--verbose)
- [ ] Pass 0: Reader-first scan (aloud)
- [ ] Pass 1: Rhythm & breath
- [ ] Pass 2: Throat-clearing & glue words
- [ ] Pass 3: Specificity & scene
- [ ] Pass 4: Stance, tradeoffs, consequences
- [ ] Pass 5: Structure & repetition
- [ ] Pass 6: Callouts & zone voice (openings, closings, boxes)
- [ ] Pass 7: Voice ↔ evidence alignment
- [ ] Re-run checker; spot-check TTS export if prose changed heavily
```

**Order matters.** Rhythm and deletion passes come before adding new examples. Accuracy pass comes last so confidence language matches sources.

---

## Pass 0: Reader-first scan

Read the section once as a **beginner at 11 p.m.**, not as an editor.

Mark anything that feels:

- **Generic** — could appear in any self-help book
- **Hedged into mush** — "may help," "can be beneficial," "depending on your needs" with no fork in the road
- **Over-confident** — "the science is clear," "this isn't speculation," "proven"
- **Mechanical** — same paragraph shape three times in a row
- **Distant** — no sensory detail, no plausible reader situation

Use the **"anyone could write this" test** (ThinkInPublic / editorial craft): highlight sentences any competent summarizer could produce. Those lines need stance, detail, or deletion — not synonym swaps.

---

## Pass 1: Rhythm and breath

AI drafts tend toward **metronome prose**: similar length, similar syntax, similar stress pattern.

### Fix burstiness

1. Find three consecutive sentences of similar length → shorten one hard or lengthen one with a subordinate clause.
2. Vary **openings** — not every paragraph with `The`, `This`, `In`, or `When`.
3. Allow **one purposeful fragment** per section: `That matters.` `Not always.` `Worth trying.`
4. Break up **idea stacks** — one sentence should not carry four distinct claims unless the list is the point.
5. Read aloud and fix every **wince** — if you run out of air, split the sentence.

### Punctuation tells

- **Em dashes** — legitimate in this book, but high density reads AI-polished. Prefer a period or comma when the aside is not essential. `check_ai_voice.py` warns above ~8 em dashes per 1000 words.
- **Semicolons** — fine sparingly; a chain of them feels academic-robotic.
- **Parentheses** — good for quick asides; a paragraph full of them feels evasive.
- **Do not ban em dashes on sight.** One well-placed dash can sound natural. The tell is **pattern density + sameness of cadence**, not the punctuation mark by itself.

---

## Pass 2: Throat-clearing and glue words

Delete or rewrite **frames that announce importance instead of delivering it**.

### Delete or replace (high priority)

| Throat-clearing / glue | Action |
|------------------------|--------|
| `It is important to note that` | Delete; state the claim |
| `It's worth noting` / `It bears mentioning` | Delete |
| `In conclusion` / `To summarize` / `Overall` (paragraph opener) | Delete; land the point |
| `Furthermore` / `Moreover` / `Additionally` / `Consequently` | Cut or use echo flow |
| `In today's fast-paced world` / `In the ever-evolving landscape` | Delete entirely |
| `When it comes to` / `In the realm of` / `At the end of the day` | Name the topic directly |
| `This chapter aims to explore` | Say what the reader will *do* or *learn* |
| `One might argue` / `It could be argued` | Take a position or cut |
| `In many cases` / `Generally speaking` | Be specific or qualify with evidence |
| `Ever wondered ...?` / `What if ...?` (when instantly answered) | Usually delete and state the setup directly |

### Corporate / AI vocabulary

Swap for plain words unless the term is technical and necessary:

`leverage` → use · `utilize` → use · `delve` → explore, look at · `harness` → use, draw on · `robust` → solid, reliable · `comprehensive` → full, complete · `pivotal` / `crucial` → important, key (sparingly) · `landscape` → field, area · `tapestry` → mix · `multifaceted` → several · `facilitate` → help · `underscore` / `highlight` → show · `navigate` → handle, work with · `testament to` → shows · `game-changer` → cut or be specific · `revolutionary` / `transformative` → cut unless literally true and cited

**Flag frequency, not one-off use.** Science writing may legitimately use `crucial` once; five hits in one chapter is a pattern.

### Contrast-template clichés

These formulas can land once. Repeated use becomes a visible AI rhythm.

- `It's not X, it's Y.`
- `This isn't X. It's Y.`
- `Not just X, but Y.`
- `More than X, Y.`

Use them only when the contrast genuinely sharpens the claim. Otherwise, replace with direct explanation.

### Forced rhetorical questions

Rhetorical questions are not banned. They become AI-sounding when they are used as **scaffolding instead of substance**.

Typical weak pattern:

> What if this question changes everything? The answer is that the simulation hypothesis has many consequences.

Better:

> The simulation hypothesis can feel enormous, but most readers meet something smaller first: one claim, three assumptions, and a probability step that is easier to state than to trust.

If a question is followed immediately by the answer, cut the question unless it adds tension, surprise, or reader recognition.

### Stacked adjectives and significance inflation

AI drafts often try to sound vivid by piling modifiers onto generic nouns.

- `powerful, transformative, deeply meaningful practice`
- `remarkably important, incredibly useful, highly effective method`
- `fascinating, multifaceted, compelling phenomenon`

Fix by:

1. Keeping the strongest noun
2. Cutting to one modifier at most
3. Replacing intensity with evidence, scene, or consequence

Example:

> `a powerful, transformative, deeply insightful experience`

becomes

> `an experience some readers remember for years`

### Forced sass / performative edge

Some AI writing tries to sound human by injecting attitude the surrounding prose has not earned.

Watch for:

- `Let's be honest.`
- `Nope.`
- `Here's the thing.`
- `Spoiler:`
- winky dismissals or fake contrarian voice

This manuscript allows **light warmth**, not snark performance. If a sentence sounds like a social post wearing a nonfiction costume, flatten it back into steady judgment.

### Echo transitions (preferred)

Instead of `Moreover, the assumptions feed the probability step`:

> Substrate independence is one assumption the argument needs. If that assumption fails, the probability step has less to stand on.

The second sentence **echoes** "assumption" and advances the logic without a formal connector.

---

## Pass 3: Specificity and scene

Replace abstract claims with something a reader could **picture, try, or verify**.

### The specificity ladder

1. **Abstract (weak):** "This technique can significantly improve your results."
2. **Behavioral (better):** "After one careful pass, many readers can name the three assumptions the argument needs."
3. **Scene (best for this book):** "Maya writes the trilemma on a card, then notices she has been treating a film plot as if it were the third assumption."

### Nonfiction scene tools (no fake memoir)

Use devices the author can stand behind:

- **Composite mini-scenes** — `Imagine a reader starts by mixing up three different claims...`
- **Sample artifacts** — a three-line trilemma, a reference-class note, an objection in the margin
- **Sensory anchors** — `a marked paperback`, `a paused film`, `a notebook with three columns`
- **Named constraints** — commute, short evenings, a background in physics or none
- **Numbers when sourced** — keep cited figures; soften unsourced precision (`almost certainly simulated` → `the argument's own probability, which still depends on the assumptions`)

### Show before explain

Place the reader in a moment first; interpret second. If a paragraph opens with definition + benefits + research, consider flipping: **moment → meaning → evidence**.

---

## Pass 4: Stance, tradeoffs, and consequences

AI defaults to **false balance** — every option presented evenly, no cost named, no recommendation.

### Add stance (calibrated)

This book should **recommend a path** while honoring variation:

- Say what works **first** for most beginners (the claim, then the assumptions, then what would count as evidence)
- Say what to **skip or defer** (optional depth, nested-simulation puzzles, physics metaphors)
- Disagree with common bad advice when the evidence supports it

### Name tradeoffs

Every strong technique should admit a cost:

| Move | Gain | Cost |
|------|------|------|
| Stating the trilemma early | A shared target | Readers may treat it as a verdict |
| A numeric probability | A feeling of precision | The number is only as strong as the reference class |
| Optional physics clues | Extra depth | Easy to confuse metaphor with evidence |

### Add consequences

After advice, add one line on **what happens if ignored** or **what success looks like at week two** — not fear-mongering, just orientation.

### Hedging: two failure modes

- **Over-hedge:** "may possibly sometimes help some individuals" → say what the evidence supports
- **Under-hedge:** "proven," "guaranteed," "the neuroscience is clear" → match source strength (see Pass 7)

### Significance inflation

AI prose often inflates importance instead of proving it:

- `This is a crucial, game-changing insight`
- `This powerful method can transform your life`
- `This underscores the profound importance of ...`

Preferred replacements:

- Name the actual consequence
- Name the evidence tier
- Name the practical use

Example:

> `This is a crucial technique for success.`

becomes

> `This technique matters because without recall, you have nothing to work with the next morning.`

---

## Pass 5: Structure and repetition

Human chapters **vary shape**. AI chapters repeat the same scaffolding.

### Break mechanical patterns

- Identical section arcs (setup → three bullets → summary) chapter after chapter
- **Rule-of-three** every time — use two or four items when that fits
- Parallel subsection titles (`Understanding X`, `Implementing X`, `Mastering X`)
- Back-to-back lists with the same rhythm
- Every chapter opening with a rhetorical question + definition + "In this chapter"

### Paragraph-level variety

Mix:

- Short declarative paragraph
- Paragraph built around one example
- One-item emphasis paragraph (`That is the whole habit.`)
- Research note or callout (not every section)

### Repeated openings

`check_ai_voice.py` flags three consecutive paragraphs starting with the same word (except common ones like `the`, `this`, `if`). Rewrite openings or merge paragraphs.

---

## Pass 6: Zone voice (LaTeX-aware)

Different **zones** need different warmth/precision balances.

### Chapter openings

Strong pattern in this book: **sensory waking moment → familiar frustration → plain promise**.

Weak pattern: definition → history → "This chapter will explore..."

Add early **Beginner Reality Check** when the topic sets high expectations (a final answer, a precise probability, a 30-day plan).

### Chapter closings

End with **curiosity and next step**, not identity pressure (`believing this becomes who you are`). Prefer: which assumption to reread, what an unsettled question feels like, what to read next.

### Callout boxes

| Environment | Voice goal |
|-------------|------------|
| `keytakeawaybox` | One plain sentence the tired reader remembers |
| `researchnotebox` | Calibrated, cited, no lecture tone |
| `examplebox` | Concrete, named constraint, low-effort path |
| `commonquestionbox` | Direct Q → short A; no prefatory fluff |
| `safetynotebox` | Clear, kind, non-alarmist; never softened for flow |

**Stacked callouts:** four identical environments in a row reads templated. Interleave with prose, or vary box type. `check_ai_voice.py` flags 4+ stacked identical `*box` environments.

Vary **first words** inside boxes — not every box starting with `The` or `Key takeaway:`.

### Extracurricular chapters (`backmatter/extracurricular-*.tex`)

Can be slightly more exploratory in tone but **not** casual at the expense of precision. Keep evidence tiers; do not drop citations for smoother prose.

### Transitions between chapters

One sentence of **signposting** helps humans too: what the last chapter built, what this one adds. Avoid template lines repeated verbatim across chapters.

---

## Pass 7: Voice ↔ evidence alignment

Voice and credibility are one system. A warm sentence that overstates research still fails.

Before finalizing a revision:

1. Does confidence language match the cited source tier?
2. Did smoothing delete a necessary qualifier (`pilot`, `lab setting`, `correlational`)?
3. Are medical/safety claims still intact in `safetynotebox`?
4. Did a composite example imply a universal outcome?

If prose and evidence conflict, **soften prose or fix citation** — see [check-resource-citations](../check-resource-citations/SKILL.md).

Common manuscript fixes from editorial review:

- `This isn't speculation` → `Current evidence suggests...`
- `The neuroscience is clear` → `Research strongly supports...`
- `Most people will by week X` → `Many readers notice...` / `Some people find...`
- Absolute therapeutic claims → tool-in-context + professional-care disclaimer

---

## AI tell hunt list

Run `python3 scripts/check_ai_voice.py --verbose` first. Treat hits as **review candidates**, not automatic errors — flag **frequency and clustering**, not a single legitimate use.

### Checked by `scripts/check_ai_voice.py`

Patterns are grouped in the report. Per-file thresholds:

| Category | Threshold | Examples |
|----------|-----------|----------|
| **AI vocabulary** | 2+ hits | `Furthermore`, `Moreover`, `Additionally`, `Consequently`, `delve`, `landscape`, `robust`, `comprehensive`, `pivotal`, `crucial`, `leverage`, `utilize`, `multifaceted`, `tapestry`, `game-changer`, `facilitate`, `elucidate`, `paradigm`, `myriad`, `seamless`, `underscore`, `testament to`, `navigate the`, `holistic`, `cutting-edge`, `revolutioniz*`, `transformative` |
| **Throat-clearing** | 1+ hit | `It is important to note`, `It's worth noting`, `Generally speaking`, `In many cases`, `One might argue`, `This chapter aims`, `In today's`, `ever-evolving`, `fast-paced world`, `When it comes to`, `At the end of the day`, `That being said`, `double-edged sword`, `plays a crucial/vital/pivotal role`, `In order to`, `underscores the importance`, `In the realm of`, `To summarize` |
| **Template framing** | 2+ hits | `In plain language`, `That is a useful`, `This chapter lives outside`, `For many beginners`, `The key takeaway is`, `This chapter will explore` |
| **Contrast templates** | 2+ hits | `It's not X, it's Y`, `This isn't X. It's Y.`, `not just X, but Y` |
| **Overclaim** | 1+ hit | `This isn't speculation`, `The neuroscience is clear`, `proven forever`, `fully proven`, `guaranteed to`, `without a doubt` |

Override vocabulary sensitivity: `python3 scripts/check_ai_voice.py --glue-threshold 3`

Pattern definitions live in `scripts/check_ai_voice.py` — keep script and skill in sync when adding tells.

### Structural tells (automated)

| Signal | Tool | Action |
|--------|------|--------|
| AI vocabulary density | `check_ai_voice.py` | Rewrite or cut |
| Throat-clearing / overclaim | `check_ai_voice.py` | Delete frame or soften claim |
| Template framing repeats | `check_ai_voice.py` | Vary meta-framing across chapters |
| 3+ same paragraph openings | `check_ai_voice.py` | Merge/vary |
| Em-dash density ≥ 8/1000 words | `check_ai_voice.py` | Split sentences |
| 4+ stacked same callout | `check_ai_voice.py` | Interleave prose / vary box type |

### Manual tells (review even if checker is quiet)

These are high-signal patterns from editorial anti-AI style guides, but they still need judgment:

- **Forced rhetorical questions** — especially when immediately answered
- **Stacked adjectives / intensifiers** — three modifiers where one concrete noun would do
- **Significance inflation** — everything framed as profound, powerful, transformative, crucial
- **Forced sass** — attitude spikes not supported by the surrounding chapter voice
- **Buzzword clusters** — multiple giveaway terms in one paragraph even if each term appears only once

### Manual ripgrep (optional deep audit)

For patterns not yet in the checker, or editorial spot-checks:

```bash
rg -n 'current evidence suggests|Research note:|Most people will by week|the science is clear|Ever wondered|What if .*\\?|Let''s be honest|Spoiler:|not just .* but|It''s not .* it''s' chapters backmatter --glob '*.tex'
```

`In plain language` and similar meta-framing can be useful once; repeated across chapters it becomes a **template tell** (now flagged at 2+ per file).

---

## Scoring rubric alignment

Prioritize revisions that move these rubric dimensions (see `book_scores.json`):

| Dimension | Humanizing lever |
|-----------|------------------|
| **Authentic Voice & Tone** | Burstiness, less template polish, plain words |
| **Engaging Storytelling** | Composite scenes, worked examples, one-claim arcs |
| **Reader Empathy** | Beginner Reality Check lines, normalize struggle |
| **Credibility & Accuracy** | Pass 7 — stance without overclaim |
| **Clarity & Accessibility** | Cut throat-clearing; one idea per breath |

The manuscript's main gap is not "more exciting" — it is **more grounded, precise, and memorable** without losing warmth.

---

## Agent revision prompts

When rewriting a flagged passage, use constraints like:

- "Rewrite with one fragment, one sentence under 8 words, one over 25 words; no Furthermore/Moreover; keep all `\cite{}` keys."
- "Replace abstract benefits with a 3-sentence composite scene; no new factual claims."
- "Take a stance: recommend X for most beginners, name one cost, one alternative."
- "Cut 20% word count; remove throat-clearing; keep the research note factual tier."

**Leave holes intentionally:** if a personal author anecdote would help but was not supplied, insert `[AUTHOR STORY NEEDED]` rather than inventing memoir.

---

## Report format

Return findings in this structure:

```markdown
## Voice audit summary

**Structural check:** pass / warnings / hard issues
**Files reviewed:** ...
**Read-aloud spot-check:** ...

### Critical
- [file:line] Passage ... — sounds robotic because ... — suggested rewrite ...

### Suggestions
- [file:line] Pattern ... — frequency ... — fix strategy ...

### Passed spot-checks
- ...

### Evidence-voice flags (coordinate with citations)
- [file:line] Overconfident phrasing vs source tier ...
```

Prioritize passages that undermine **Authentic Voice & Tone** or **Engaging Storytelling**.

---

## Do not

- Run text through synonym spinners or commercial "AI humanizer" tools
- Add fake typos, random slang, or forced irreverence to "sound human"
- Invent author memoir, credentials, or "I remember when..." unless the author supplied it
- Invent study results, success rates, or reader outcomes
- Remove citations, safety notes, or evidence tiers for smoother prose
- Make extracurricular chapters casual at the expense of precision
- Optimize for detector evasion instead of reader trust
- Replace one AI template (`In conclusion`) with another (`The key takeaway is`)

---

## Pair with citations

Voice and accuracy work together. If a sentence sounds confident but the source is tentative, soften the prose **and** check the citation.

Workflow for high-stakes chapters (the probability argument, objections, ethics, physics clues):

1. Humanize voice (this skill)
2. Verify claim-source fit ([check-resource-citations](../check-resource-citations/SKILL.md))
3. Re-read aloud once more

---

## Reference notes

Stylometric fingerprints and burstiness are discussed in McGovern et al. (2025), *Your Large Language Models Are Leaving Fingerprints*; Bitton et al. (2025), *Detecting Stylistic Fingerprints of Large Language Models*; and Pangram Labs on limits of perplexity-only detection. Editorial craft synthesis aligns with common developmental-editor practice: read aloud, cut glue, add specificity, take stance, vary structure.

Practical anti-cliche additions in this skill were informed by the user-supplied editorial resources: `tropes.fyi` (AI cliché catalog and contrast-template warnings), Geri Mileva on AI writing patterns to avoid (em-dash density, rhetorical scaffolding, significance inflation), Stackedo on dead-giveaway AI words and plainer substitutions, and Hunting the Muse on robot-style tells such as buzzword clusters, cliché phrasing, and forced sass.
