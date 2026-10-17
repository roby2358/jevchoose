# jevchoose

A choose-your-own-adventure novella that nobody chooses. A writer model drafts
each section and the three options at the end of it; [Jev](https://typesafe.ai)
— a TypeSafe System One model — reads the story so far and picks one. Ten
sections later you have a finished tale and a log of every decision with the
probability Jev gave each option.

The point is the reader, not the writer. Jev's instructions are part of the
story file, so the same opening told under different picking rules becomes a
different story.

## How a run works

Each section takes three calls:

1. **Prose** — the writer model gets the voice, the prose rules, the story so
   far and the option the reader took, and writes a section that ends at the
   moment the hero must decide.
2. **Choices** — a second call turns that decision point into exactly three
   numbered options.
3. **Jev** — the story state (prose, section number, stage, the three options)
   goes to `system_one` as a `Choice` question. Jev returns a pick, a
   confidence and a probability per option.

The section's stage shapes both the writing and the picking: sections 1–8
**build**, section 9 **wraps** the crescendo, section 10 **seeds** the next
story in the series.

Every run starts from scratch and overwrites `story_<name>.md`. Nothing else
is written to disk, and the file is rewritten after each section, so you can
read along while it runs.

## Setup

```sh
just setup     # .venv with typesafe_sdk
```

Keys go in `.env.secure`, beside `driver.py` or one directory up (gitignored):

```
JEV_KEY=...                # or TYPESAFE_API_KEY
OPENROUTER_API_KEY=...
```

## Use

```sh
just stories             # list the open_*.md you have
just run nightfall       # write all ten sections -> story_nightfall.md
just upto nightfall 3    # write only the first three
just show nightfall      # print the story
just jev nightfall       # just Jev's picks and probabilities
```

The writer model is `mistral` (`mistralai/mistral-medium-3-5`) by default;
`MODEL=sonnet just run nightfall` switches to `anthropic/claude-sonnet-5`, and
any OpenRouter id works in its place. `PYTHON=...` overrides the interpreter.

Or without `just`:

```sh
.venv/bin/python driver.py --model mistral --story nightfall run
```

## Writing a story: `open_<name>.md`

One file is the whole story definition. Five sections, each read verbatim:

| Section | What it is |
| --- | --- |
| `## Voice` | Who is telling this and how. Sent with both writer calls. |
| `## Prose` | Rules for one section — length, shape, where to stop. |
| `## Choices` | Rules for the three options, including the output format. |
| `## Choose (for jev)` | Jev's instructions: how to judge options, per stage. |
| `## Open` | The opening paragraphs, which become the start of Section 1. |

`open_nightfall.md` is the worked example — a sword-and-sandals chase through a
city at dusk, written as if by a half-drunk 70s pulp novelist. Copy it and
change the five sections.

Story files and their output stay local: `.gitignore` excludes every `open_*`
and `story_*` except `open_nightfall.md`.

## License

MIT — see [LICENSE](LICENSE).
