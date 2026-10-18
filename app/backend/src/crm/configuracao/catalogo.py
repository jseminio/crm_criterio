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
        # Receber as mensagens dos leads (fase 0 do SDR de IA, amostra aprovada em 14/10/2026).
        Campo("whatsapp.recebimento", "Recebimento ligado", padrao="false", opcoes=("true", "false"),
              ajuda="Desligado, o CRM recusa o que chegar."),
        Campo("whatsapp.token_verificacao", "Token de verificação", segredo=True,
              ajuda="Gere, cole o mesmo valor na Meta em “Verificar token” e salve aqui."),
        Campo("whatsapp.app_secret", "Chave secreta do aplicativo (App Secret)", segredo=True,
              ajuda="Meta for Developers › seu app › Configurações › Básico. Com ela o CRM confere a assinatura de "
                    "cada entrega e recusa o que não veio da Meta."),
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
    Grupo("meta_ads", "Meta Ads (investimento por campanha)", (
        Campo("meta_ads.ligado", "Leitura ligada", padrao="false", opcoes=("true", "false"),
              ajuda="Ligada, a aba Campanhas lê o gasto de cada campanha do mês no Meta Ads."),
        Campo("meta_ads.token", "Token de acesso", segredo=True,
              ajuda="Usuário do sistema no Business Manager, com a permissão ads_read na conta de anúncios."),
        Campo("meta_ads.conta", "ID da conta de anúncios", exemplo="1708029123631617",
              ajuda="Gerenciador de Anúncios › Configurações da conta. Só os números, sem act_."),
        Campo("meta_ads.versao", "Versão da API da Meta", padrao="v24.0", exemplo="v24.0"),
        Campo("meta_ads.conversoes", "Devolver conversões", padrao="false", opcoes=("true", "false"),
              ajuda="Ligada, o CRM avisa ao Meta lead qualificado, reunião marcada e contrato fechado, a cada 10 minutos. "
                    "E-mail e telefone saem só criptografados (SHA-256)."),
        Campo("meta_ads.conjunto", "ID do conjunto de dados (pixel)", exemplo="123456789012345",
              ajuda="Gerenciador de Eventos › Conjuntos de dados. O token precisa de acesso a ele."),
        Campo("meta_ads.leads", "Trazer leads do formulário", padrao="false", opcoes=("true", "false"),
              ajuda="Ligada, os leads dos formulários de anúncio da página entram sozinhos no CRM, a cada 10 minutos."),
        Campo("meta_ads.pagina", "ID da página do Facebook", exemplo="102938475610293",
              ajuda="Configurações da página › Transparência da página, ou o Business Manager › Páginas."),
        Campo("meta_ads.token_pagina", "Token da página", segredo=True,
              ajuda="Usuário do sistema no Business Manager com a página atribuída e a permissão leads_retrieval."),
    )),
    Grupo("google_ads", "Google Ads (investimento por campanha)", (
        Campo("google_ads.ligado", "Leitura ligada", padrao="false", opcoes=("true", "false"),
              ajuda="Ligada, o botão Atualizar dos anúncios da aba Campanhas lê também o Google Ads."),
        Campo("google_ads.token_dev", "Token de desenvolvedor", segredo=True,
              ajuda="Central de API da conta de administrador do Google Ads, com acesso Básico aprovado."),
        Campo("google_ads.cliente_id", "ID do cliente OAuth", exemplo="1234-abc.apps.googleusercontent.com",
              ajuda="Google Cloud › APIs e serviços › Credenciais, no projeto com a API do Google Ads ativada."),
        Campo("google_ads.cliente_segredo", "Segredo do cliente OAuth", segredo=True),
        Campo("google_ads.refresh_token", "Refresh token", segredo=True,
              ajuda="Gerado uma vez, entrando com a conta Google que acessa o Google Ads (escopo adwords)."),
        Campo("google_ads.conta", "ID da conta (cliente)", exemplo="123-456-7890",
              ajuda="No alto do Google Ads, ao lado do nome da conta."),
        Campo("google_ads.conta_admin", "ID da conta de administrador", exemplo="123-456-7890",
              ajuda="Só se o acesso vem por uma conta de administrador (MCC). Deixe vazio se não houver."),
        Campo("google_ads.versao", "Versão da API do Google Ads", padrao="v25", exemplo="v25",
              ajuda="A v25 é a mais nova em 14/10/2026. O Google aposenta cada versão em cerca de um ano."),
        Campo("google_ads.leads", "Trazer leads do formulário", padrao="false", opcoes=("true", "false"),
              ajuda="Ligada, os leads do formulário de lead do Google Ads entram sozinhos no CRM, a cada 10 minutos, "
                    "com o gclid. Usa as mesmas credenciais da leitura."),
        Campo("google_ads.conversoes", "Devolver conversões", padrao="false", opcoes=("true", "false"),
              ajuda="Ligada, o CRM avisa ao Google, a cada 10 minutos, os eventos dos leads que têm gclid. "
                    "E-mail e telefone saem só criptografados (SHA-256)."),
        Campo("google_ads.acao_qualificado", "Ação de conversão “Lead qualificado”", exemplo="123456789",
              ajuda="Google Ads › Metas › Conversões: ação do tipo importação de cliques. O ID está no endereço da ação."),
        Campo("google_ads.acao_reuniao", "Ação de conversão “Reunião marcada”", exemplo="123456790"),
        Campo("google_ads.acao_contrato", "Ação de conversão “Contrato fechado”", exemplo="123456791",
              ajuda="Recebe o valor do contrato em MRR (parcela × 13 ÷ 12)."),
    )),
    # Assinatura eletrônica do contrato (amostra aprovada por Eduardo em 18/10/2026).
    Grupo("clicksign", "Clicksign (assinatura eletrônica)", (
        Campo("clicksign.ligado", "Assinatura ligada", padrao="false", opcoes=("true", "false"),
              ajuda="Ligada, o contrato ganha o envio para assinatura e o CRM aceita os avisos da Clicksign."),
        Campo("clicksign.ambiente", "Ambiente", padrao="sandbox", opcoes=("sandbox", "producao"),
              ajuda="Sandbox é para teste e não tem validade jurídica. Troque para produção depois do ensaio."),
        Campo("clicksign.token", "Access token", segredo=True,
              ajuda="Clicksign › Configurações › API (o token do sandbox é outro, gerado na conta de sandbox)."),
        Campo("clicksign.segredo_webhook", "Chave do webhook (HMAC SHA256 Secret)", segredo=True,
              ajuda="Gerada ao cadastrar o webhook na Clicksign, com o endereço "
                    "https://crmcs.criterioconsultores.com.br/api/clicksign/webhook. Sem ela o CRM recusa os avisos."),
        Campo("clicksign.autenticacao", "Autenticação do signatário", padrao="email", opcoes=("email", "whatsapp", "sms"),
              ajuda="Como a Clicksign confirma quem assina: token por e-mail, WhatsApp ou SMS (estes dois pedem o celular)."),
        Campo("clicksign.email_criterio", "E-mail de quem assina pela Critério", exemplo="socio@grupocriterio.com.br",
              ajuda="O nome vem de Configurações › Serviços e contratos; o e-mail, daqui."),
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
