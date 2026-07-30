# Phase 0.5: Knowledge Sync & Mental Modeling

## The Pivot

We will NOT write the analysis tools (`analyze_track.py`) or lock the schemas until we have extracted the mental models of top neurofunk producers. If we build the tools before understanding the workflow, we will end up rewriting all the data schemas when we discover new routing tricks on the way.

## The Objectives

Before reverse-engineering tracks, we must extract actionable philosophies from multiple sources — this is an ongoing intake, not a one-time pass on a single course:

- **Producer courses / workshops:** Start with ABIS (June Miller) Start-to-Finish, but treat it as the first entry, not the reference. Every subsequent course or workshop (any producer, any platform) goes through the same pipeline below and gets tagged `producer_course` per `docs/BLUEPRINT.md` §3.
- **Top Producer Ableton Projects:** Analyzing actual routing chains, group structures, and layer separation (Sub vs. Body vs. Movement).
- **Serum 1 & 2 Presets:** Extracting oscillator strategies, routing matrices, and modulation paths — not just saving sounds.

New sources are added to this list over time; the pipeline stays the same regardless of which course or producer it is.

## The Workflow (Mobile-First Knowledge Capture)

Because knowledge gathering happens while watching courses or opening projects, we use GitHub Issues as our "Inbox."

1. **Capture:** While watching a video or looking at an Ableton project, take a screenshot or write a quick note.
2. **Inbox:** Create a GitHub Issue in `npos-v2` with the screenshot and a 1-sentence summary.
3. **Process:** The AI (Architect/Analyst) reads the Issue and translates the raw note into strict NPOS Markdown, mapping it to our controlled vocabularies (e.g., `layer_function`, `body_design`).
4. **Store:** The formatted knowledge is saved into `knowledge/producers/` or `knowledge/principles/`, then the source Issue is closed with a link to where it landed.

## Success Metric for Phase 0.5

- We have documented at least 3 core routing/layering principles, sourced from at least one producer course (ABIS or otherwise).
- We have analyzed the Ableton routing of at least 2 top producers.
- We have extracted strategies from 10 key Serum presets.
- Our `docs/BLUEPRINT.md` schemas are updated to reflect these real-world workflows before we write a single line of Python.
- No single course or producer is treated as the final word — each new source is expected to revise or extend `knowledge/principles/` and `knowledge/archetypes/`.
