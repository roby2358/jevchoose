#!/usr/bin/env python3
"""Choose-your-own-adventure driver.

A writer model (via OpenRouter; Mistral by default, Sonnet behind a switch)
writes each section in one call and the three choices in a second call; Jev
(TypeSafe System One) picks the choice. Sections 1..10 accumulate in story.md, with a
"# Jev" appendix recording every choice and its probabilities. Every run starts
from scratch and overwrites story_NAME.md; nothing else is written to disk.

Usage:
  driver.py --story NAME run       # write all 10 sections
  driver.py --story NAME run N     # write only the first N sections

open_NAME.md needs four sections: `## Voice`, `## Prose` (writer rules for a
section, sent verbatim), `## Choices` (writer rules
for the three options), `## Choose (for jev)` (how Jev picks), and `## Open`.

The story NAME (or env STORY) selects open_NAME.md as input and story_NAME.md
as output.

Writer model: --model mistral|sonnet (or a full OpenRouter id), or env
OPENROUTER_MODEL. Default: mistral.

Keys come from .env.secure, beside this file or one directory up
(JEV_KEY or TYPESAFE_API_KEY, OPENROUTER_API_KEY).
"""
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

from typesafe_sdk import Choice, TypeSafeClient

HERE = Path(__file__).parent
OPEN = STORY = None  # set by set_story()
TOTAL = 10
MODELS = {
    "mistral": "mistralai/mistral-medium-3-5",
    "sonnet": "anthropic/claude-sonnet-5",
}
MODEL = MODELS["mistral"]
OR_URL = "https://openrouter.ai/api/v1/chat/completions"


def load_env():
    for f in (HERE / ".env.secure", HERE.parent / ".env.secure"):
        if not f.exists():
            continue
        for ln in f.read_text().splitlines():
            if "=" in ln and not ln.startswith("#"):
                k, v = ln.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
        return


def section_text(md: str, heading: str) -> str:
    m = re.search(rf"^{re.escape(heading)}\n(.*?)(?=^#|\Z)", md, re.S | re.M)
    return m.group(1).strip() if m else ""


def stage(n: int) -> str:
    return "build" if n <= TOTAL - 2 else ("wrap" if n == TOTAL - 1 else "seed")


def set_story(name: str | None) -> None:
    """Bind OPEN/STORY to open_<name>.md and story_<name>.md."""
    global OPEN, STORY
    name = name or os.environ.get("STORY")
    if not name:
        sys.exit("no story: pass --story NAME (reads open_NAME.md) or set STORY")
    OPEN = HERE / f"open_{name}.md"
    STORY = HERE / f"story_{name}.md"
    if not OPEN.exists():
        sys.exit(f"missing {OPEN}")


# --- Writer (OpenRouter) ---------------------------------------------------------

def set_model(name: str | None) -> None:
    """Pick the writer model by alias (mistral, sonnet) or full OpenRouter id."""
    global MODEL
    name = name or os.environ.get("OPENROUTER_MODEL") or "mistral"
    MODEL = MODELS.get(name, name)


