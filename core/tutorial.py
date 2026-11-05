"""Conteúdo do tutorial, por perfil. Texto curto, uma ideia por passo, sem termos técnicos.

Cada passo: titulo, icone (Bootstrap Icons), intro, acoes (lista "onde clicar -> o que acontece").
Em textos, o que está entre [colchetes] aparece desenhado como botão.

Passos de módulo também podem ter:
  onde    - caminho no menu ("Menu → Matrículas → Nova matrícula")
  abrir   - (nome da rota, rótulo do botão) para abrir a tela direto
  precisa - chaves de REQUISITOS que precisam existir antes (lista fixa "Antes de começar", com link para a tela de cada um)

O tutorial só ENSINA: ele não consulta o que já foi cadastrado nem mostra o que está pronto ou pendente.
(O banco só é consultado por faltando(), usado nos avisos das telas de cadastro, como Nova matrícula.)
"""
from django.urls import reverse


def perfil(user):
    if user.is_superuser:
        return "admin"
    return "secretaria" if user.is_staff else "familia"


NOMES = {"admin": "Administração", "secretaria": "Secretaria", "familia": "Família ou professor"}


# ---------- o que precisa existir antes de quê ----------
# ordem = ordem sugerida de preparação. "depende" = o que precisa estar pronto antes de poder fazer este.
REQUISITOS = {
    "escola": {"titulo": "Dados da escola", "rota": "adm_escola", "botao": "Preencher os dados",
               "onde": "Menu → Administração → Dados da escola",
               "por_que": "CNPJ, endereço e direção saem escritos nos documentos impressos.", "so_admin": True, "depende": []},
    "ano": {"titulo": "Ano letivo", "rota": "adm_ano_novo", "botao": "Criar o ano letivo",
            "onde": "Menu → Administração → Anos letivos → Novo ano letivo",
            "por_que": "Turmas, matrículas e frequência pertencem a um ano letivo (por exemplo, 2027).", "depende": []},
    "ano_config": {"titulo": "Início e fim das aulas", "rota": "adm_anos", "botao": "Abrir os anos letivos",
                   "onde": "Menu → Administração → Anos letivos → botão [Aulas e bimestres]",
                   "por_que": "Com as datas, o sistema conta os dias letivos e avisa quando falta chamada.", "depende": ["ano"]},
    "feriados": {"titulo": "Feriados do ano", "rota": "feriados_gerar", "botao": "Gerar os feriados",
                 "onde": "Menu → Administração → Feriados do ano",
                 "por_que": "Marca no calendário os feriados nacionais, do estado e do município, e os dias sem aula.", "depende": []},
    "turma": {"titulo": "Turma", "rota": "adm_turma_nova", "botao": "Criar uma turma",
              "onde": "Menu → Administração → Turmas → Nova turma",
              "por_que": "O aluno é matriculado em uma turma. Sem turma não dá para matricular nem fazer chamada.", "depende": ["ano"]},
    "usuarios": {"titulo": "Acesso das pessoas", "rota": "adm_usuario_novo", "botao": "Criar um acesso",
                 "onde": "Menu → Administração → Usuários → Novo usuário",
                 "por_que": "Cada pessoa entra com o próprio usuário e senha, no perfil certo.", "so_admin": True, "depende": []},
    "aluno": {"titulo": "Aluno cadastrado", "rota": "aluno_create", "botao": "Cadastrar um aluno",
              "onde": "Menu → Alunos → Novo aluno",
              "por_que": "Primeiro se cadastra a criança (dados e responsáveis); depois se faz a matrícula.", "depende": []},
    "matricula": {"titulo": "Matrícula do aluno na turma", "rota": "matricula_create", "botao": "Matricular um aluno",
                  "onde": "Menu → Matrículas → Nova matrícula",
                  "por_que": "É a matrícula que coloca o aluno na turma, na chamada, no financeiro e nos documentos.",
                  "depende": ["ano", "turma", "aluno"]},
    "mensalidades": {"titulo": "Mensalidades geradas", "rota": "matricula_list", "botao": "Abrir as matrículas",
                     "onde": "Menu → Matrículas → abrir a matrícula → botão [Gerar mensalidades]",
                     "por_que": "As mensalidades NÃO são criadas sozinhas: você gera os meses na matrícula do aluno.",
                     "depende": ["matricula"]},
    "chamada": {"titulo": "Primeira chamada feita", "rota": "frequencia", "botao": "Fazer a chamada",
                "onde": "Menu → Frequência → escolher o dia → tocar na turma",
                "por_que": "Cada chamada salva conta como um dia de aula e alimenta os relatórios e as declarações.",
                "depende": ["turma", "matricula"]},
}


