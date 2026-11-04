import re
from urllib.parse import quote


def links_contato(escola):
    """Links de contato montados a partir dos dados da escola (None quando falta a informação)."""
    telefone = escola.get("telefone", "")
    digitos = re.sub(r"\D", "", telefone)
    if digitos.startswith("55") and len(digitos) in (12, 13):
        internacional = digitos
    elif len(digitos) in (10, 11):
        internacional = "55" + digitos
    else:
        internacional = ""

    perfil = (escola.get("instagram") or "").strip().rstrip("/")
    if "instagram.com/" in perfil:
        perfil = perfil.split("instagram.com/")[-1].split("?")[0].strip("/")
    perfil = perfil.lstrip("@")

    endereco = ", ".join(p for p in (escola.get("endereco"), escola.get("cidade")) if p)
    return {
        "whatsapp": f"https://wa.me/{internacional}" if internacional else "",
        "tel": f"tel:+{internacional}" if internacional else "",
        "instagram": f"https://www.instagram.com/{perfil}/" if perfil else "",
        "instagram_perfil": perfil,
        "mapa": f"https://www.google.com/maps/search/?api=1&query={quote(endereco)}" if endereco else "",
    }
