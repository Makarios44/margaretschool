"""Conteúdo do tutorial, por perfil. Texto curto, uma ideia por passo, sem termos técnicos.

Cada passo: titulo, icone (Bootstrap Icons), intro (frase de abertura), acoes (lista "onde clicar -> o que acontece").
Em acoes, o que está entre [colchetes] aparece com cara de botão, para a pessoa reconhecer na tela.
"""


def perfil(user):
    if user.is_superuser:
        return "admin"
    return "secretaria" if user.is_staff else "familia"


NOMES = {"admin": "Administração", "secretaria": "Secretaria", "familia": "Família ou professor"}

BASE = [
    {"titulo": "Bem-vindo(a) ao sistema da escola", "icone": "bi-emoji-smile",
     "intro": "Em poucos passos você vai conhecer tudo. Pode ir no seu tempo e voltar aqui quando quiser pelo botão [Ajuda] no menu.",
     "acoes": ["Use [Próximo] para avançar e [Voltar] para rever um passo.",
               "Não tem como estragar nada: este tutorial é só para ler."]},
    {"titulo": "Como se movimentar", "icone": "bi-compass",
     "intro": "O menu fica no alto de todas as telas.",
     "acoes": ["No celular, toque em [Menu] para abrir a lista de opções.",
               "Toque em [Painel] a qualquer momento para voltar à tela inicial.",
               "Quando terminar, toque em [Sair] para fechar o seu acesso com segurança."]},
    {"titulo": "Calendário da escola", "icone": "bi-calendar3",
     "intro": "Veja feriados, reuniões, provas, passeios e dias sem aula.",
     "acoes": ["Toque em [Calendário] no menu.",
               "Use as setas para passar de um mês para outro.",
               "Toque em um evento para ver data, horário e detalhes."]},
    {"titulo": "Avisos e fotos", "icone": "bi-megaphone",
     "intro": "A escola publica comunicados e fotos das atividades.",
     "acoes": ["Na página inicial, os avisos aparecem no alto, com um botão quando há algo para fazer.",
               "Toque em [Fotos] no menu para ver os álbuns das atividades."]},
]

SECRETARIA = [
    {"titulo": "Alunos", "icone": "bi-people",
     "intro": "Aqui ficam os dados de cada criança: responsáveis, contatos de emergência, alergias e cuidados.",
     "acoes": ["Toque em [Alunos] no menu.",
               "Para achar alguém, digite só uma parte do nome. A ordem das palavras não importa e acentos também não.",
               "Toque em [Novo aluno] para cadastrar. Os campos com * são obrigatórios."]},
    {"titulo": "Matrículas e rematrículas", "icone": "bi-journal-check",
     "intro": "Matricule o aluno em uma turma e imprima a ficha e o contrato.",
     "acoes": ["Toque em [Matrículas] e depois em [Nova matrícula].",
               "Digite o nome do aluno: a lista vai diminuindo até sobrar só ele. Toque no nome certo.",
               "Escolha a turma, confira a mensalidade e o dia de vencimento e toque em [Salvar].",
               "Na matrícula pronta, use os botões para imprimir a ficha e o contrato."]},
    {"titulo": "Pré-matrículas pelo link", "icone": "bi-inbox",
     "intro": "A família preenche os dados em casa; você só confere e aprova.",
     "acoes": ["Toque em [Pré-matrículas] e crie um link.",
               "Envie o link para a família pelo WhatsApp.",
               "Quando ela enviar, a solicitação aparece na lista para você analisar e aprovar."]},
    {"titulo": "Chamada de todo dia (frequência)", "icone": "bi-clipboard-check",
     "intro": "Funciona muito bem no celular. Leva menos de um minuto por turma.",
     "acoes": ["Toque em [Frequência], escolha o dia e toque na turma.",
               "Todos já vêm como Presente. Toque em [Falta] só para quem faltou.",
               "Se a falta tem motivo, toque em [Justificada] e escreva (por exemplo: atestado médico).",
               "Confira os totais na barra de baixo e toque em [Salvar chamada].",
               "Depois, em [Relatórios], veja o mês inteiro da turma. Dá para imprimir."]},
    {"titulo": "Financeiro", "icone": "bi-cash-coin",
     "intro": "Mensalidades, recibos, descontos e despesas da escola.",
     "acoes": ["Toque em [Financeiro] para ver quem pagou e quem está em atraso.",
               "Abra uma mensalidade para registrar o pagamento e gerar o recibo.",
               "Em despesas, lance os gastos da escola e acompanhe os gráficos do mês."]},
    {"titulo": "Documentos escolares", "icone": "bi-file-earmark-text",
     "intro": "Declarações, histórico, transferência, ficha individual e folha de ponto dos professores.",
     "acoes": ["Toque em [Documentos] e escolha o que quer emitir.",
               "Escolha o aluno digitando o nome e confira os dados que já vêm preenchidos.",
               "Na declaração de frequência, os dias e as faltas vêm da chamada diária.",
               "Toque em [Imprimir] ou salve em PDF."]},
    {"titulo": "Divulgação: avisos e fotos", "icone": "bi-brush",
     "intro": "Você controla o que aparece na página inicial da escola.",
     "acoes": ["Toque em [Divulgação] e depois em [Novo anúncio].",
               "Coloque o título, a imagem (por exemplo, o banner da rematrícula) e as datas em que ele deve aparecer.",
               "Para fotos das atividades, crie um álbum. Antes de publicar, confirme que a escola tem autorização de uso de imagem."]},
]

ADMIN = [
    {"titulo": "Administração", "icone": "bi-gear",
     "intro": "A parte de configuração da escola. Só administradores entram aqui.",
     "acoes": ["Toque em [Administração] no menu.",
               "Cadastre o ano letivo e as turmas antes de fazer matrículas.",
               "Em usuários, crie o acesso de cada pessoa e escolha o perfil: Família ou professor, Secretaria ou Administrador.",
               "Em dados da escola, preencha CNPJ, endereço e direção: isso aparece nos documentos impressos."]},
]

FINAL = {"titulo": "Pronto! Agora é só usar", "icone": "bi-patch-check",
         "intro": "Você viu o essencial. Se esquecer algo, o botão [Ajuda] no menu mostra este passo a passo de novo.",
         "acoes": ["Para aumentar as letras, use os botões [A+] e [A−] no alto desta página.",
                   "Em caso de dúvida, fale com a secretaria da escola."]}


def passos(user):
    p = perfil(user)
    lista = list(BASE)
    if p in ("secretaria", "admin"):
        lista += SECRETARIA
    if p == "admin":
        lista += ADMIN
    lista.append(FINAL)
    return lista
