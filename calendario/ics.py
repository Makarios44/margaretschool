"""Gera o arquivo .ics (iCalendar) para assinar o calendário no Google Agenda, iPhone, Outlook."""
from datetime import datetime, timedelta, timezone


def _escapar(texto):
    return (texto.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
            .replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "\\n"))


def _dobrar(linha):
    """Linhas do iCalendar têm no máximo 75 bytes; continuam na linha seguinte com um espaço."""
    dados = linha.encode("utf-8")
    if len(dados) <= 75:
        return [linha]
    partes, atual = [], b""
    for ch in linha:
        b = ch.encode("utf-8")
        limite = 75 if not partes else 74
        if len(atual) + len(b) > limite:
            partes.append(atual.decode("utf-8"))
            atual = b""
        atual += b
    partes.append(atual.decode("utf-8"))
    return [partes[0]] + [" " + p for p in partes[1:]]


def gerar_ics(eventos, nome_calendario, dominio="margaret-school"):
    agora = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    linhas = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Margaret School//Calendario escolar//PT-BR",
        "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_escapar(nome_calendario)}", "X-WR-TIMEZONE:America/Fortaleza",
    ]
    for ev in eventos:
        linhas += ["BEGIN:VEVENT", f"UID:evento-{ev.pk}@{dominio}", f"DTSTAMP:{agora}"]
        if ev.hora_inicio:  # horário local "flutuante": aparece na mesma hora em qualquer fuso
            ini = datetime.combine(ev.data_inicio, ev.hora_inicio)
            fim_dia = ev.ultimo_dia
            fim = datetime.combine(fim_dia, ev.hora_fim) if ev.hora_fim else ini + timedelta(hours=1)
            linhas += [f"DTSTART:{ini:%Y%m%dT%H%M%S}", f"DTEND:{fim:%Y%m%dT%H%M%S}"]
        else:  # dia inteiro: o fim é exclusivo
            linhas += [f"DTSTART;VALUE=DATE:{ev.data_inicio:%Y%m%d}",
                       f"DTEND;VALUE=DATE:{ev.ultimo_dia + timedelta(days=1):%Y%m%d}"]
        linhas.append(f"SUMMARY:{_escapar(ev.titulo)}")
        if ev.local:
            linhas.append(f"LOCATION:{_escapar(ev.local)}")
        descricao = ev.descricao
        if ev.sem_aula:
            descricao = ("Não há aula. " + descricao).strip()
        if descricao:
            linhas.append(f"DESCRIPTION:{_escapar(descricao)}")
        linhas.append(f"CATEGORIES:{_escapar(ev.get_categoria_display())}")
        linhas.append("END:VEVENT")
    linhas.append("END:VCALENDAR")
    saida = []
    for l in linhas:
        saida += _dobrar(l)
    return "\r\n".join(saida) + "\r\n"
