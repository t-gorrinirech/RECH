# RECH

**Ruthless Exposure of Credential Habits**, a personalized wordlist generator that thinks like the person you're targeting.

RECH takes what you know about a target (names, dates, pets, nicknames, teams, that kind of thing) and turns it into a wordlist. The _how_ is the key factor here:

- RECH models the way real people actually build passwords
- Two core factors for generation: standard human behavior, and a 'paranoid' baseline
- Multiple personalities available, each one with a different way of creating passwords
- Feed the same data to two personalities and you get two very different wordlists
- Highly tweakable, almost every aspect of the passwords can be customized

So the pitch is simple: same input, human-shaped output, tuned to the kind of person you think the target is.

> For **authorized** pentesting and bug bounty only. You already know this.

## How It Works

Two core settings drive the entire generation.

**Assembly mode** (how tokens are merged together):

- `human`: Predictable and structured. It relies on standard patterns like `word + word + number`, with symbols usually at the very end and capitalization only on the first letter (if used at all).
- `paranoid`: Chaotic and interleaved. Words are split and injected into each other, heavily obfuscated with aggressive leetspeak and scattered symbols (which are sometimes doubled).

Leak Probability:
Nobody is 100% consistent. Every profile has a small margin of randomness, meaning a mostly "human" profile will still occasionally spit out a "paranoid" password to mimic real-world inconsistency.

**Personality**, which fields it cares about, how much leet and symbols it uses, and where those symbols land. This part is fully data driven (`profiles/*.json`), nothing is hardcoded.

## The 8 Personalities

| id (`-p`)     | vibe                                                          | leans on                                                      |
| ------------- | ------------------------------------------------------------- | ------------------------------------------------------------- |
| `sentimental` | names and dates, barely any structural variation              | pets, family, partner, important dates, childhood street      |
| `lazy`        | dead simple, few combinations                                 | name, nickname, obvious number, current address, lucky number |
| `technical`   | camelCase / PascalCase, no abbreviations                      | profession, tech hobby, favorite game, language/OS            |
| `paranoid`    | heavy interleaving, high leet, repeated patterns              | a bit of everything, artificial length                        |
| `fanatic`     | pop culture, sports, idol references                          | football team, sport, celebrity, saga/character               |
| `corporate`   | `Lastname + Role + Year`, predictable but meets min policy    | last name, job role, current year, company, degree            |
| `gamer`       | strong leet, gamertag, 2 digit birth year                     | nickname/nick, favorite game, birth year, in game character   |
| `default`     | no personality, flat weights, symbol almost always at the end | every field, no prioritization                                |

List them anytime:

```bash
python3 RECH.py -lp
```

## Get Started

### 1. Installation

Needs **Python 3.9+** (developed on 3.13). The only real dependency is `typer`.

```bash
git clone <this-repo> RECH
cd RECH
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

That's it, nothing fancy.

### 2. The Input File

You feed it a JSON with what you know about the target. Start from the template:

```
config/input_template.json
```

It has around 55 fields across categories like `personal_info`, `birth_data`, `address_data`, `education`, `family_and_relationships`, `work_and_career`, `interests_and_fandom`, `tech_and_gaming`, `social_media_usernames`, `vehicles_and_numbers`.

Rules:

- Fill in what you know. **Leave the rest as `"WRITE HERE"`**, that literal string means "empty" and gets skipped.
- Don't add or remove fields. The tokenizer only knows the fields in the template.
- Array fields (`pet_names`, `sibling_names`, `important_dates`, and so on) take 0, 1, or N entries. Each non-empty one is tokenized on its own.

More data means a bigger, better wordlist. Thin input means RECH warns you the output is going to be low variety.

## Usage

```
python3 RECH.py -p <personality> -s <size> --input <path> [OPTIONS]
```

### Flags

| Short | Long                 | What it does                                                                                                                   |
| ----- | -------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `-p`  | `--personality`      | One of the 8 personalities. **Required**, no silent default.                                                                   |
| `-lp` | `--list`             | List available personalities and exit.                                                                                         |
|       | `--input`            | Path to your filled in data JSON. **Required**.                                                                                |
| `-r`  | `--range`            | Password length range `min,max`. Default `6,20`.                                                                               |
| `-sc` | `--special-chars`    | Symbols to allow, e.g. `-sc !,@,$`. Bare `-sc` uses the default pool `_ . - ! @ * $ ? & %`.                                    |
| `-sP` | `--spaces`           | Allow spaces inside passwords. Off by default.                                                                                 |
| `-Uc` | `--upper-case`       | Apply uppercase (mostly the first letter of each word). Off by default.                                                        |
| `-nf` | `--num-first`        | Let numbers show up at the _start_ too (e.g. `1600johndoe`), not just the end.                                                 |
| `-lc` | `--limit-characters` | Hard cap on special symbols per password, e.g. `-lc 2`. Anything over the cap gets dropped.                                    |
| `-s`  | `--size`             | How many to generate: `small`=300k, `medium`=700k, `large`=1M, or any integer `N`. **Required**.                               |
| `-o`  | `--output`           | Output file path. Default `wordlist.txt`.                                                                                      |
|       | `--depth`            | Max data fields combined per password. Default `3`.                                                                            |
|       | `--debug`            | Also write a `.debug.jsonl` with metadata (tokens, personality, mode) per password.                                            |
|       | `--allow-relax`      | If `--size` is bigger than what's actually reachable, loosen personality/symbol rules to get closer instead of stopping short. |
|       | `--seed`             | Int seed for reproducibility. Same seed **plus same options** gives the same wordlist.                                         |
| `-h`  | `--help`             | Show help.                                                                                                                     |

### Examples

```bash
# Basic gamer run, 300k lines, uppercase on
python3 RECH.py -p gamer --input config/input_template.json -s small -Uc

