import re
from typing import Any, Dict, List, Tuple


ACTION_PATTERN = re.compile(r"\[\[ACTION:([^\]]+)\]\]")
INGREDIENT_PATTERN = re.compile(r"\[\[INGREDIENT:([^\]]+)\]\]")


def _parse_action_payload(payload: str) -> Tuple[str, Dict[str, Any]]:
    """Parse an ACTION payload like "30 min/50C/3" or "30 min/50C/3/R".

    Returns a tuple of:
      - human-readable text to insert into the step (e.g. "30 min/50°C/vitesse 3")
      - annotation data dict for the TTS annotation
    """
    # Split by '/': time_part, temp_part, speed_part[, reverse]
    parts = [p.strip() for p in payload.split("/") if p.strip()]
    if len(parts) < 3:
        raise ValueError(f"Invalid ACTION payload: {payload!r}")

    time_part, temp_part, speed_part, *rest = parts

    # Time: be very forgiving, support minutes or seconds with many spellings.
    # Examples: "5 min", "5min", "5 m", "5", "5 sec", "5s", "5sec", "5 seconds"
    m_time = re.match(r"^(?P<value>\d+)\s*(?P<rest>.*)$", time_part.strip())
    if not m_time:
        raise ValueError(f"Invalid ACTION time segment: {time_part!r}")

    time_value = int(m_time.group("value"))
    rest = m_time.group("rest").strip().lower()

    # Decide minutes vs seconds based on the rest of the string.
    # Default to minutes when nothing is specified.
    if not rest:
        unit = "min"
    elif "min" in rest or rest == "m":
        unit = "min"
    else:
        # Anything else (sec, s, seconds, etc.) -> seconds
        unit = "sec"

    if unit == "min":
        time_seconds = time_value * 60
        time_text = f"{time_value} min"
    else:
        time_seconds = time_value
        time_text = f"{time_value} sec"

    # Temperature: numeric like "50C" OR special value "Varoma"
    temp_part_stripped = temp_part.strip()
    if temp_part_stripped.lower().startswith("varoma"):
        # Map Varoma to 120°C internally, but keep the label "Varoma" in text.
        temp_value = "120"
        temp_unit = "C"
        temp_text = "Varoma"
    else:
        m_temp = re.match(
            r"^(?P<value>\d+)(?:\s*[°]?)?\s*(?P<unit>C|°C)?$",
            temp_part_stripped,
            re.IGNORECASE,
        )
        if not m_temp:
            raise ValueError(f"Invalid ACTION temperature segment: {temp_part!r}")
        temp_value = m_temp.group("value")
        temp_unit = "C"
        temp_text = f"{temp_value}°C"

    # Speed: number like "3"
    m_speed = re.match(r"^(?P<value>\d+)$", speed_part)
    if not m_speed:
        raise ValueError(f"Invalid ACTION speed segment: {speed_part!r}")
    speed_value = m_speed.group("value")

    reverse = False
    if rest:
        # Any extra segment (e.g. "R") means reverse
        reverse = any(seg.upper().startswith("R") for seg in rest)

    # Build human-readable text similar to the NOTE example
    text_parts = [time_text, temp_text, f"vitesse {speed_value}"]
    if reverse:
        text_parts.append("sens inverse")
    text = "/".join(text_parts)

    annotation_data = {
        "speed": speed_value,
        "time": time_seconds,
        "temperature": {"value": temp_value, "unit": temp_unit},
    }

    if reverse:
        annotation_data["reverse"] = True

    return text, annotation_data


def parse_step_with_annotations(step: str) -> Dict[str, Any]:
    """Parse a step text containing [[ACTION:...]] and [[INGREDIENT:...]] markers.

    Returns a dict with:
      - "text": the cleaned step text with human-readable fragments inserted
      - "annotations": list of Cookidoo-style annotations with correct offsets
    """
    annotations: List[Dict[str, Any]] = []

    # We'll build the output text incrementally while tracking how far we've written.
    out_chars: List[str] = []
    offset = 0  # current length of out_chars

    # We process markers in order of appearance from left to right.
    # Find all matches (ACTION or INGREDIENT), then sort by start index.
    matches: List[Tuple[int, int, str, re.Match[str]]] = []
    for m in ACTION_PATTERN.finditer(step):
        matches.append((m.start(), m.end(), "ACTION", m))
    for m in INGREDIENT_PATTERN.finditer(step):
        matches.append((m.start(), m.end(), "INGREDIENT", m))

    matches.sort(key=lambda t: t[0])

    cursor = 0
    for start, end, kind, match in matches:
        # Copy literal text before this marker
        if start > cursor:
            segment = step[cursor:start]
            out_chars.append(segment)
            offset += len(segment)

        payload = match.group(1).strip()

        if kind == "ACTION":
            human_text, data = _parse_action_payload(payload)
            # Insert human-readable text into output
            action_offset = offset
            out_chars.append(human_text)
            offset += len(human_text)

            annotations.append(
                {
                    "type": "TTS",
                    "data": data,
                    "position": {"offset": action_offset, "length": len(human_text)},
                }
            )
        else:  # INGREDIENT
            # Insert ingredient text literally
            ingr_offset = offset
            out_chars.append(payload)
            offset += len(payload)

            annotations.append(
                {
                    "type": "INGREDIENT",
                    "data": {"description": payload},
                    "position": {"offset": ingr_offset, "length": len(payload)},
                }
            )

        cursor = end

    # Copy any remaining trailing text after the last marker
    if cursor < len(step):
        tail = step[cursor:]
        out_chars.append(tail)
        offset += len(tail)

    final_text = "".join(out_chars)

    return {
        "text": final_text,
        "annotations": annotations,
    }


def build_instructions_from_steps(steps: List[str]) -> List[Dict[str, Any]]:
    """Convert high-level steps into Cookidoo instructions with annotations.

    Plain steps become simple STEP instructions without annotations.
    Steps containing [[ACTION:...]] / [[INGREDIENT:...]] markers get
    their markers replaced with human-readable fragments and corresponding
    annotations in the Cookidoo format.
    """
    instructions: List[Dict[str, Any]] = []

    for step in steps:
        parsed = parse_step_with_annotations(step)
        instruction: Dict[str, Any] = {"type": "STEP", "text": parsed["text"]}
        if parsed["annotations"]:
            instruction["annotations"] = parsed["annotations"]
        instructions.append(instruction)

    return instructions
