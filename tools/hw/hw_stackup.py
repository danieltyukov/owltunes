"""Write the board stackup from setup.toml into a .kicad_pcb as a (stackup ...) block.

setup.toml lists the layers between the solder masks, top to bottom, as [[stackup.layer]] tables
(name, type, thickness in mm, and for dielectrics material, epsilon_r, loss_tangent). Silkscreen,
paste and mask layers are added around them. The total of the listed layers must equal
thickness_mm; the solder mask is not counted, as JLCPCB quotes the thickness without it.
"""

from __future__ import annotations

MASK_MM = 0.01


def total_mm(cfg: dict) -> float:
    return round(sum(layer["thickness"] for layer in cfg["stackup"]["layer"]), 4)


def validate(cfg: dict) -> list[str]:
    errors = []
    total = total_mm(cfg)
    if abs(total - cfg["thickness_mm"]) > 0.005:
        errors.append(f"stackup layers add up to {total} mm, thickness_mm is {cfg['thickness_mm']}")
    coppers = [layer for layer in cfg["stackup"]["layer"] if layer["type"] == "copper"]
    if len(coppers) != cfg["copper_layers"]:
        errors.append(f"stackup has {len(coppers)} copper layers, copper_layers is {cfg['copper_layers']}")
    return errors


def build(cfg: dict) -> str:
    def fmt(v: float) -> str:
        return f"{v:g}"

    rows = [("F.SilkS", "Top Silk Screen", None), ("F.Paste", "Top Solder Paste", None),
            ("F.Mask", "Top Solder Mask", MASK_MM)]
    dielectric = 0
    for layer in cfg["stackup"]["layer"]:
        rows.append((layer.get("name", ""), layer["type"], layer))
    rows += [("B.Mask", "Bottom Solder Mask", MASK_MM), ("B.Paste", "Bottom Solder Paste", None),
             ("B.SilkS", "Bottom Silk Screen", None)]
    lines = ["\t\t(stackup"]
    for name, kind, extra in rows:
        if isinstance(extra, dict):
            if kind == "copper":
                lines.append(f'\t\t\t(layer "{name}" (type "copper") (thickness {fmt(extra["thickness"])}))')
            else:
                dielectric += 1
                lines.append(
                    f'\t\t\t(layer "dielectric {dielectric}" (type "{kind}") (thickness {fmt(extra["thickness"])}) '
                    f'(material "{extra.get("material", "FR4")}") (epsilon_r {fmt(extra.get("epsilon_r", 4.5))}) '
                    f'(loss_tangent {fmt(extra.get("loss_tangent", 0.02))}))'
                )
        elif extra is None:
            lines.append(f'\t\t\t(layer "{name}" (type "{kind}"))')
        else:
            lines.append(f'\t\t\t(layer "{name}" (type "{kind}") (thickness {fmt(extra)}))')
    lines.append(f'\t\t\t(copper_finish "{cfg["stackup"].get("finish", "ENIG")}")')
    lines.append("\t\t\t(dielectric_constraints no)")
    lines.append("\t\t)")
    return "\n".join(lines) + "\n"


def _remove_block(text: str, start: int) -> str:
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                end = i + 1
                if text[end : end + 1] == "\n":
                    end += 1
                line_start = text.rfind("\n", 0, start) + 1
                return text[:line_start] + text[end:]
    raise ValueError("unbalanced stackup block")


def apply(text: str, cfg: dict) -> str:
    """Replace or insert the (stackup ...) block as the first child of (setup ...)."""
    pos = text.find("(stackup")
    if pos != -1:
        text = _remove_block(text, pos)
    anchor = text.find("(setup\n")
    if anchor == -1:
        raise ValueError("no (setup ...) block in the PCB")
    insert_at = anchor + len("(setup\n")
    return text[:insert_at] + build(cfg) + text[insert_at:]
