import django.db.models.deletion
import pre_matriculas.models
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("alunos", "0002_aluno_naturalidade"),
        ("matriculas", "0003_turma_etapa"),
    ]
    operations = [
        migrations.CreateModel(
            name="LinkPreMatricula",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token", models.CharField(default=pre_matriculas.models.gerar_token, editable=False, max_length=64, unique=True)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("expira_em", models.DateTimeField(default=pre_matriculas.models.expiracao_padrao)),
                ("usado_em", models.DateTimeField(blank=True, null=True)),
                ("ativo", models.BooleanField(default=True)),
                ("observacoes_internas", models.CharField(blank=True, max_length=250)),
                ("ano_letivo", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="links_pre_matricula", to="matriculas.anoletivo")),
                ("criado_por", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="links_pre_matricula_criados", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-criado_em"], "verbose_name": "link de pré-matrícula", "verbose_name_plural": "links de pré-matrícula"},
        ),
        migrations.CreateModel(
            name="SolicitacaoPreMatricula",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("recebida", "Recebida"), ("em_analise", "Em análise"), ("aprovada", "Aprovada"), ("rejeitada", "Rejeitada")], default="recebida", max_length=12)),
                ("enviada_em", models.DateTimeField(auto_now_add=True)),
                ("nome_crianca", models.CharField(max_length=150, verbose_name="Nome completo da criança")),
                ("data_nascimento", models.DateField(verbose_name="Data de nascimento")),
                ("sexo", models.CharField(blank=True, choices=[("F", "Feminino"), ("M", "Masculino")], max_length=1)),
                ("naturalidade", models.CharField(blank=True, max_length=100)),
                ("certidao_nascimento", models.CharField(blank=True, max_length=40)),
                ("endereco", models.CharField(blank=True, max_length=200)),
                ("bairro", models.CharField(blank=True, max_length=80)),
                ("cidade", models.CharField(blank=True, max_length=80)),
                ("alergias", models.TextField(blank=True)),
                ("observacoes_cuidado", models.TextField(blank=True)),
                ("nome_responsavel", models.CharField(max_length=150, verbose_name="Nome completo do responsável")),
                ("parentesco", models.CharField(choices=[("mae", "Mãe"), ("pai", "Pai"), ("avo_f", "Avó"), ("avo_m", "Avô"), ("tio", "Tio(a)"), ("tutor", "Tutor(a) legal"), ("outro", "Outro")], max_length=10)),
                ("cpf_responsavel", models.CharField(blank=True, max_length=14)),
                ("telefone", models.CharField(max_length=20)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("profissao", models.CharField(blank=True, max_length=80)),
                ("endereco_responsavel_diferente", models.BooleanField(default=False)),
                ("responsavel_legal", models.BooleanField(default=True)),
                ("responsavel_financeiro", models.BooleanField(default=True)),
                ("observacoes_familia", models.TextField(blank=True)),
                ("observacoes_secretaria", models.TextField(blank=True)),
                ("aluno_criado", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="solicitacoes_pre_matricula", to="alunos.aluno")),
                ("link", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="solicitacao", to="pre_matriculas.linkprematricula")),
                ("matricula_criada", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="solicitacoes_origem", to="matriculas.matricula")),
                ("turma_desejada", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="solicitacoes_pre_matricula", to="matriculas.turma")),
            ],
            options={"ordering": ["-enviada_em"], "verbose_name": "solicitação de pré-matrícula", "verbose_name_plural": "solicitações de pré-matrícula"},
        ),
    ]