def estado():
    """{chave: pronto?} consultando o banco. Poucas consultas simples."""
    from django.contrib.auth import get_user_model

    from administracao.models import ConfiguracaoEscola
    from alunos.models import Aluno
    from calendario.models import Evento
    from financeiro.models import Cobranca
    from frequencia.models import Chamada
    from matriculas.models import AnoLetivo, Matricula, Turma

    return {
        "escola": ConfiguracaoEscola.objects.exists(),
        "ano": AnoLetivo.objects.exists(),
        "ano_config": AnoLetivo.objects.filter(inicio_aulas__isnull=False, fim_aulas__isnull=False).exists(),
        "feriados": Evento.objects.filter(origem=Evento.Origem.AUTOMATICO).exists(),
        "turma": Turma.objects.exists(),
        "usuarios": get_user_model().objects.filter(is_active=True).count() > 1,
        "aluno": Aluno.objects.exists(),
        "matricula": Matricula.objects.exists(),
        "mensalidades": Cobranca.objects.exists(),
        "chamada": Chamada.objects.exists(),
    }


def requisito(chave):
    r = REQUISITOS[chave]
    return {"chave": chave, "titulo": r["titulo"], "url": reverse(r["rota"]), "botao": r["botao"]}


def faltando(chaves):
    """Requisitos que ainda não existem no banco (para avisos nas telas de cadastro). Cada item: titulo, url, botao."""
    pronto = estado()
    return [requisito(c) for c in chaves if not pronto[c]]


def lista_comece(user):
    """Lista fixa da ordem de preparação, com o que cada etapa precisa antes. Não depende dos dados da escola."""
    admin = user.is_superuser
    visiveis = {k for k, r in REQUISITOS.items() if admin or not r.get("so_admin")}
    itens = []
    for chave, r in REQUISITOS.items():
        if chave not in visiveis:
            continue
        itens.append({"chave": chave, "titulo": r["titulo"], "onde": r["onde"], "por_que": r["por_que"],
                      "url": reverse(r["rota"]), "botao": r["botao"],
                      "precisa": [requisito(d) for d in r["depende"] if d in visiveis]})
    return itens


# ---------- passos ----------
INICIO = [
    {"titulo": "Bem-vindo(a) ao sistema da escola", "icone": "bi-emoji-smile",
     "intro": "Em poucos passos você vai conhecer tudo. Pode ir no seu tempo e voltar aqui quando quiser pelo botão [Ajuda] no menu.",
     "acoes": ["Use [Próximo] para avançar e [Voltar] para rever um passo.",
               "Não tem como estragar nada: este tutorial é só para ler."]},
    {"titulo": "Como se movimentar", "icone": "bi-compass",
     "intro": "O menu fica no alto de todas as telas.",
     "acoes": ["No celular, toque em [Menu] para abrir a lista de opções.",
               "Toque em [Painel] a qualquer momento para voltar à tela inicial.",
               "Quando terminar, toque em [Sair] para fechar o seu acesso com segurança."]},
]

MAPA = {"titulo": "Onde fica cada coisa", "icone": "bi-map", "tipo": "mapa",
        "intro": "Tudo está no [Menu] no alto da tela. Toque em um item abaixo para abrir a tela direto.",
        "acoes": []}

COMECE = {"titulo": "A ordem certa das coisas", "icone": "bi-list-check", "tipo": "comece",
          "intro": "Algumas coisas só podem ser feitas depois de outras. Por exemplo: para matricular um aluno, a turma precisa existir antes. "
                   "Esta é a ordem para preparar a escola, de cima para baixo.",
          "acoes": []}

CALENDARIO = {"titulo": "Calendário da escola", "icone": "bi-calendar3",
              "intro": "Veja feriados, reuniões, provas, passeios e dias sem aula.",
              "onde": "Menu → Calendário", "abrir": ("calendario", "Abrir o calendário"),
              "acoes": ["Use as setas para passar de um mês para outro.",
                        "Toque em um evento para ver data, horário e detalhes."]}

