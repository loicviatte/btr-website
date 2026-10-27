"""Thumbnail layout settings.

Defaults live here; Loïc's changes live in <data>/design.json and are read at EVERY render, so a setting can be changed
from the chat without any deploy. A real layout change (new element, new template) is still a code change.
"""
import json
from pathlib import Path

FORMATS = {"youtube": "horizontal (YouTube)", "instagram": "vertical (Instagram)", "square": "carré"}

_TEXT = {
    "key_scale": (1.0, "taille du mot clé (1 = normal, 1.1 = +10 %)"),
    "small_scale": (1.0, "taille des lignes du haut et du bas (1 = normal)"),
    "line_gap": (0, "interligne : espace ajouté autour du mot clé (px)"),
    "word_gap": (0, "écart ajouté entre les mots d'une même ligne (px)"),
}

PARAMS = {
    "youtube": {
        "text_dx": (0, "décalage du texte vers la droite (px, négatif = gauche)"),
        "text_dy": (0, "décalage du texte vers le bas (px, négatif = haut)"),
        **_TEXT,
        "text_front": (True, "texte devant les personnes (oui) ou derrière (non)"),
    },
    "square": {
        "text_dx": (0, "décalage du texte vers la droite (px, négatif = gauche)"),
        "text_dy": (0, "décalage du texte vers le bas (px, négatif = haut)"),
        **_TEXT,
        "text_front": (True, "texte devant les personnes (oui) ou derrière (non)"),
        "marius_front": (True, "Marius devant l'invitée (oui) ou derrière (non)"),
    },
    "instagram": {
        "text_anchor_head": (True, "le texte se cale sur la tête de l'invité (oui) ou reste à la position x/y (non)"),
        "head_dist": (-10, "distance entre la dernière ligne et le haut de la tête (px, négatif = plus haut)"),
        "head_margin": (10, "marge entre les mots et le bord de la tête (px)"),
        "split_extra": (0, "écart supplémentaire à droite de la tête sur la dernière ligne (px)"),
        "text_x": (145, "position x du texte (px)"),
        "text_y": (355, "position y du texte (px), utilisée si le texte ne se cale pas sur la tête"),
        **_TEXT,
        "text_front": (False, "texte devant la tête (oui) ou derrière, coupé par la tête (non)"),
    },
}


def _path(data_dir: Path) -> Path:
    return Path(data_dir) / "design.json"


def _overrides(data_dir: Path) -> dict:
    try:
        return json.loads(_path(data_dir).read_text())
    except Exception:  # noqa: BLE001
        return {}


def _coerce(default, value):
    if isinstance(default, bool):
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "oui", "yes", "on", "devant")
        return bool(value)
    if isinstance(default, int):
        return int(round(float(value)))
    return round(float(value), 3)


def load(data_dir: Path, fmt: str) -> dict:
    """Defaults + overrides for one format, read from disk now."""
    ov = _overrides(data_dir).get(fmt, {})
    out = {}
    for name, (default, _) in PARAMS[fmt].items():
        try:
            out[name] = _coerce(default, ov[name]) if name in ov else default
        except (TypeError, ValueError):
            out[name] = default
    return out


def set_value(data_dir: Path, fmt: str, name: str, value) -> object:
    """value: a number/bool, or a string like "+20" / "-5" / "x1.1" relative to the current value. Returns the new value."""
    if fmt not in PARAMS or name not in PARAMS[fmt]:
        raise KeyError(f"{fmt}.{name}")
    default = PARAMS[fmt][name][0]
    cur = load(data_dir, fmt)[name]
    if isinstance(value, str) and not isinstance(default, bool):
        v = value.strip().replace(",", ".")
        if v[:1] in "+-" and len(v) > 1:
            new = cur + float(v)
        elif v[:1].lower() == "x" and len(v) > 1:
            new = cur * float(v[1:])
        else:
            new = float(v)
    else:
        new = value
    new = _coerce(default, new)
    if name.endswith("_scale"):
        new = min(2.0, max(0.5, new))
    allv = _overrides(data_dir)
    allv.setdefault(fmt, {})[name] = new
    _path(data_dir).write_text(json.dumps(allv, indent=1, ensure_ascii=False))
    return new


def reset(data_dir: Path, fmt: str) -> None:
    allv = _overrides(data_dir)
    allv.pop(fmt, None)
    _path(data_dir).write_text(json.dumps(allv, indent=1, ensure_ascii=False))


def describe(data_dir: Path, fmt: str) -> str:
    cur = load(data_dir, fmt)
    lines = []
    for name, (default, doc) in PARAMS[fmt].items():
        v = cur[name]
        shown = ("oui" if v else "non") if isinstance(v, bool) else v
        lines.append(f"{name} = {shown}" + ("" if v == default else f" (défaut {('oui' if default else 'non') if isinstance(default, bool) else default})")
                     + f" — {doc}")
    return f"Réglages {FORMATS[fmt]} :\n" + "\n".join(lines)