def llm(system: str, user: str) -> str:
    req = urllib.request.Request(
        OR_URL,
        data=json.dumps({
            "model": MODEL,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "temperature": 0.9,
            "max_tokens": 2500,
        }).encode(),
        headers={
            "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
            "Content-Type": "application/json",
            "X-Title": "jevclient choose",
        },
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        data = json.load(r)
    return data["choices"][0]["message"]["content"]


STAGE_NOTES = {
    "build": "This section must push the tension higher than the last and end on a "
             "discovery or a danger that forces a decision.",
    "wrap": "The crescendo has passed. This section resolves it, pays off what was "
            "set up, and lets the hero breathe. End on a quieter choice about what "
            "to do now that it is over.",
    "seed": "This is the final section. Cool down, close this tale, and end on a "
            "choice whose options each point toward a different next story in the "
            "series: a new threat, a new goal, or an unfinished debt.",
}


def write_prose(n: int, voice: str, rules: str, prose: str, chosen: str | None) -> str:
    """Call 1: the section's prose, ending on a decision point. No choices.

    `rules` is the open file's `## Prose` section, sent verbatim.
    """
    system = (
        "You are writing one section at a time of a serialized choose-your-own-adventure "
        "novella. Voice and rules:\n\n" + voice + "\n\n" +
        rules
    )
    parts = [f"Story so far:\n\n{prose}\n\n"]
    if n == 1:
        parts.append("The opening above is the start of Section 1. Continue it directly "
                     "from where it leaves off, as the rest of Section 1.")
    else:
        parts.append(f"The reader chose: {chosen}\n\nWrite Section {n} of {TOTAL}. "
                     "Open by playing out that choice, then carry the story forward.")
    parts.append(f"\n\nStage note: {STAGE_NOTES[stage(n)]}")
    out = llm(system, "".join(parts)).strip()
    # strip a stray CHOICES block if the model ignores instructions
    out = out.split("CHOICES:")[0].strip()
    if not out:
        raise RuntimeError("writer returned empty prose")
    paras = [p for p in re.split(r"\n\s*\n", out) if p.strip()]
    print(f"({len(paras)} paras, {len(out.split())} words)", file=sys.stderr, end=" ", flush=True)
    return out


def write_choices(n: int, voice: str, rules: str, prose: str) -> list[str]:
    """Call 2: three choices for the decision point the prose just reached.

    `rules` is the open file's `## Choices` section (format + constraints).
    """
    system = (
        "You write the choices for a serialized choose-your-own-adventure novella. "
        "Voice and rules of the story:\n\n" + voice + "\n\n" +
        rules
    )
    user = (f"Story so far, ending at the decision point:\n\n{prose}\n\n"
            f"This is Section {n} of {TOTAL}. Stage note: {STAGE_NOTES[stage(n)]}\n\n"
            "Give the three choices the hero faces right now.")
    out = llm(system, user).strip()
    choices = [re.sub(r"^\s*\d+[.)]\s*", "", ln).strip()
               for ln in out.splitlines() if re.match(r"^\s*\d+[.)]", ln)]
    if len(choices) != 3:
        raise RuntimeError(f"expected 3 choices, got {choices}")
    return choices


# --- Jev ---------------------------------------------------------------------

def jev_choose(client: TypeSafeClient, jev_prompt: str, n: int, prose: str, choices: list[str]):
    state = {
        "story_so_far": prose,
        "section_number": n,
        "total_sections": TOTAL,
        "stage": stage(n),
        "choices": {"A": choices[0], "B": choices[1], "C": choices[2]},
    }
    q = Choice(
        instructions=jev_prompt,
        criteria={"A": choices[0], "B": choices[1], "C": choices[2]},
    )
    resp = client.system_one(state=state, questions={"pick": q})
    a = resp.answers["pick"]
    return a.choice, a.confidence, a.probabilities


# --- story.md ----------------------------------------------------------------

def render(log: list[dict]) -> str:
    out = ["# Story\n"]
    for r in log:
        out.append(f"## Section {r['n']}\n\n{r['prose']}\n")
        if r["choices"]:
            out.append("**What do you do?**\n")
            for i, c in enumerate(r["choices"]):
                mark = " ←" if "ABC"[i] == r["pick"] else ""
                out.append(f"{i+1}. {c}{mark}")
            out.append("")
    out.append("# Jev\n")
    for r in log:
        if not r["choices"]:
            continue
        p = r["probs"]
        out.append(f"- Section {r['n']} ({r['stage']}): picked {r['pick']} "
                   f"(conf {r['conf']:.2f}) — A {p['A']:.2f}, B {p['B']:.2f}, C {p['C']:.2f}")
    return "\n".join(out) + "\n"


def run(upto: int) -> None:
    load_env()
    opn = OPEN.read_text()
    voice = section_text(opn, "## Voice")
    jev_prompt = section_text(opn, "## Choose (for jev)")
    prose_rules = section_text(opn, "## Prose")
    choice_rules = section_text(opn, "## Choices")
    for name, val in (("## Prose", prose_rules), ("## Choices", choice_rules),
                      ("## Voice", voice), ("## Choose (for jev)", jev_prompt)):
        if not val:
            sys.exit(f"{OPEN} is missing a `{name}` section")
    opening = section_text(opn, "## Open")
    log: list[dict] = []
    api_key = os.environ.get("TYPESAFE_API_KEY") or os.environ.get("JEV_KEY")
    with TypeSafeClient(api_key=api_key) as client:
        for n in range(1, upto + 1):
            prose_so_far = "\n\n".join(r["prose"] for r in log) if log else opening
            chosen = log[-1]["choices"]["ABC".index(log[-1]["pick"])] if log else None
            print(f"section {n} [{stage(n)}]: prose...", file=sys.stderr, end=" ", flush=True)
            text = write_prose(n, voice, prose_rules, prose_so_far, chosen)
            prose = (opening + "\n\n" + text) if n == 1 else text
            print("choices...", file=sys.stderr, end=" ", flush=True)
            choices = write_choices(n, voice, choice_rules, prose_so_far + "\n\n" + text)
            print("jev...", file=sys.stderr, end=" ", flush=True)
            pick, conf, probs = jev_choose(client, jev_prompt, n, prose_so_far + "\n\n" + text, choices)
            print(f"{pick} {probs}", file=sys.stderr)
            rec = {"n": n, "stage": stage(n), "model": MODEL, "prose": prose,
                   "choices": choices, "pick": pick, "conf": conf, "probs": probs}
            log.append(rec)
            STORY.write_text(render(log))
    print(f"wrote {STORY} ({len(log)} sections)")


if __name__ == "__main__":
    argv = sys.argv[1:]
    opts = {}
    for flag in ("--model", "--story"):
        if flag in argv:
            i = argv.index(flag)
            opts[flag] = argv[i + 1]
            del argv[i:i + 2]
    set_model(opts.get("--model"))
    set_story(opts.get("--story"))
    cmd = argv[0] if argv else "run"
    if cmd == "run":
        run(int(argv[1]) if len(argv) > 1 else TOTAL)
    else:
        sys.exit(__doc__)
