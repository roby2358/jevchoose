# interpreter: $PYTHON, else .venv (made by `just setup`), else system python3
python := env_var_or_default("PYTHON", if path_exists(".venv/bin/python") == "true" { ".venv/bin/python" } else { "python3" })
# writer model: mistral (default) | sonnet | any OpenRouter id
model := env_var_or_default("MODEL", "mistral")

# list recipes
default:
    @just --list

# create .venv with typesafe_sdk (run on the machine you will run stories from)
setup:
    python3 -m venv .venv
    .venv/bin/pip install --quiet --upgrade pip typesafe_sdk
    .venv/bin/python -c "import typesafe_sdk; print('typesafe_sdk', typesafe_sdk.__file__)"

# write all ten sections of open_<story>.md -> story_<story>.md (always starts from scratch)
run story:
    {{python}} driver.py --model {{model}} --story {{story}} run

# write only the first N sections
upto story n:
    {{python}} driver.py --model {{model}} --story {{story}} run {{n}}

# print a story
show story:
    @test -f story_{{story}}.md || { echo "no story_{{story}}.md yet; run: just run {{story}}"; exit 1; }
    @cat story_{{story}}.md

# show Jev's picks and probabilities for a story
jev story:
    @test -f story_{{story}}.md || { echo "no story_{{story}}.md yet; run: just run {{story}}"; exit 1; }
    @sed -n '/^# Jev/,$p' story_{{story}}.md

# list available stories
stories:
    @ls open_*.md | sed 's/^open_//; s/\.md$//'
