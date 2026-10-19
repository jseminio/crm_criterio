/** Registrar indicação (19/10/2026, amostra aprovada por Eduardo): a empresa da base ou uma nova, o serviço de
 * interesse, quem falar no cliente e a autorização do cliente para o contato (LGPD), obrigatória. Cria a oportunidade no
 * Funil comercial já ligada ao parceiro. Os alertas da cláusula 2.2 (já cliente, já em negociação, já de outro parceiro)
 * só avisam: quem decide é a validação. */

import { useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { AlertaDaIndicacao, EmpresaEncontrada, ParceiroDetalhe, ServicoDoCatalogo } from "../api/tipos";
import { BuscaDeEmpresa } from "./BuscaDeEmpresa";
import { CampoDeData } from "./CampoDeData";
import { PainelLateral } from "./PainelLateral";
import { hojeIso } from "../formato";
import { usarDados } from "../usarDados";

export function RegistrarIndicacao({ parceiro, aoFechar, aoRegistrar }: {
  parceiro: ParceiroDetalhe;
  aoFechar: () => void;
  aoRegistrar: (p: ParceiroDetalhe) => void;
}) {
  const servicos = usarDados<ServicoDoCatalogo[]>(() => api.servicos(), []);
  const [empresa, definirEmpresa] = useState<EmpresaEncontrada | null>(null);
  const [nova, definirNova] = useState(false);
  const [nomeNovo, definirNomeNovo] = useState("");
  const [cnpjNovo, definirCnpjNovo] = useState("");
  const [alertas, definirAlertas] = useState<AlertaDaIndicacao[]>([]);
  const [servico, definirServico] = useState("");
  const [recebida, definirRecebida] = useState(hojeIso());
  const [contatoNome, definirContatoNome] = useState("");
  const [contatoMeio, definirContatoMeio] = useState("");
  const [autorizado, definirAutorizado] = useState(false);
  const [salvando, definirSalvando] = useState(false);
  const [falha, definirFalha] = useState<string | null>(null);

  async function escolher(e: EmpresaEncontrada) {
    definirEmpresa(e);
    definirAlertas([]);
    try {
      definirAlertas(await api.alertasDaIndicacao(parceiro.id, e.id));
    } catch {
      /* sem alerta não impede o registro: a validação confere de novo */
    }
  }

  const empresaOk = nova ? nomeNovo.trim().length >= 2 : empresa !== null;
  const pronto = empresaOk && servico !== "" && autorizado;

  async function registrar() {
    if (!autorizado) {
      definirFalha("Sem a autorização do cliente para o contato (LGPD), a indicação não entra.");
      return;
    }
    definirSalvando(true);
    definirFalha(null);
    try {
      const p = await api.registrarIndicacao(parceiro.id, {
        empresa_id: nova ? null : empresa?.id,
        empresa_nova: nova ? { nome: nomeNovo.trim(), cnpj: cnpjNovo.trim() || null } : null,
        servico, recebida_em: recebida || null,
        contato_nome: contatoNome.trim() || null, contato_meio: contatoMeio.trim() || null,
        autorizado_pelo_cliente: autorizado,
      });
      aoRegistrar(p);
    } catch (e) {
      definirFalha(e instanceof ErroDaApi ? e.message : "Não consegui registrar.");
    } finally {
      definirSalvando(false);
    }
  }

  return (
    <PainelLateral titulo="Registrar indicação" subtitulo={`${parceiro.nome} · ${parceiro.nivel}`} aoFechar={aoFechar}
      rodape={
        <>
          <button type="button" className="botao botao-secundario" onClick={aoFechar}>Cancelar</button>
          <button type="button" className="botao botao-primario" onClick={registrar} disabled={salvando || !pronto}>
            {salvando ? "Registrando…" : "Registrar indicação"}
          </button>
        </>
      }>
      {falha && <div className="estado estado-erro" role="alert"><p className="estado-texto">{falha}</p></div>}
      <div className="formulario">
        {!nova ? (
          <BuscaDeEmpresa id="ri-empresa" rotulo="Empresa indicada" escolhida={empresa} aoEscolher={escolher}
            ajuda="Busca na base de empresas pelo nome ou CNPJ." />
        ) : (
          <div className="formulario-duplo">
            <div className="campo-bloco">
              <label className="campo-rotulo" htmlFor="ri-nome">Empresa nova</label>
              <input id="ri-nome" className="entrada" value={nomeNovo} placeholder="Comércio Delta Ltda"
                onChange={(e) => definirNomeNovo(e.target.value)} />
            </div>
            <div className="campo-bloco">
              <label className="campo-rotulo" htmlFor="ri-cnpj">CNPJ</label>
              <input id="ri-cnpj" className="entrada" value={cnpjNovo} placeholder="00.000.000/0001-00"
                onChange={(e) => definirCnpjNovo(e.target.value)} />
            </div>
          </div>
        )}
        <button type="button" className="botao botao-secundario" onClick={() => {
          definirNova(!nova);
          definirEmpresa(null);
          definirAlertas([]);
        }}>
          {nova ? "Escolher da base de empresas" : "Não achou? Cadastrar empresa nova"}
        </button>

        {alertas.length > 0 && (
          <div className="aviso-de-alerta" role="status">
            <strong>Atenção (cláusula 2.2)</strong>
            <ul>{alertas.map((a) => <li key={a.texto}>{a.texto} Pode ser recusada como "{a.motivo_sugerido}".</li>)}</ul>
            <span>Você decide na validação.</span>
          </div>
        )}

        <div className="campo-bloco">
          <label className="campo-rotulo" htmlFor="ri-servico">Serviço de interesse</label>
          <select id="ri-servico" className="selecao" value={servico} onChange={(e) => definirServico(e.target.value)}>
            <option value="">Escolha o serviço</option>
            {(servicos.dados ?? []).map((s) => <option key={s.nome} value={s.nome}>{s.nome}</option>)}
          </select>
        </div>
        <div className="campo-bloco">
          <label className="campo-rotulo" htmlFor="ri-recebida">Indicada em</label>
          <CampoDeData id="ri-recebida" value={recebida} aoMudar={definirRecebida} />
        </div>
        <div className="formulario-duplo">
          <div className="campo-bloco">
            <label className="campo-rotulo" htmlFor="ri-contato">Contato no cliente</label>
            <input id="ri-contato" className="entrada" value={contatoNome} onChange={(e) => definirContatoNome(e.target.value)} />
          </div>
          <div className="campo-bloco">
            <label className="campo-rotulo" htmlFor="ri-meio">E-mail ou telefone</label>
            <input id="ri-meio" className="entrada" value={contatoMeio} onChange={(e) => definirContatoMeio(e.target.value)} />
          </div>
        </div>
        <label className="campo-marcar">
          <input type="checkbox" checked={autorizado} onChange={(e) => definirAutorizado(e.target.checked)} />
          {" "}O cliente autorizou o contato da Critério (LGPD)
        </label>
      </div>
      <div className="recado">
        Cria a oportunidade no Funil comercial em <strong>Enviar proposta</strong>, com Tipo de canal Parceiros, o parceiro
        ligado e a data da indicação. A validação fica para o sócio, em até 5 dias úteis.
      </div>
    </PainelLateral>
  );
}
