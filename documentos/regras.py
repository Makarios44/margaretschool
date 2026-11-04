"""Regras educacionais que mudam conforme a etapa de ensino.

Base (conferir sempre com o conselho de educação do sistema da escola):
- LDB, art. 31: na educação infantil a avaliação é feita por acompanhamento e registro do
  desenvolvimento, sem objetivo de promoção (nem retenção), mesmo para o acesso ao ensino
  fundamental; carga mínima de 800 h em 200 dias; controle de frequência, com mínimo de 60%
  na pré-escola; expedição de documentação que ateste os processos de desenvolvimento e
  aprendizagem da criança.
- LDB, art. 24, VI: no ensino fundamental, frequência mínima de 75% do total de horas letivas
  para aprovação.
- Lei 9.870/1999, art. 6º: é proibido reter documentos escolares por inadimplência.
"""
from matriculas.models import Etapa

INFANTIL = {Etapa.INFANTIL_CRECHE, Etapa.INFANTIL_PRE}

FREQUENCIA_MINIMA = {Etapa.INFANTIL_PRE: 60, Etapa.FUNDAMENTAL_INICIAIS: 75}
BASE_FREQUENCIA = {
    Etapa.INFANTIL_PRE: "LDB, art. 31, IV",
    Etapa.FUNDAMENTAL_INICIAIS: "LDB, art. 24, VI",
}

NOTA_INFANTIL = (
    "Na educação infantil, a avaliação é feita mediante acompanhamento e registro do "
    "desenvolvimento da criança, sem objetivo de promoção, mesmo para o acesso ao ensino "
    "fundamental (LDB, art. 31, I)."
)

# Sugestão inicial de componentes (anos iniciais). A secretaria confere conforme a matriz da escola.
COMPONENTES_SUGERIDOS = [
    "Língua Portuguesa", "Matemática", "Ciências", "História", "Geografia",
    "Arte", "Educação Física", "Ensino Religioso",
]

# Dados da escola exigidos para o documento ter validade; o rótulo aparece no aviso.
DADOS_OBRIGATORIOS = [
    ("cnpj", "CNPJ"), ("endereco", "endereço"), ("cidade", "cidade"),
    ("ato_autorizacao", "ato de credenciamento/autorização"),
    ("diretor", "nome da direção"), ("secretario", "nome do(a) secretário(a) escolar"),
]


def eh_infantil(etapa):
    return etapa in INFANTIL


def frequencia_minima(etapa):
    """Percentual mínimo previsto em lei (None quando a LDB não fixa, como na creche)."""
    return FREQUENCIA_MINIMA.get(etapa)


def escola_pendencias(escola):
    return [rotulo for chave, rotulo in DADOS_OBRIGATORIOS if not escola.get(chave)]
