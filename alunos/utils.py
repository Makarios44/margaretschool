import unicodedata


def normalizar(texto):
    """minúsculas, sem acentos e com espaços únicos: 'José  da Silva' -> 'jose da silva'."""
    sem_acento = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return " ".join(sem_acento.lower().split())


def filtrar_por_nome(qs, texto, campo="nome_busca"):
    """Cada palavra digitada precisa aparecer no nome (em qualquer ordem, sem acento)."""
    for palavra in normalizar(texto).split():
        qs = qs.filter(**{f"{campo}__contains": palavra})
    return qs


def resumo_aluno(aluno):
    """Dados que ajudam a diferenciar alunos com o mesmo nome."""
    resp = aluno.contratante
    mat = aluno.matricula_atual
    turma = f"{mat.turma.nome} · {mat.get_turno_display()} ({mat.ano_letivo})" if mat else ""
    partes = [f"Nasc. {aluno.data_nascimento:%d/%m/%Y} ({aluno.idade})"]
    if resp:
        partes.append(f"Resp.: {resp.nome}")
    if turma:
        partes.append(turma)
    return {
        "id": aluno.pk, "nome": aluno.nome, "idade": aluno.idade, "responsavel": resp.nome if resp else "",
        "turma": turma, "detalhe": " · ".join(partes),
    }
