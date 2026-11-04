# Margaret School

Site da escola: página inicial, login, painel, **gestão de alunos**, **matrículas/rematrículas**, **controle financeiro**, **documentos escolares**, **calendário escolar** e **pré-matrícula online**.
Django + Bootstrap 5 + JS.

## Rodar localmente

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser # primeiro usuário (direção)
python manage.py runserver
```

Abra http://127.0.0.1:8000/ e rode `python manage.py test` para conferir os testes.

## Primeiros passos

1. Entre como administrador e abra **Administração → Dados da escola** (CNPJ, direção, atos oficiais, multa e juros).
2. Em **Administração → Anos letivos**, crie o ano (marque "Ano atual") e, em **Turmas**, cadastre as turmas (nome, turno, etapa, vagas).
3. Em **Administração → Usuários**, crie as contas e escolha o perfil: *Família/professor* (só painel e calendário),
   *Secretaria* (alunos, matrículas, financeiro, documentos) ou *Administrador* (tudo, inclusive usuários e dados da escola).
   Só a equipe acessa alunos e matrículas; famílias e professores logados veem apenas o painel.
4. No painel: **Alunos → Novo aluno**, depois **Matrículas → Nova matrícula**.

## Rotas

| URL                          | O que é                                           |
|------------------------------|---------------------------------------------------|
| `/`                          | Página principal                                  |
| `/entrar/`, `/sair/`         | Login / logout                                    |
| `/painel/`                   | Painel                                            |
| `/alunos/`                   | Lista, busca e filtros (ano, turma, situação)     |
| `/alunos/novo/`              | Cadastro completo                                 |
| `/alunos/<id>/`              | Ficha do aluno                                    |
| `/matriculas/`               | Lista de matrículas                               |
| `/matriculas/nova/`          | Nova matrícula (aceita `?aluno=&ano=&tipo=`)      |
| `/matriculas/rematriculas/`  | Alunos do ano anterior ainda sem rematrícula      |
| `/matriculas/<id>/`          | Detalhe, valores e checklist de documentos        |
| `/matriculas/<id>/ficha/`    | Ficha de matrícula para imprimir                  |
| `/matriculas/<id>/contrato/` | Contrato para imprimir                            |
| `/financeiro/`               | Cobranças: filtros por mês, situação e tipo       |
| `/financeiro/gerar/<mat>/`   | Gera as mensalidades do ano de uma matrícula      |
| `/financeiro/<id>/receber/`  | Registra pagamento (forma, desconto, multa, juros)|
| `/financeiro/<id>/recibo/`   | Recibo para imprimir                              |
| `/financeiro/relatorio/`     | Relatório mensal de receitas e inadimplência      |
| `/documentos/`               | Livro de registro dos documentos emitidos         |
| `/documentos/emitir/`        | Escolher o aluno e emitir um documento            |
| `/documentos/ficha/<aluno>/` | Ficha individual do aluno (dados atuais)          |
| `/documentos/registros/<mat>/` | Registro escolar: frequência, resultado, parecer |
| `/frequencia/`               | Frequência diária: escolher dia e turma (equipe)  |
| `/frequencia/chamada/<turma>/<AAAA-MM-DD>/` | Chamada do dia (presente, falta, justificada)  |
| `/frequencia/aluno/`         | Frequência por aluno e período                    |
| `/frequencia/relatorio/`     | Relatório mensal e consolidado por turma (+ CSV)  |
| `/calendario/`               | Calendário do mês (público); também `/calendario/ano/2026/` e `/calendario/agenda/` |
| `/calendario/calendario.ics` | Assinatura no Google Agenda / iPhone / Outlook    |
| `/calendario/eventos/`       | Gerenciar eventos (equipe)                        |
| `/calendario/feriados/`      | Gerar feriados do ano (equipe)                    |
| `/calendario/dias-letivos/`  | Conferência de 200 dias / 800 horas (equipe)      |
| `/pre-matricula/<código>/`   | Formulário público da família (link individual)   |
| `/pre-matriculas/`           | Solicitações recebidas (equipe)                   |
| `/pre-matriculas/novo-link/` | Gerar link para uma família (equipe)              |
| `/pre-matriculas/links/`     | Links gerados: copiar de novo e desativar (equipe)|
| `/financeiro/`               | Painel financeiro (gráficos de receitas e despesas)|
| `/financeiro/cobrancas/`     | Lista de cobranças                                |
| `/financeiro/despesas/`      | Despesas: lista, lançamento, detalhe e CSV        |
| `/documentos/folha-de-ponto/`| Folha de ponto dos professores                    |
| `/alunos/buscar/?q=`         | Sugestões de alunos enquanto se digita (JSON)     |
| `/`                          | Página inicial: anúncios, avisos, eventos, fotos  |
| `/galeria/`, `/avisos/`      | Álbuns de fotos e avisos (públicos)               |
| `/divulgacao/`               | Anúncios e álbuns (equipe)                        |
| `/administracao/`            | Anos, turmas, categorias, usuários, dados da escola|

## Financeiro

1. Na matrícula, informe mensalidade, vencimento e (se houver) a **bolsa/desconto em %**.
2. Em **Matrículas → (aluno) → Gerar mensalidades**, crie o carnê do ano. Meses já gerados não são duplicados.
3. Em **Financeiro**, use **Receber** para registrar o pagamento (Pix, dinheiro, cartão ou transferência) e imprima o **recibo**.

- **Situações**: pendente (a vencer), vencida, paga e cancelada. "Vencida" é calculada pela data, não precisa marcar.
- **Multa e juros**: padrão de 2% de multa e 1% ao mês (proporcional aos dias de atraso). Mude com as variáveis
  `FIN_MULTA_PERCENTUAL` e `FIN_JUROS_MENSAL_PERCENTUAL` (use `0` para desligar). Mantenha iguais ao contrato,
  que passa a citar esses percentuais. Na hora de receber, os valores podem ser ajustados ou zerados.
- **Descontos**: a bolsa da matrícula vale para as mensalidades geradas depois dela; abatimentos avulsos
  entram na cobrança ou no momento do recebimento.
- **Erros de lançamento**: cobranças em aberto podem ser editadas ou canceladas; pagamentos podem ser estornados.

## Documentos escolares

Documentos: declaração de matrícula, declaração de frequência, histórico (ou ficha de registros
escolares, na educação infantil), documento de transferência e ficha individual do aluno.

1. **Dados oficiais da escola**: preencha em **Administração → Dados da escola** (CNPJ, INEP, mantenedora, endereço,
   ato de credenciamento, direção e secretaria, com os atos de designação). Se faltar algo, a tela
   avisa antes de imprimir.
2. **Etapa de cada turma**: em **Administração → Turmas**, confira o campo **Etapa de ensino** (creche, pré-escola ou
   fundamental – anos iniciais). Ele define o modelo do documento. As turmas antigas vieram como "pré-escola".
3. **Registro escolar** (Matrículas → aluno → *Registro escolar*): dias letivos, faltas, resultado e parecer do ano.
   No fundamental, também os componentes curriculares e o resultado de cada um. É a base do histórico.
4. **Emitir**: Documentos → *Emitir documento*, ou o painel "Documentos escolares" na ficha do aluno.
   Cada documento recebe número (ano/0001) e fica guardado como foi emitido: a segunda via sai igual,
   mesmo que o cadastro mude depois. Um documento errado é **anulado** (continua no registro, marcado).
5. **PDF**: *Imprimir / salvar em PDF* funciona em qualquer navegador. Para o botão *Baixar PDF*, instale
   `pip install -r requirements-pdf.txt`.

Regras aplicadas (confirme com o conselho de educação do sistema de ensino da escola, que pode exigir elementos
adicionais): na educação infantil não há aprovação nem retenção (LDB, art. 31, I) e a frequência mínima de 60% vale
para a pré-escola (art. 31, IV); no fundamental, 75% (LDB, art. 24, VI); documentos escolares não podem ser
retidos por inadimplência (Lei 9.870/1999, art. 6º), então o sistema nunca bloqueia a emissão por pendência financeira.

## Frequência diária

App `frequencia`, feito para uso no celular (botões grandes, uma coluna, barra de salvar fixa). Só a equipe (`is_staff`) acessa.

- **Chamada:** em `/frequencia/`, escolha o dia e a turma. Lista os alunos com matrícula ativa na data. Cada aluno vem como *Presente*; toque em *Falta* ou *Justificada* para quem faltou. A justificativa é obrigatória para falta justificada. Dá para refazer a chamada de dias passados (não de dias futuros) e excluir uma chamada se não houve aula.
- **Dia letivo:** cada chamada registrada conta como um dia de aula da turma. O sistema avisa quando o dia não é letivo pelo calendário (feriado, recesso, fim de semana), mas deixa salvar (reposição, sábado letivo).
- **Falta justificada conta como falta** no cálculo do percentual; a justificativa fica só como registro da escola. Percentual = presenças ÷ dias com chamada.
- **Consulta por aluno:** presenças, faltas, justificativas e percentual em qualquer período, com alerta quando fica abaixo do mínimo da etapa (60% na pré-escola, 75% no fundamental, conforme `documentos/regras.py`). O alerta é informativo.
- **Relatório da turma:** mensal ou consolidado (ano letivo, bimestres ou datas livres), com grade dia a dia, impressão/PDF pelo navegador e planilha CSV. Aponta dias letivos sem chamada.
- **Documentos:** na consulta do aluno, "Gerar declaração de frequência com estes dados" preenche período, dias letivos e faltas. No registro escolar anual, "Preencher … pela frequência diária" preenche os campos (nada é gravado até você salvar).

Ao atualizar um projeto existente: `python manage.py migrate` (cria as tabelas `Chamada` e `Presenca`).

## Calendário escolar

1. **Região**: o padrão é **Tibau do Sul/RN** (a Praia da Pipa é distrito de Tibau do Sul), configurável em
   *Administração → Dados da escola*. Em *Calendário → Gerenciar → Gerar feriados*, escolha o ano: saem os feriados
   nacionais (Sexta-feira Santa calculada pela Páscoa), os pontos facultativos (Carnaval, Quarta de Cinzas, Corpus Christi),
   o estadual do RN (3 de outubro) e, opcionalmente, datas comemorativas (inclui o Dia do Professor, feriado escolar).
   **Os feriados municipais de Tibau do Sul não vêm prontos** (não há fonte oficial confirmada no sistema): cadastre-os
   como evento (categoria *Feriado municipal*, marcando *Repete todo ano*) conforme o calendário da prefeitura, e eles
   são copiados para os próximos anos. Natal/RN tem os municipais pré-cadastrados (6 de janeiro e 21 de novembro).
2. **Confira todo ano**: estaduais e municipais mudam por lei/decreto. Ao sair o decreto do ano, compare com a lista gerada.
   Pontos facultativos vêm como "sem aula"; edite o evento se a escola funcionar.
3. **Eventos**: reuniões, avaliações, conselho de classe, entrega de boletins, matrículas, recesso, sábado letivo etc.,
   com horário, local, turmas e visibilidade (pública ou só da equipe). Eventos marcados "não há aula" saem da conta dos dias letivos.
4. **Dias letivos**: em *Configurar o ano*, informe início e fim das aulas e as horas por dia. A tela *Dias letivos* confere o
   mínimo legal (800 horas de 60 min em, no mínimo, 200 dias) e mostra o total por mês e por bimestre.
5. **Famílias**: o calendário é público (só eventos marcados como públicos); aniversários de alunos aparecem apenas para a equipe.
   Há assinatura por link (.ics) e versão para imprimir ou baixar em PDF (PDF direto exige `requirements-pdf.txt`).

## Pré-matrícula online

1. A equipe gera um link individual em *Pré-matrículas → Gerar link* (escolhe o ano letivo; dá para enviar direto pelo
   WhatsApp). Vale por **14 dias** e só pode ser usado **uma vez** (um link por criança; irmãos precisam de links separados).
2. A família abre o link, sem login, e preenche os dados da criança, do responsável e de um **contato de emergência**.
3. A solicitação aparece em *Pré-matrículas* (e no painel, com a contagem das pendentes). A secretaria pode marcar
   *em análise*, **rejeitar** ou **aprovar**, escolhendo turma, mensalidade, taxa e vencimento. A turma precisa ter vaga.
4. Ao aprovar, numa única operação, são criados: aluno, responsável, contato de emergência, matrícula (com a lista de
   documentos) e, se a taxa for maior que zero, a cobrança da taxa em aberto. O sistema abre a matrícula para você
   **gerar as mensalidades**.
5. Se já existir um aluno com o mesmo nome e data de nascimento, o sistema avisa e só segue se você marcar
   *Usar o cadastro existente* (cria apenas a matrícula) — evita cadastro duplicado.
6. Link enviado por engano? Em *Links gerados* dá para desativá-lo.

Cuidados: o formulário coleta dados de crianças. Não divulgue os links publicamente, restrinja o acesso da equipe e
defina quanto tempo as solicitações rejeitadas ficam guardadas (LGPD). O pagamento da taxa é registrado no Financeiro;
cobrança automática por Pix exigiria integração com um provedor de pagamento e não está incluída.

## Página inicial, anúncios e fotos (Divulgação)

A página inicial (`/`) mostra, na ordem: **anúncios em destaque** (carrossel com a arte da escola, como o banner de
matrículas), a apresentação da escola, **avisos e novidades**, **próximos eventos** do calendário, **fotos das atividades**
e o contato (endereço com "Como chegar", telefone e WhatsApp). Quem é da equipe vê uma barra com atalhos para editar.

- **Anúncios** (menu *Divulgação*): título, categoria (rematrícula, evento, aviso…), imagem/banner, texto curto, botão com link,
  e **quando aparece**: data de início e de fim, então o anúncio entra e sai do ar sozinho. Dá para agendar, desativar
  ou deixar só como novidade (fora do carrossel). Para carregar a arte "Matrículas abertas 2027" já pronta:
  `python manage.py carregar_banner_inicial` (ou envie a imagem pelo formulário).
- **Álbuns de fotos**: crie o álbum, envie várias fotos de uma vez, escreva legendas e escolha a capa. As fotos são reduzidas
  e a **localização (GPS) é removida** automaticamente. O visitante abre a foto ampliada e navega com setas ou deslizando.
- **Quem vê cada álbum**: *rascunho* (só a equipe), *só com login* (famílias e equipe) ou *qualquer pessoa*. Para publicar é
  preciso confirmar a **autorização de uso de imagem** dos responsáveis. Evite nomes completos de crianças nas legendas.
- As fotos dos álbuns ficam na pasta `midia_privada/` (fora de `media/`) e só saem pelo sistema, respeitando a visibilidade:
  **inclua essa pasta no backup e não a exponha no servidor web**. Os banners dos anúncios ficam em `media/anuncios/`.
- Telefone, endereço, frase de destaque, texto de apresentação e Instagram vêm de *Administração → Dados da escola*.

## Busca de aluno por digitação

Ao escolher um aluno (por exemplo em *Nova matrícula*), digite o nome: a lista de sugestões aparece e vai diminuindo
a cada letra, sem diferenciar maiúsculas nem acentos ("jose" acha "José"). Cada sugestão traz nascimento, responsável e
turma, para separar alunos com o mesmo nome. Use ↑ ↓ e Enter, ou clique.

## Administração

Em **Administração** (menu): anos letivos (com cópia das **turmas do ano anterior** ao virar o ano), turmas, categorias
de despesa, feriados do ano e, para administradores, **usuários** (perfil, desativar, redefinir senha) e **dados da escola**.
O painel técnico do Django (`/admin/`) continua existindo só como recurso de manutenção e não é mais necessário no dia a dia.

## Despesas e painel financeiro

**Financeiro** abre o *Painel*: receitas recebidas, despesas, resultado e inadimplência, com gráfico mensal de
receitas × despesas, pizza por categoria e os maiores gastos. Filtre por ano e mês.
- **Lançar despesa**: descrição, data, categoria, valor, fornecedor, forma de pagamento, nº da nota e comprovante
  (PDF ou foto, até 5 MB). *Salvar e lançar outra* agiliza várias compras seguidas.
- **Despesas**: lista com busca e filtros, detalhe de cada gasto, edição, exclusão e **exportação para CSV** (abre no Excel).
- As categorias (material, aluguel, salários…) são editáveis em *Administração → Categorias de despesa*.
- O *Relatório mensal* também mostra as despesas e o resultado do mês.
- Comprovantes ficam em `media/`; em produção sirva essa pasta por um caminho protegido.

## Folha de ponto de professores

*Documentos → Folha de ponto (professores)*: informe o nome (ou vários, um por linha), o mês e o ano. Sai uma página A4 por
professor, com os dias do mês, fins de semana e **feriados/recessos do calendário** já marcados, colunas de entrada, saída,
intervalo, total, assinatura e observações. Imprima ou salve em PDF.

## Dados da escola nas impressões

CNPJ, endereço, cidade (foro), telefone, atos oficiais, direção e os percentuais de multa e juros ficam em
**Administração → Dados da escola** (só administradores). O que ficar em branco usa o valor padrão de `ESCOLA`,
`FINANCEIRO` e `CALENDARIO` em `config/settings.py` (que também podem vir de variáveis de ambiente, como `ESCOLA_CNPJ`).
O texto do contrato é um **modelo**: peça a revisão de um advogado antes de usar.

## Produção

- Defina `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=0` e `DJANGO_ALLOWED_HOSTS`.
- Fotos dos alunos ficam em `media/`. Em desenvolvimento o Django as serve; em produção,
  sirva `media/` por um caminho protegido (os dados são de crianças) e faça backup da pasta e do banco.
- Troque o SQLite por PostgreSQL quando o uso crescer.
