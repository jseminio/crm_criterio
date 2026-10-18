/** Assinatura eletrônica pela Clicksign — fase 1 (amostra aprovada por Eduardo em 18/10/2026).
 *
 * Sobe o PDF final (o Word gerado, com os anexos ajustados), confere os signatários sugeridos e envia. Daí em diante o
 * CRM acompanha pelos avisos da Clicksign: quando todos assinam, o contrato vira Ativo sozinho, com a data da
 * assinatura. "Conferir na Clicksign" é o caminho de reserva se um aviso não chegar. Estado sempre com palavra. */

import { useEffect, useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { AbaDaAssinatura, EnvioParaAssinatura, SignatarioNovo } from "../api/tipos";
import { usarAcesso } from "../entrada";
import { data, dataHora } from "../formato";
import { CampoDeData } from "./CampoDeData";

const PAPEIS = ["Contratada", "Contratante", "Testemunha"];
const TOM: Record<EnvioParaAssinatura["situacao"], string> = {
  em_assinatura: "espera", assinado: "ganho", recusado: "perda", expirado: "perda", cancelado: "neutra",
};
const AUTENTICACAO: Record<string, string> = { email: "token por e-mail", whatsapp: "token por WhatsApp", sms: "token por SMS" };

function lerComoBase64(arquivo: File): Promise<string> {
  return new Promise((resolver, rejeitar) => {
    const leitor = new FileReader();
    leitor.onload = () => resolver(String(leitor.result));
    leitor.onerror = () => rejeitar(leitor.error);
    leitor.readAsDataURL(arquivo);
  });
}

function Situacao({ envio }: { envio: EnvioParaAssinatura }) {
  const assinaram = envio.signatarios.filter((s) => s.assinou_em).length;
  const texto =
    envio.situacao === "em_assinatura"
      ? `⏳ Em assinatura · ${assinaram} de ${envio.signatarios.length}`
      : envio.situacao === "assinado"
        ? `✓ Assinado por todos em ${data(envio.concluido_em)}`
        : `✗ ${envio.situacao_texto}`;
  return <span className={`etiqueta etiqueta-${TOM[envio.situacao]}`}>{texto}</span>;
}

export function AssinaturaEletronica({ contratoId, aoAssinar }: { contratoId: number; aoAssinar?: () => void }) {
  const { eu, pode } = usarAcesso();
  const podeEnviar = pode("contratos.editar");
  const [aba, definirAba] = useState<AbaDaAssinatura | null>(null);
  const [arquivo, definirArquivo] = useState<File | null>(null);
  const [signatarios, definirSignatarios] = useState<SignatarioNovo[]>([]);
  const [prazo, definirPrazo] = useState("");
  const [ocupado, definirOcupado] = useState(false);
  const [falha, definirFalha] = useState<string | null>(null);
  const [feito, definirFeito] = useState<string | null>(null);

  const aplicar = (nova: AbaDaAssinatura) => {
    const assinouAgora = nova.atual?.situacao === "assinado" && aba?.atual?.situacao !== "assinado";
    definirAba(nova);
    definirSignatarios(nova.sugeridos.map(({ nome, email, telefone, papel }) => ({ nome, email, telefone, papel })));
    definirPrazo(nova.prazo_sugerido);
    if (assinouAgora && aba) aoAssinar?.();
  };

  useEffect(() => {
    api.assinaturaDoContrato(contratoId).then(aplicar)
      .catch((f) => definirFalha(f instanceof ErroDaApi ? f.message : "Falha ao abrir a assinatura eletrônica."));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [contratoId]);

  if (!aba) return falha ? <p className="estado-texto estado-erro" role="alert">✗ {falha}</p> : null;

  const agir = async (acao: () => Promise<AbaDaAssinatura>, sucesso: string, erro: string) => {
    definirOcupado(true);
    definirFalha(null);
    definirFeito(null);
    try {
      aplicar(await acao());
      definirFeito(sucesso);
    } catch (f) {
      definirFalha(f instanceof ErroDaApi ? f.message : erro);
    } finally {
      definirOcupado(false);
    }
  };

  const enviar = async () => {
    if (!arquivo) {
      definirFalha("Escolha o PDF final do contrato.");
      return;
    }
    const conteudo = await lerComoBase64(arquivo);
    await agir(
      () => api.enviarParaAssinatura(contratoId, {
        nome_arquivo: arquivo.name, conteudo_base64: conteudo, prazo, signatarios,
        enviado_por: eu.modo === "local" ? eu.nome ?? "" : undefined,
      }),
      "Enviado. A Clicksign mandou o pedido de assinatura a cada signatário.",
      "Falha ao enviar para assinatura.",
    );
    definirArquivo(null);
  };

  const mudar = (i: number, campo: keyof SignatarioNovo, valor: string) =>
    definirSignatarios((lista) => lista.map((s, j) => (j === i ? { ...s, [campo]: valor } : s)));

  const atual = aba.atual;
  const emAndamento = atual?.situacao === "em_assinatura";
  const mostrarFormulario = podeEnviar && !aba.problema;

  return (
    <section className="gerar-contrato" aria-labelledby="assinatura-titulo">
      <div className="reajuste-cabecalho">
        <div>
          <h3 className="reajuste-titulo" id="assinatura-titulo">Assinatura eletrônica · Clicksign</h3>
          <p className="campo-ajuda" style={{ margin: 0 }}>
            {aba.ambiente === "producao" ? "Produção" : "Sandbox: teste, sem validade jurídica"}
            {aba.ligada && ` · autenticação por ${AUTENTICACAO[aba.autenticacao] ?? aba.autenticacao}`}
          </p>
        </div>
        {atual && podeEnviar && (
          <div className="reajuste-acoes">
            {(emAndamento || (atual.situacao === "assinado" && !atual.tem_pdf)) && aba.ligada && (
              <button type="button" className="botao botao-secundario" disabled={ocupado}
                onClick={() => void agir(() => api.conferirAssinatura(contratoId), "Conferido na Clicksign.",
                  "Falha ao conferir na Clicksign.")}>
                Conferir na Clicksign
              </button>
            )}
            {emAndamento && aba.ligada && (
              <button type="button" className="botao botao-secundario" disabled={ocupado}
                onClick={() => {
                  if (window.confirm("Cancelar o envio? Os signatários não poderão mais assinar este documento."))
                    void agir(() => api.cancelarAssinatura(contratoId), "Envio cancelado.", "Falha ao cancelar.");
                }}>
                Cancelar envio
              </button>
            )}
          </div>
        )}
      </div>

      {aba.problema && !emAndamento && !(atual?.situacao === "assinado") && (
        <p className="recado recado-alcada" role="status">{aba.problema}</p>
      )}
      {feito && <p className="recado" role="status">✓ {feito}</p>}
      {falha && <p className="estado-texto estado-erro" role="alert">✗ {falha}</p>}

      {atual && (
        <div className="assinatura-envio">
          <p style={{ margin: 0 }}>
            <Situacao envio={atual} />{" "}
            <span className="campo-ajuda">
              {atual.nome_arquivo} · enviado por {atual.enviado_por} em {dataHora(atual.enviado_em)}
              {emAndamento && ` · prazo ${data(atual.prazo)}`}
            </span>
          </p>
          {atual.motivo && atual.situacao !== "assinado" && <p className="campo-ajuda">{atual.motivo}</p>}
          <div className="tabela-rolagem">
            <table className="tabela" aria-label="Signatários do envio">
              <thead>
                <tr><th scope="col">Signatário</th><th scope="col">Papel</th><th scope="col">Situação</th>{emAndamento && podeEnviar && <th scope="col"><span className="visualmente-oculto">Ação</span></th>}</tr>
              </thead>
              <tbody>
                {atual.signatarios.map((s) => (
                  <tr key={s.email}>
                    <td>{s.nome}<span className="celula-fonte">{s.email}</span></td>
                    <td>{s.papel}</td>
                    <td>{s.assinou_em ? `✓ Assinou em ${dataHora(s.assinou_em)}` : emAndamento ? "⏳ Pendente" : "— Não assinou"}</td>
                    {emAndamento && podeEnviar && (
                      <td>
                        {!s.assinou_em && aba.ligada && (
                          <button type="button" className="botao botao-secundario" disabled={ocupado}
                            onClick={() => void agir(() => api.lembrarSignatario(contratoId, s.email),
                              `Aviso reenviado para ${s.nome}.`, "Falha ao reenviar o aviso.")}>
                            Reenviar aviso
                          </button>
                        )}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {atual.situacao === "assinado" && (
            atual.tem_pdf ? (
              <button type="button" className="botao botao-secundario" onClick={() => void api.baixarContratoAssinado(atual.id)}>
                Baixar documento assinado
              </button>
            ) : (
              <p className="campo-ajuda">O PDF assinado ainda não foi baixado da Clicksign: use “Conferir na Clicksign”.</p>
            )
          )}
          {atual.situacao === "assinado" && (
            <p className="campo-ajuda">A data da assinatura veio da Clicksign e ativou o contrato: a vigência começa nela.</p>
          )}
        </div>
      )}

      {mostrarFormulario && (
        <div className="formulario assinatura-formulario">
          <div className="campo-bloco">
            <label className="campo-rotulo" htmlFor="assinatura-pdf">Documento final (PDF)</label>
            <input id="assinatura-pdf" type="file" accept="application/pdf,.pdf" disabled={ocupado}
              onChange={(e) => definirArquivo(e.target.files?.[0] ?? null)} />
            <p className="campo-ajuda">O Word gerado acima, com os anexos ajustados, salvo como PDF.</p>
          </div>
          <div className="tabela-rolagem">
            <table className="tabela" aria-label="Signatários">
              <thead>
                <tr>
                  <th scope="col">Nome</th><th scope="col">E-mail</th>
                  {aba.pede_telefone && <th scope="col">Celular</th>}
                  <th scope="col">Papel</th><th scope="col"><span className="visualmente-oculto">Remover</span></th>
                </tr>
              </thead>
              <tbody>
                {signatarios.map((s, i) => (
                  <tr key={i}>
                    <td>
                      <input className="entrada" value={s.nome} aria-label={`Nome do signatário ${i + 1}`} maxLength={200}
                        onChange={(e) => mudar(i, "nome", e.target.value)} />
                      {aba.sugeridos[i] && aba.sugeridos[i].origem !== "digitar" && (
                        <span className="celula-fonte">do {aba.sugeridos[i].origem}</span>
                      )}
                    </td>
                    <td>
                      <input className="entrada" type="email" value={s.email} aria-label={`E-mail do signatário ${i + 1}`}
                        maxLength={200} onChange={(e) => mudar(i, "email", e.target.value)} />
                    </td>
                    {aba.pede_telefone && (
                      <td>
                        <input className="entrada" value={s.telefone ?? ""} aria-label={`Celular do signatário ${i + 1}`}
                          maxLength={30} placeholder="21 99999-9999" onChange={(e) => mudar(i, "telefone", e.target.value)} />
                      </td>
                    )}
                    <td>
                      <select className="selecao" value={s.papel} aria-label={`Papel do signatário ${i + 1}`}
                        onChange={(e) => mudar(i, "papel", e.target.value)}>
                        {PAPEIS.map((p) => <option key={p} value={p}>{p}</option>)}
                      </select>
                    </td>
                    <td>
                      {i >= 2 && (
                        <button type="button" className="botao botao-secundario" aria-label={`Remover o signatário ${i + 1}`}
                          onClick={() => definirSignatarios((lista) => lista.filter((_, j) => j !== i))}>
                          Remover
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div>
            <button type="button" className="botao botao-secundario" disabled={signatarios.length >= 10}
              onClick={() => definirSignatarios((lista) => [...lista, { nome: "", email: "", telefone: null, papel: "Testemunha" }])}>
              + Signatário ou testemunha
            </button>
          </div>
          <div className="campo-bloco">
            <label className="campo-rotulo" htmlFor="assinatura-prazo">Prazo para assinar</label>
            <CampoDeData id="assinatura-prazo" value={prazo} aoMudar={definirPrazo} />
          </div>
          <div className="reajuste-acoes">
            <button type="button" className="botao botao-secundario" disabled={ocupado} onClick={() => void enviar()}>
              {ocupado ? "Enviando…" : "Enviar para assinatura"}
            </button>
          </div>
        </div>
      )}

      {aba.anteriores.length > 0 && (
        <details className="campo-ajuda">
          <summary>Envios anteriores ({aba.anteriores.length})</summary>
          <ul>
            {aba.anteriores.map((a) => (
              <li key={a.id}>{dataHora(a.enviado_em)} · {a.situacao_texto}{a.motivo ? ` · ${a.motivo}` : ""}</li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}
