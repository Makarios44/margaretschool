MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho",
         "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]


def data_extenso(d):
    """24 de outubro de 2026 (mês em minúsculas, como em documentos formais)."""
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"
