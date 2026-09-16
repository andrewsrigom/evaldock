"""Two offline examples for curated English specification passages, not web scrapers.

Functions accept only a passage. They have no access to references, case IDs, URLs,
other cases, network services or credentials. Neither is a production extractor.
"""

import re

COUNTRIES = {"usa": "US", "united states": "US", "china": "CN", "germany": "DE"}
COUNTRY = r"(?:USA|United States|China|Germany)"
GRAMS = r"(?<![\w.-])(\d+(?:\.\d+)?)\s*g\b"


def country_code(value):
    return COUNTRIES.get(value.lower())


def material(text, preserve_grade=True):
    text = text.lower()
    if "tritan renew" in text:
        return "Tritan Renew"
    if re.search(r"\bhdpe\b|high[ -]density poly\s*ethylene", text):
        return "HDPE"
    if preserve_grade and re.search(r"grade\s+1\s+titanium", text):
        return "grade 1 titanium"
    if "titanium" in text:
        return "titanium"
    return None


def baseline(passage):
    """Naive first-mention implementation, retained unchanged for comparison."""
    weight = re.search(GRAMS, passage, re.I)
    country = re.search(COUNTRY, passage, re.I)
    return {
        "material": material(passage, preserve_grade=False),
        "weight_g": float(weight[1]) if weight else None,
        "country": country_code(country[0]) if country else None,
    }


def candidate(passage):
    """Scoped specification parser: metric weight, assembly and explicit origin.

    Supported vocabulary is deliberately limited. Unknown or ambiguous facts
    yield null. This accepts curated labeled lines, not arbitrary HTML or prose.
    """
    lines = [line.strip() for line in passage.splitlines() if line.strip()]
    material_values = {
        material(line.split(":", 1)[1])
        for line in lines
        if re.match(r"^(?:body )?material:", line, re.I)
    }
    weights = []
    for line in lines:
        if not re.match(r"^(?:net |product |pot |bottle )?(?:weight|mass)", line, re.I):
            continue
        if re.search(r"without (?:the )?lid|pot only|packaging|shipping", line, re.I):
            continue
        values = re.findall(GRAMS, line, re.I)
        # Metric values supplied by the manufacturer take precedence over oz.
        if len(set(values)) == 1:
            priority = 1 if re.search(r"with (?:the )?lid", line, re.I) else 0
            weights.append((priority, float(values[0])))
        elif values:
            weights.append((0, None))
    weight = None
    if weights:
        highest = max(priority for priority, _ in weights)
        candidates = {value for priority, value in weights if priority == highest}
        if len(candidates) == 1:
            weight = candidates.pop()
    origins = []
    for line in lines:
        explicit = re.match(
            rf"^(?:(?:Bottle|Body|Product) )?(?:made|manufactured) in (?:the )?({COUNTRY})\b",
            line,
            re.I,
        )
        field = re.match(rf"^Country of origin:\s*({COUNTRY})\b", line, re.I)
        if explicit or field:
            origins.append(country_code((explicit or field)[1]))
    return {
        "material": material_values.pop() if len(material_values) == 1 else None,
        "weight_g": weight,
        "country": origins[0] if origins and len(set(origins)) == 1 else None,
    }