AVISOS = {"titulo": "Avisos e fotos", "icone": "bi-megaphone",
          "intro": "A escola publica comunicados e fotos das atividades.",
          "onde": "Menu → Fotos (os avisos aparecem na página inicial)", "abrir": ("galeria", "Ver as fotos"),
          "acoes": ["Na página inicial, os avisos aparecem no alto, com um botão quando há algo para fazer.",
                    "Toque em [Fotos] no menu para ver os álbuns das atividades."]}

SECRETARIA = [
    {"titulo": "Alunos", "icone": "bi-people",
     "intro": "Aqui ficam os dados de cada criança: responsáveis, contatos de emergência, alergias e cuidados.",
     "onde": "Menu → Alunos", "abrir": ("aluno_list", "Abrir os alunos"),
     "acoes": ["Para achar alguém, digite só uma parte do nome. A ordem das palavras não importa e acentos também não.",
               "Toque em [Novo aluno] para cadastrar. Os campos com * são obrigatórios.",
               "Cadastrar o aluno ainda não o coloca em uma turma: isso é feito na matrícula."]},
    {"titulo": "Matrículas e rematrículas", "icone": "bi-journal-check",
     "intro": "A matrícula coloca o aluno em uma turma. Depois dela, saem a ficha, o contrato, as mensalidades e a chamada.",
     "onde": "Menu → Matrículas → Nova matrícula", "abrir": ("matricula_create", "Abrir a nova matrícula"),
     "precisa": ["ano", "turma", "aluno"],
     "acoes": ["Digite o nome do aluno: a lista vai diminuindo até sobrar só ele. Toque no nome certo.",
               "Escolha o ano letivo e a turma, confira a mensalidade e o dia de vencimento e toque em [Salvar].",
               "Na matrícula pronta, use os botões para imprimir a ficha e o contrato.",
               "No começo do ano seguinte, use [Rematrículas] para renovar os alunos que continuam."]},
    {"titulo": "Pré-matrículas pelo link", "icone": "bi-inbox",
     "intro": "A família preenche os dados em casa; você só confere e aprova.",
     "onde": "Menu → Pré-matrículas → Novo link", "abrir": ("pre_matricula_lista", "Abrir as pré-matrículas"),
     "precisa": ["ano", "turma"],
     "acoes": ["Crie um link e envie para a família pelo WhatsApp (ele vale por 14 dias).",
               "Quando ela enviar, a solicitação aparece na lista para você analisar.",
               "Ao aprovar, escolha a turma: o sistema cria o aluno e a matrícula sozinho. Por isso a turma precisa existir antes."]},
    {"titulo": "Chamada de todo dia (frequência)", "icone": "bi-clipboard-check",
     "intro": "Funciona muito bem no celular. Leva menos de um minuto por turma.",
     "onde": "Menu → Frequência", "abrir": ("frequencia", "Abrir a frequência"),
     "precisa": ["ano", "turma", "matricula"],
     "acoes": ["Escolha o dia e toque na turma. Só aparecem alunos com matrícula ativa.",
               "Todos já vêm como Presente. Toque em [Falta] só para quem faltou.",
               "Se a falta tem motivo, toque em [Justificada] e escreva (por exemplo: atestado médico).",
               "Confira os totais na barra de baixo e toque em [Salvar chamada].",
               "Depois, em [Relatórios], veja o mês inteiro da turma. Dá para imprimir."]},
    {"titulo": "Financeiro", "icone": "bi-cash-coin",
     "intro": "Mensalidades, recibos, descontos e despesas da escola.",
     "onde": "Menu → Financeiro", "abrir": ("financeiro_painel", "Abrir o financeiro"),
     "precisa": ["matricula", "mensalidades"],
     "acoes": ["Primeiro gere os meses: abra a matrícula do aluno e toque em [Gerar mensalidades]. Elas não são criadas sozinhas.",
               "Em [Financeiro], veja quem pagou e quem está em atraso.",
               "Abra uma mensalidade para registrar o pagamento e gerar o recibo.",
               "Em despesas, lance os gastos da escola e acompanhe os gráficos do mês."]},
    {"titulo": "Documentos escolares", "icone": "bi-file-earmark-text",
     "intro": "Declarações, histórico, transferência, ficha individual e folha de ponto dos professores.",
     "onde": "Menu → Documentos", "abrir": ("documento_list", "Abrir os documentos"),
     "precisa": ["escola", "aluno", "matricula"],
     "acoes": ["Escolha o documento e depois o aluno, digitando o nome.",
               "Confira os dados que já vêm preenchidos. Na declaração de frequência, os dias e as faltas vêm da chamada diária.",
               "Toque em [Imprimir] ou salve em PDF.",
               "A folha de ponto dos professores não precisa de matrícula: é só digitar o nome e o mês."]},
    {"titulo": "Divulgação: avisos e fotos", "icone": "bi-brush",
     "intro": "Você controla o que aparece na página inicial da escola.",
     "onde": "Menu → Divulgação", "abrir": ("divulgacao", "Abrir a divulgação"),
     "acoes": ["Toque em [Novo anúncio]. Coloque o título, a imagem (por exemplo, o banner da rematrícula) e as datas em que ele deve aparecer.",
               "Para fotos das atividades, crie um álbum. Antes de publicar, confirme que a escola tem autorização de uso de imagem."]},
]

