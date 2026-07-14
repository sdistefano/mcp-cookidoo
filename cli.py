#!/usr/bin/env python3
"""
Cookidoo CLI

A thin command-line wrapper around the same logic that powers the Cookidoo MCP
server (``server.py``). Where the MCP server keeps a long-lived authenticated
session in module globals, every CLI invocation is a fresh process, so each
online command authenticates inline before doing its work.

All machine-readable output is emitted as JSON on **stdout**; any progress /
debug chatter (including the ``print`` calls inside ``CookidooService``) is
redirected to **stderr** so stdout stays parseable.

Examples
--------
    cookidoo connect                     # verify credentials work
    cookidoo list                        # list your custom recipes
    cookidoo read <recipe_id>            # read a recipe in marker language
    cookidoo get  r59322                 # fetch an official recipe's details
    cookidoo raw  <recipe_id>            # dump the raw created-recipe JSON
    cookidoo validate recipe.json        # validate a recipe structure offline
    cookidoo create recipe.json          # create a new custom recipe
    cookidoo update <recipe_id> -        # update a recipe from stdin JSON

Recipe input (``validate``/``create``/``update``) accepts a file path, a literal
JSON string, or ``-`` to read JSON from stdin.
"""

import argparse
import asyncio
import contextlib
import json
import os
import sys
from typing import Any, Callable, Dict, List

from cookidoo_service import CookidooService, load_cookidoo_credentials
from schemas import CustomRecipe
from annotations import (
    build_instructions_from_steps,
    instructions_to_steps,
    text_steps_to_marker_steps,
)


# --------------------------------------------------------------------------- #
# Output helpers
# --------------------------------------------------------------------------- #
def emit(obj: Any) -> None:
    """Print a result to stdout: strings verbatim, everything else as JSON."""
    if isinstance(obj, str):
        print(obj)
    else:
        print(json.dumps(obj, indent=2, ensure_ascii=False))


@contextlib.contextmanager
def quiet_stdout():
    """Redirect stdout to stderr for the duration of a block.

    ``CookidooService`` prints HTTP status/body lines to stdout for debugging.
    We route those to stderr so the only thing on stdout is our final JSON.
    """
    with contextlib.redirect_stdout(sys.stderr):
        yield


def load_recipe_input(src: str) -> Dict[str, Any]:
    """Load recipe JSON from a file path, a literal JSON string, or stdin (``-``)."""
    if src == "-":
        text = sys.stdin.read()
    elif os.path.exists(src):
        with open(src, "r", encoding="utf-8") as handle:
            text = handle.read()
    else:
        text = src
    return json.loads(text)


# --------------------------------------------------------------------------- #
# Authenticated session
# --------------------------------------------------------------------------- #
@contextlib.asynccontextmanager
async def cookidoo_session():
    """Yield a logged-in ``(service, api)`` pair, closing the session on exit."""
    email, password = load_cookidoo_credentials()
    service = CookidooService(email, password)
    with quiet_stdout():
        api = await service.login()
    try:
        yield service, api
    finally:
        await service.close()


# --------------------------------------------------------------------------- #
# Payload / translation helpers (shared shape with server.py)
# --------------------------------------------------------------------------- #
def build_recipe_payload(recipe: CustomRecipe) -> Dict[str, Any]:
    """Map a validated ``CustomRecipe`` into the low-level created-recipes PATCH body.

    Unlike ``server.py``'s ``update_custom_recipe`` (which kept steps as plain
    ``STEP`` text), we route steps through ``build_instructions_from_steps`` so
    that ``[[ACTION:...]]`` / ``[[INGREDIENT:...]]`` markers survive an update —
    keeping ``read`` -> edit -> ``update`` round-trips lossless.
    """
    hints = recipe.hints
    hints_text = "\n".join(hints) if isinstance(hints, list) else (hints or "")
    return {
        "name": recipe.name,
        "image": None,
        "isImageOwnedByUser": False,
        "tools": ["TM6"],
        "yield": {"value": recipe.servings, "unitText": "portion"},
        "prepTime": recipe.prep_time * 60,
        "cookTime": 0,
        "totalTime": recipe.total_time * 60,
        "ingredients": [{"type": "INGREDIENT", "text": ing} for ing in recipe.ingredients],
        "instructions": build_instructions_from_steps(recipe.steps),
        "hints": hints_text,
        "workStatus": "PRIVATE",
        "recipeMetadata": {"requiresAnnotationsCheck": False},
    }


def raw_to_marker_recipe(recipe_id: str, raw: Dict[str, Any]) -> Dict[str, Any]:
    """Translate a raw created-recipe payload back into the marker language.

    Mirrors ``server.py``'s ``read_recipe``: ingredients become a flat list and
    instructions are rendered with ``[[ACTION:...]]`` / ``[[INGREDIENT:...]]``.
    """
    recipe_content = raw.get("recipeContent") or {}
    name = raw.get("name") or raw.get("recipeName") or recipe_content.get("name") or ""

    ingredients: List[str] = []
    if "ingredients" in raw:
        for ing in raw.get("ingredients", []):
            if isinstance(ing, dict) and ing.get("type") == "INGREDIENT" and ing.get("text"):
                ingredients.append(ing["text"])
    else:
        for text in recipe_content.get("recipeIngredient", []) or []:
            if isinstance(text, str) and text.strip():
                ingredients.append(text.strip())

    if "instructions" in raw:
        steps = instructions_to_steps(raw.get("instructions") or [])
    else:
        plain = [
            s.strip()
            for s in (recipe_content.get("recipeInstructions") or [])
            if isinstance(s, str) and s.strip()
        ]
        steps = text_steps_to_marker_steps(plain)

    return {"id": recipe_id, "name": name, "ingredients": ingredients, "steps": steps}