# Paranoid, 1M, custom symbols but capped at 3 per password, seeded, custom output
python3 RECH.py -p paranoid --input in.json -s large -sc !,@,$,% -lc 3 --seed 42 -o out.txt

# Corporate, length window, numbers allowed up front, allow spaces, debug + relax
python3 RECH.py -p corporate --input in.json -r 8,16 -nf -sP --debug --allow-relax

# Lazy, numbers up front, max 2 symbols per password, uppercase, length window
python3 RECH.py -p lazy --input in.json -s 50000 -r 8,16 -nf -lc 2 -Uc -sc .,!,@

# Technical, custom size, deeper token combos, seeded and reproducible
python3 RECH.py -p technical --input in.json -s 200000 --depth 4 -sc _,-,. --seed 7
```

## Warnings and Sanity Checks

Before generating, RECH runs a check pass and prints warnings (yellow) or hard errors (red). It flags stuff like:

- **Completeness**: sentimental with no pet or family data, gamer with no nickname, or just too few fields filled. Your output is going to be boring.
- **Flag coherence**: `-sc` on a `lazy` or `sentimental` personality (symbols will be low variety), or _no_ `-sc` on `paranoid` or `technical` (you're leaving realism on the table). A bad `--range` (min > max, values ≤ 0) is a hard error.
- **Feasibility**: you asked for more passwords than actually exist given your data, personality, and range. It tells you the real reachable number and either stops early or, with `--allow-relax`, loosens the rules.
- **Runtime**: a heads up when your option combo is going to be slow (see below).
- **Output**: no write permission or not enough disk is a hard error before it even starts.

## Output

- A plain text wordlist (one password per line) at `-o` (default `wordlist.txt`).
- With `--debug`, a sibling `<output>.debug.jsonl` with per password metadata (source tokens, personality, assembly mode). Handy for understanding _why_ a password was generated.
- A run metrics summary to stderr: generated vs requested, length distribution, % with symbols, % with uppercase, most used fields, elapsed time, and the seed used.

Everything streams to disk with buffered writes and generator based candidate production, so memory stays flat even on `large` runs.

## Reproducibility

Pass `--seed <int>` and you get the exact same wordlist every time, as long as the other options are identical. The seed drives every random decision (partial leet, paranoid split point, secondary token choice). Change a flag, change the result. If you don't pass a seed, RECH picks a random one and prints it, so you can reproduce a run after the fact.

## Project Layout

```
RECH.py                 # entrypoint (thin launcher)
cli.py                  # typer CLI, flag parsing/validation, progress UI, orchestration
core/
  tokenizer.py          # raw fields into typed, tiered token variants
  personalities.py      # loads profiles/*.json, computes field weights
  leet.py               # letter substitutions + symbol picking
  assembler.py          # human/paranoid assembly, streams candidates
  sanity_checks.py      # the up front warning/error pass
output/
  writer.py             # length/symbol filter, dedup, streaming, metrics
config/
  input_template.json   # the ~55 field input template you fill in
  field_types.json      # field to type mapping (drives variant generation)
  field_tiers.json      # field to tier mapping (drives variant aggressiveness)
profiles/
  *.json                # one file per personality
tests/                  # distribution tests (each personality must differ)
```

## Running The Tests

```bash
python3 -m pytest -q
```

The suite checks that each personality produces a statistically distinct distribution (symbol %, average length, top tokens). That's the whole point of the tool, so that's what we test.

## License

This is a personal project released under **MIT license**. See [LICENSE](https://github.com/t-gorrinirech/RECH/blob/main/LICENSE) and [DISCLAIMER](https://github.com/t-gorrinirech/RECH/blob/main/DISCLAIMER.md) for more usage info.
