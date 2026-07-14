# Cookidoo CLI

`bin/cookidoo` is a standalone command-line client for the Cookidoo custom-recipe API. It exposes the same operations as the
[MCP server](./README.md) (`server.py`) but is convenient for quick, scriptable use without running a server.

> **Disclaimer:** Unofficial project. Not affiliated with Cookidoo, Vorwerk, or Thermomix. See [README](./README.md).

## How it works

- **Stateless invocations.** The MCP server keeps one authenticated session in memory across tool calls. The CLI cannot — every
  process is fresh — so each *online* command authenticates inline before doing its work. Expect a short login delay per call.
- **JSON on stdout.** Machine-readable results are printed to **stdout** as indented JSON (or a plain string for `connect`).
- **Noise on stderr.** Login progress and the low-level HTTP status/body lines emitted by `CookidooService` are redirected to
  **stderr**, so stdout stays clean and parseable (e.g. pipe into `jq`).
- **Exit codes.** `0` on success; `1` on any error, with an `Error: <message>` line on stderr.

## Setup

1. Create the virtualenv and install dependencies (see the [README](./README.md#setup)):

   ```bash
   python -m venv .venv
   .venv/bin/python -m pip install -r requirements.txt
   ```

   The launcher uses `.venv/bin/python` when present and falls back to `python3` otherwise.

2. Provide credentials in `.env` (same file the MCP server reads):

   ```bash
   COOKIDOO_EMAIL=you@example.com
   COOKIDOO_PASSWORD=your-password
   # Optional, only needed by `list` (HTML scrape of the created-recipes page):
   COOKIDOO_COOKIE=<full browser cookie string for cookidoo.fr>
   ```

3. (Optional) Put the launcher on your `PATH`:

   ```bash
   ln -sf "$(pwd)/bin/cookidoo" ~/.local/bin/cookidoo
   ```

   The launcher resolves its own symlink, so it still finds the repo (and its `.venv`) when invoked from anywhere.

## Commands

| Command                      | Online? | Description                                                            |
| ---------------------------- | :-----: | --------------------------------------------------------------------- |
| `connect`                    |   yes   | Log in and confirm credentials work — a quick smoke test.             |
| `list`                       |   yes   | List your custom (created) recipes as `{id, name, url}` objects.       |
| `read <recipe_id>`           |   yes   | Read a custom recipe back into the marker language (see below).        |
| `raw <recipe_id>`            |   yes   | Dump the raw created-recipe JSON exactly as the API returns it.        |
| `get <recipe_id>`            |   yes   | Fetch an *official* recipe's details by ID (e.g. `r59322`).            |
| `validate <recipe>`          |   no    | Validate a recipe structure offline; echo the normalized JSON.         |
| `create <recipe>`            |   yes   | Create a new custom recipe from a validated structure.                 |
| `update <recipe_id> <recipe>`|   yes   | Update an existing custom recipe in place.                             |

Run `cookidoo <command> --help` for per-command usage.

### Recipe input (`validate` / `create` / `update`)

The `<recipe>` argument accepts, in this order of precedence:

1. `-` — read JSON from **stdin**.
2. An existing **file path** — read JSON from that file.
3. Otherwise, the argument is treated as a **literal JSON string**.

The JSON is validated against the `CustomRecipe` schema ([`schemas.py`](./schemas.py)):

```json
{
  "name": "Chocolate Chip Cookies",
  "ingredients": ["200g flour", "100g butter", "100g sugar", "1 egg", "100g chocolate chips"],
  "steps": ["Mix butter and sugar", "Add egg", "Fold in flour and chips", "Bake [[ACTION:12 min/180C/1]]"],
  "servings": 6,
  "prep_time": 15,
  "total_time": 30,
  "hints": ["Don't overmix", "They firm up as they cool"]
}
```

| Field         | Type            | Notes                                              |
| ------------- | --------------- | -------------------------------------------------- |
| `name`        | string          | Required, 1–200 chars.                             |
| `ingredients` | list of strings | Required, at least one.                            |
| `steps`       | list of strings | Required, at least one. May contain markers.       |
| `servings`    | int             | Default `4`, range 1–20.                           |
| `prep_time`   | int (minutes)   | Default `30`, range 1–1440.                        |
| `total_time`  | int (minutes)   | Default `60`, range 1–1440.                        |
| `hints`       | list of strings | Optional.                                          |

## Marker language

Steps may embed inline markers that are expanded into Cookidoo annotations (Thermomix guided-cooking actions and ingredient
links). `read` reverses the process, turning stored annotations back into markers — so `read` → edit → `update` round-trips
without losing them. Logic lives in [`annotations.py`](./annotations.py).

### `[[ACTION:...]]` — guided step (time / temperature / speed)

```
[[ACTION:<time>/<temp>/<speed>]]
[[ACTION:<time>/<temp>/<speed>/R]]   # /R (or any trailing segment) = reverse rotation
[[ACTION:<time>/<speed>]]            # shorthand: no temperature
```

- **time** — `30 min`, `30min`, `30` (minutes assumed) or `45 sec`, `45s` for seconds.
- **temp** — `100C`, `100`, `100°C`, or `Varoma` (kept as the label "Varoma", treated as 120°C internally).
- **speed** — a number, e.g. `3`.
- **reverse** — add a trailing `/R` for reverse (Thermomix "sens inverse").

Example: `Cuire [[ACTION:30 min/100C/2]]` renders as `Cuire 30 min/100°C/vitesse 2` with the matching `TTS` annotation.

### `[[INGREDIENT:...]]` — ingredient reference

```
[[INGREDIENT:<description>]]
```

Example: `Hacher [[INGREDIENT:oignon]]` links the word "oignon" in the step to an ingredient annotation.

## Examples

```bash
# Verify credentials
cookidoo connect

# List recipes and pull out just the IDs with jq
cookidoo list | jq -r '.[].id'

# Round-trip: read a recipe, tweak it, push it back
cookidoo read 01KBHZPGSKAHAJATWQR23PWYM8 > recipe.json
$EDITOR recipe.json
cookidoo update 01KBHZPGSKAHAJATWQR23PWYM8 recipe.json

# Create from a heredoc piped to stdin
cookidoo create - <<'JSON'
{"name":"Test Soup","ingredients":["500g eau","1 oignon"],
 "steps":["Hacher [[INGREDIENT:oignon]]","Cuire [[ACTION:30 min/100C/2]]"],
 "servings":4,"prep_time":10,"total_time":40}
JSON

# Validate a file without touching the network
cookidoo validate recipe.json

# Inspect an official recipe for inspiration
cookidoo get r59322
```

## Differences from the MCP server

- **`update` preserves annotations.** The CLI routes update steps through `build_instructions_from_steps`, so `[[ACTION:...]]`
  and `[[INGREDIENT:...]]` markers survive an update. The MCP server's `update_custom_recipe` currently stores plain `STEP`
  text (a noted TODO). `server.py` is otherwise untouched.
- **No persistent `connect`.** There is a `connect` command for testing, but unlike the MCP tool it does not persist a session;
  every other command logs in on its own.

## Troubleshooting

- **`Error: Missing Cookidoo credentials...`** — populate `COOKIDOO_EMAIL` / `COOKIDOO_PASSWORD` in `.env`.
- **`list` returns `[]`** — the created-recipes page needs the browser `COOKIDOO_COOKIE` (it uses a separate CIAM login from the
  official API). Copy a fresh cookie from your browser dev tools while logged into `cookidoo.fr`.
- **`ModuleNotFoundError`** — the `.venv` is missing or incomplete; re-run the [Setup](#setup) install step.
