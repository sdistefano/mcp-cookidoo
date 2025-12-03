import pytest

from annotations import (
    parse_step_with_annotations,
    build_instructions_from_steps,
    instructions_to_steps,
)


def test_parse_step_with_single_action_and_ingredient_matches_notes_shape():
    # This corresponds conceptually to NOTES.md, but expressed via markers.
    step = "test [[ACTION:30 min/65C/3]] [[INGREDIENT:eau]]"

    result = parse_step_with_annotations(step)

    assert isinstance(result, dict)
    text = result["text"]
    ann = result["annotations"]

    # The human-readable text should contain the action phrase and ingredient.
    assert "30 min/65°C/vitesse 3" in text
    assert "eau" in text

    # There should be exactly two annotations: TTS and INGREDIENT
    assert len(ann) == 2

    tts = next(a for a in ann if a["type"] == "TTS")
    ing = next(a for a in ann if a["type"] == "INGREDIENT")

    # TTS data
    assert tts["data"]["speed"] == "3"
    assert tts["data"]["time"] == 1800  # 30 min in seconds
    assert tts["data"]["temperature"] == {"value": "65", "unit": "C"}

    # Positions must be consistent with the final text
    tts_pos = tts["position"]
    tts_sub = text[tts_pos["offset"] : tts_pos["offset"] + tts_pos["length"]]
    assert tts_sub == "30 min/65°C/vitesse 3"

    ing_pos = ing["position"]
    ing_sub = text[ing_pos["offset"] : ing_pos["offset"] + ing_pos["length"]]
    assert ing_sub == "eau"


def test_parse_step_without_markers_returns_plain_step():
    step = "Rincer le bol du Thermomix."

    result = parse_step_with_annotations(step)

    assert result["text"] == step
    assert result["annotations"] == []


def test_parse_step_with_reverse_action():
    step = "Cuire [[ACTION:5 min/100C/1/R]] avec sens inverse."

    result = parse_step_with_annotations(step)

    text = result["text"]
    ann = result["annotations"]

    assert "5 min/100°C/vitesse 1/sens inverse" in text

    tts = ann[0]
    assert tts["type"] == "TTS"
    assert tts["data"]["reverse"] is True


def test_parse_step_with_seconds_action():
    step = "Cuire [[ACTION:5 sec/50C/3]] puis arrêter."

    result = parse_step_with_annotations(step)

    text = result["text"]
    ann = result["annotations"]

    assert "5 sec/50°C/vitesse 3" in text

    tts = ann[0]
    assert tts["type"] == "TTS"
    assert tts["data"]["time"] == 5


def test_build_instructions_from_steps_mixed():
    steps = [
        "Préparer les ingrédients.",
        "Cuire [[ACTION:10 min/90C/2]] puis ajouter [[INGREDIENT:riz]].",
    ]

    instructions = build_instructions_from_steps(steps)

    assert len(instructions) == 2

    # First step: plain STEP
    assert instructions[0]["type"] == "STEP"
    assert instructions[0]["text"] == steps[0]
    assert "annotations" not in instructions[0]

    # Second step: should have annotations
    second = instructions[1]
    assert second["type"] == "STEP"
    assert "annotations" in second
    assert any(a["type"] == "TTS" for a in second["annotations"])
    assert any(a["type"] == "INGREDIENT" for a in second["annotations"])


def test_instructions_to_steps_roundtrip():
    original_step = "Cuire [[ACTION:5 min/100C/1/R]] puis ajouter [[INGREDIENT:eau]]."
    instructions = build_instructions_from_steps([original_step])

    # Now go back from instructions to steps
    steps = instructions_to_steps(instructions)

    assert len(steps) == 1
    # The roundtrip should preserve our marker language (order and payloads)
    assert "[[ACTION:5 min/100C/1/R]]" in steps[0]
    assert "[[INGREDIENT:eau]]" in steps[0]
