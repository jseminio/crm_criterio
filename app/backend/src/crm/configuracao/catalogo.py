"""O que se configura pela tela Configurações › Integrações (pedido de Eduardo, 07/10/2026).

Nada de configuração manual no painel do servidor: chave de IA, WhatsApp, e-mail, questionário e
disparo se cadastram, trocam e testam na tela. Cada campo diz de qual variável de ambiente ele herda
o valor antigo: o atualizador copia essa variável para o banco uma vez, e daí em diante **vale a
tela** (a variável fica no painel, sem uso, e ninguém precisa apagá-la).

Só o que a API precisa para subir continua no ambiente: o banco, o segredo das sessões e a conta do
primeiro administrador (`crm.config`).
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["Campo", "Grupo", "GRUPOS", "CAMPOS", "campo", "grupo"]


@dataclass(frozen=True)
class Campo:
    chave: str
    """Nome estável no banco, como `whatsapp.token`. Não é variável de ambiente."""
    rotulo: str
    segredo: bool = False
    """Cifrado no banco e nunca devolvido à tela: ela vê só os 4 últimos caracteres."""
    variavel: str | None = None
    """A variável de ambiente que tinha este valor antes da tela; `None` = só existe na tela."""
    padrao: str = ""
    ajuda: str = ""
    exemplo: str = ""
    opcoes: tuple[str, ...] = ()
    """Valores aceitos, quando a tela mostra uma lista."""
    secao: str = ""
    """Subtítulo que a tela mostra antes deste campo, dentro do cartão."""
    opcional: bool = False
    """Não conta para o cartão aparecer como "Configurado"."""


@dataclass(frozen=True)
class Grupo:
    chave: str
    titulo: str
    campos: tuple[Campo, ...]
    testavel: bool = True


GRUPOS: tuple[Grupo, ...] = (
    Grupo("ia", "Inteligência artificial", (
        Campo("ia.principal", "IA principal", padrao="Anthropic", opcoes=("Anthropic", "OpenAI"),
              ajuda="Quem responde no agente SDR, na ata e na análise da carteira."),
        Campo("ia.reserva", "IA de reserva", padrao="Nenhuma", opcoes=("Nenhuma", "Anthropic", "OpenAI"),
              ajuda="Entra quando a principal falha ou recusa."),
        Campo("anthropic.chave", "Chave da API da Anthropic", segredo=True, variavel="ANTHROPIC_API_KEY",
              ajuda="Console da Anthropic › API keys.", exemplo="sk-ant-…"),
        Campo("anthropic.modelo", "Modelo da Anthropic", variavel="CRM_AGENTE_MODELO", padrao="claude-opus-5",
              exemplo="claude-opus-5"),
        Campo("openai.chave", "Chave da API da OpenAI", segredo=True,
              ajuda="platform.openai.com › API keys. É a API da OpenAI, não a assinatura do ChatGPT.",
              exemplo="sk-…"),
        Campo("openai.modelo", "Modelo da OpenAI", padrao="gpt-6.1-sol", exemplo="gpt-6.1-sol",
              ajuda="gpt-6-astra (o mais capaz), gpt-6.1-sol (quase igual, mais barato), gpt-6-luna (o mais barato)."),
    )),
    Grupo("whatsapp", "WhatsApp (Meta)", (
        Campo("whatsapp.token", "Token permanente", segredo=True, variavel="CRM_WHATSAPP_TOKEN",
              ajuda="Usuário do sistema no Business Manager, com whatsapp_business_messaging."),
        Campo("whatsapp.numero_id", "ID do número de telefone", variavel="CRM_WHATSAPP_NUMERO_ID",
              ajuda="Gerenciador do WhatsApp › Números de telefone.", exemplo="123456789012345"),
        Campo("whatsapp.versao", "Versão da API da Meta", variavel="CRM_WHATSAPP_VERSAO", padrao="v24.0",
              exemplo="v24.0"),
        # Webhook (09/10/2026): receber as respostas do lead. Só existem na tela.
        Campo("whatsapp.verificacao", "Token de verificação", segredo=True, opcional=True,
              secao="Receber respostas (webhook)",
              ajuda="Você inventa (no mínimo 16 caracteres) e cola o mesmo na Meta, junto com o endereço."),
        Campo("whatsapp.chave_do_app", "Chave secreta do app", segredo=True, opcional=True,
              ajuda="Meta for Developers › seu app › Configurações do app › Básico › Chave secreta do app."),
    )),
    Grupo("email", "E-mail (Microsoft 365)", (
        Campo("m365.tenant", "ID do diretório (tenant)", variavel="CRM_M365_TENANT_ID"),
        Campo("m365.cliente", "ID do aplicativo", variavel="CRM_M365_CLIENT_ID"),
        Campo("m365.segredo", "Segredo do aplicativo", segredo=True, variavel="CRM_M365_CLIENT_SECRET"),
        Campo("m365.remetente", "Caixa remetente", variavel="CRM_M365_REMETENTE",
              exemplo="comercial@grupocriterio.com.br"),
    )),
    Grupo("questionario", "Questionário de volumetria", (
        Campo("questionario.link", "Link enviado ao lead", variavel="CRM_LINK_DO_QUESTIONARIO",
              padrao="https://criterio-questionario-proposta.netlify.app/questionario",
              ajuda="Quando o questionário for para o domínio da Critério, troque aqui."),
        Campo("questionario.url", "Endereço da busca no site", variavel="CRM_QUESTIONARIO_URL",
              exemplo="https://<projeto>.supabase.co/functions/v1/questionarios-crm"),
        Campo("questionario.chave", "Chave da busca", segredo=True, variavel="CRM_QUESTIONARIO_CHAVE"),
    )),
    Grupo("disparo", "Disparo do lembrete e do agradecimento", (
        Campo("disparo.ligado", "Disparo ligado", variavel="CRM_DISPARO_DO_QUESTIONARIO", padrao="false",
              opcoes=("true", "false"), ajuda="A cada 10 minutos, de segunda a sexta, das 9h às 18h."),
    ), testavel=False),
)

CAMPOS: dict[str, Campo] = {c.chave: c for g in GRUPOS for c in g.campos}


def campo(chave: str) -> Campo:
    return CAMPOS[chave]


def grupo(chave: str) -> Grupo | None:
    return next((g for g in GRUPOS if g.chave == chave), None)