ADMIN = [
    {"titulo": "Administração", "icone": "bi-gear",
     "intro": "A parte de configuração da escola. É aqui que começa tudo.",
     "onde": "Menu → Administração", "abrir": ("administracao", "Abrir a administração"),
     "acoes": ["Em [Anos letivos] e [Turmas], cadastre a base da escola antes de matricular.",
               "Em [Usuários], crie o acesso de cada pessoa e escolha o perfil: Família ou professor, Secretaria ou Administrador.",
               "Em [Dados da escola], preencha CNPJ, endereço e direção: isso aparece nos documentos impressos.",
               "Em [Categorias de despesa], ajuste os grupos usados para lançar gastos."]},
]

FINAL = {"titulo": "Pronto! Agora é só usar", "icone": "bi-patch-check",
         "intro": "Você viu o essencial. Se esquecer algo, o botão [Ajuda] no menu mostra este passo a passo de novo.",
         "acoes": ["Para aumentar as letras, use os botões [A+] e [A−] no alto desta página.",
                   "Em caso de dúvida, fale com a secretaria da escola."]}

MODULOS_MAPA = [  # (ícone, nome, para que serve, rota)
    ("bi-people", "Alunos", "Cadastro das crianças, responsáveis e contatos.", "aluno_list"),
    ("bi-journal-check", "Matrículas", "Matricular, rematricular, ficha e contrato.", "matricula_list"),
    ("bi-inbox", "Pré-matrículas", "Pedidos que as famílias enviam pelo link.", "pre_matricula_lista"),
    ("bi-clipboard-check", "Frequência", "Chamada diária e relatórios de faltas.", "frequencia"),
    ("bi-cash-coin", "Financeiro", "Mensalidades, recibos e despesas.", "financeiro_painel"),
    ("bi-file-earmark-text", "Documentos", "Declarações, histórico, transferência e folha de ponto.", "documento_list"),
    ("bi-calendar3", "Calendário", "Feriados, eventos e dias letivos.", "calendario"),
    ("bi-brush", "Divulgação", "Anúncios e fotos da página inicial.", "divulgacao"),
    ("bi-gear", "Administração", "Anos letivos, turmas, usuários e dados da escola.", "administracao"),
]


def _resolver(passo, admin):
    """Transforma 'abrir' e 'precisa' em links (itens só de administrador somem para os outros)."""
    p = dict(passo)
    if "abrir" in p:
        rota, rotulo = p["abrir"]
        p["abrir"] = {"url": reverse(rota), "rotulo": rotulo}
    if "precisa" in p:
        p["precisa"] = [requisito(c) for c in p["precisa"] if admin or not REQUISITOS[c].get("so_admin")]
    return p


def passos(user):
    p = perfil(user)
    staff = p in ("secretaria", "admin")
    lista = list(INICIO)
    if staff:
        mapa = dict(MAPA)
        mapa["modulos"] = [{"icone": i, "nome": n, "descricao": d, "url": reverse(r)} for i, n, d, r in MODULOS_MAPA]
        comece = dict(COMECE)
        comece["itens"] = lista_comece(user)
        lista += [mapa, comece]
    lista += [CALENDARIO, AVISOS]
    if staff:
        lista += SECRETARIA
    if p == "admin":
        lista += ADMIN
    lista.append(FINAL)
    return [_resolver(x, p == "admin") for x in lista]