def recipe_details_to_dict(recipe: Any) -> Dict[str, Any]:
    """Extract the interesting attributes of an official-recipe object into a dict."""
    result: Dict[str, Any] = {
        "name": getattr(recipe, "name", None),
        "id": getattr(recipe, "id", None),
    }
    for attr in ("serving_size", "total_time", "difficulty", "url"):
        if hasattr(recipe, attr):
            result[attr] = getattr(recipe, attr)

    ingredients = getattr(recipe, "ingredients", None)
    if ingredients:
        result["ingredients"] = [
            {"name": getattr(i, "name", None), "quantity": getattr(i, "quantity", None)}
            for i in ingredients
        ]

    steps = getattr(recipe, "steps", None)
    if steps:
        result["steps"] = [getattr(s, "description", None) for s in steps]

    return result


# --------------------------------------------------------------------------- #
# Command handlers (each returns the object to emit)
# --------------------------------------------------------------------------- #
async def cmd_connect(args: argparse.Namespace) -> Any:
    """Authenticate and report success — a quick credential smoke test."""
    async with cookidoo_session() as (service, _api):
        return f"Successfully connected to Cookidoo as {service.email}"


async def cmd_list(args: argparse.Namespace) -> Any:
    """List custom (created) recipes via authenticated HTML scraping."""
    async with cookidoo_session() as (service, _api):
        with quiet_stdout():
            return await service.list_custom_recipes()


async def cmd_read(args: argparse.Namespace) -> Any:
    """Read a custom recipe and translate it back into the marker language."""
    async with cookidoo_session() as (service, _api):
        with quiet_stdout():
            raw = await service.get_custom_recipe(args.recipe_id)
    return raw_to_marker_recipe(args.recipe_id, raw)


async def cmd_raw(args: argparse.Namespace) -> Any:
    """Dump the raw created-recipe JSON exactly as the API returns it."""
    async with cookidoo_session() as (service, _api):
        with quiet_stdout():
            return await service.get_custom_recipe(args.recipe_id)


async def cmd_get(args: argparse.Namespace) -> Any:
    """Fetch an official recipe's details by ID (e.g. ``r59322``)."""
    async with cookidoo_session() as (_service, api):
        with quiet_stdout():
            recipe = await api.get_recipe_details(args.recipe_id)
    return recipe_details_to_dict(recipe)


async def cmd_validate(args: argparse.Namespace) -> Any:
    """Validate a recipe structure offline and echo the normalized JSON."""
    recipe = CustomRecipe(**load_recipe_input(args.recipe))
    return json.loads(recipe.model_dump_json())


async def cmd_create(args: argparse.Namespace) -> Any:
    """Create a brand-new custom recipe from a validated structure."""
    recipe = CustomRecipe(**load_recipe_input(args.recipe))
    async with cookidoo_session() as (service, api):
        with quiet_stdout():
            recipe_id = await service.create_custom_recipe(
                name=recipe.name,
                ingredients=recipe.ingredients,
                steps=recipe.steps,
                servings=recipe.servings,
                prep_time=recipe.prep_time,
                total_time=recipe.total_time,
                hints=recipe.hints,
            )
        url = f"https://{api.localization.url}/recipes/custom-recipes/{recipe_id}"
    return {"id": recipe_id, "name": recipe.name, "url": url}


async def cmd_update(args: argparse.Namespace) -> Any:
    """Update an existing custom recipe in place from a validated structure."""
    recipe = CustomRecipe(**load_recipe_input(args.recipe))
    payload = build_recipe_payload(recipe)
    async with cookidoo_session() as (service, _api):
        with quiet_stdout():
            await service.update_custom_recipe(args.recipe_id, payload)
    return {"id": args.recipe_id, "name": recipe.name, "status": "updated"}


# --------------------------------------------------------------------------- #
# Argument parsing / dispatch
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    """Build the argparse CLI; each subcommand wires its async handler via ``func``."""
    parser = argparse.ArgumentParser(
        prog="cookidoo",
        description="Command-line client for the Cookidoo custom-recipe API.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name: str, handler: Callable, help_text: str) -> argparse.ArgumentParser:
        p = sub.add_parser(name, help=help_text, description=handler.__doc__)
        p.set_defaults(func=handler)
        return p

    add("connect", cmd_connect, "Verify credentials by logging in.")
    add("list", cmd_list, "List your custom (created) recipes.")

    p_read = add("read", cmd_read, "Read a custom recipe in marker language.")
    p_read.add_argument("recipe_id", help="Custom recipe ID, e.g. 01KBHZ...")

    p_raw = add("raw", cmd_raw, "Dump the raw created-recipe JSON.")
    p_raw.add_argument("recipe_id", help="Custom recipe ID.")

    p_get = add("get", cmd_get, "Get an official recipe's details by ID.")
    p_get.add_argument("recipe_id", help="Official recipe ID, e.g. r59322.")

    p_val = add("validate", cmd_validate, "Validate a recipe structure offline.")
    p_val.add_argument("recipe", help="Path, JSON string, or '-' for stdin.")

    p_create = add("create", cmd_create, "Create a new custom recipe.")
    p_create.add_argument("recipe", help="Path, JSON string, or '-' for stdin.")

    p_update = add("update", cmd_update, "Update an existing custom recipe.")
    p_update.add_argument("recipe_id", help="Custom recipe ID to update.")
    p_update.add_argument("recipe", help="Path, JSON string, or '-' for stdin.")

    return parser


def main(argv: List[str] | None = None) -> int:
    """Parse arguments, run the selected async handler, and emit its result."""
    args = build_parser().parse_args(argv)
    try:
        result = asyncio.run(args.func(args))
    except Exception as exc:  # noqa: BLE001 - surface any failure cleanly on the CLI
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    emit(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
