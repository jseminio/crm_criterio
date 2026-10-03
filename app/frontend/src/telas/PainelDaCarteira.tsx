/** A bimestral interna da carteira (Eduardo, 03/10/2026): Head do BPO e CEO da Critério, para um
 * overview da carteira e correção de rotas de análise. Não é de um cliente; vence a cada 2 meses. */

import { useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { CarteiraComReunioes } from "../api/tipos";
import { CampoDeData } from "../componentes/CampoDeData";
import { Carregando, Erro } from "../componentes/estados";
import { PainelLateral } from "../componentes/PainelLateral";
import { usarAcesso } from "../entrada";
import { data } from "../formato";
import { usarDados } from "../usarDados";

export function PainelDaCarteira({ aoFechar, aoMudar }: { aoFechar: () => void; aoMudar: () => void }) {
  const { pode } = usarAcesso();
  const edita = pode("sucesso.editar");
  const carteira = usarDados<CarteiraComReunioes>(() => api.reunioesDaCarteira(), []);
  const hoje = new Date().toLocaleDateString("sv");
  const [campos, definirCampos] = useState({ data: hoje, participantes: "", resumo: "", correcoes_de_rota: "" });
  const [ocupado, definirOcupado] = useState(false);
  const [falha, definirFalha] = useState<string | null>(null);
  const [feito, definirFeito] = useState<string | null>(null);
  const mudar = (campo: keyof typeof campos, valor: string) => {
    definirFeito(null);
    definirCampos((c) => ({ ...c, [campo]: valor }));
  };

  const registrar = async () => {
    definirOcupado(true);
    definirFalha(null);
    try {
      await api.registrarReuniaoDaCarteira(campos);
      definirFeito(`Bimestral da carteira de ${data(campos.data)} registrada.`);
      definirCampos({ data: hoje, participantes: "", resumo: "", correcoes_de_rota: "" });
      carteira.recarregar();
      aoMudar();
    } catch (e) {
      definirFalha(e instanceof ErroDaApi ? e.message : "Não consegui registrar. Tente de novo.");
    } finally {
      definirOcupado(false);
    }
  };

  const d = carteira.dados?.devida;
  return (
    <PainelLateral
      titulo="Reunião bimestral da carteira" subtitulo="Interna · Head do BPO e CEO da Critério" aoFechar={aoFechar}
      rodape={edita ? (
        <button type="button" className="botao botao-primario" disabled={ocupado || !campos.data} onClick={() => void registrar()}>
          {ocupado ? "Registrando…" : "Registrar a bimestral"}
        </button>
      ) : undefined}
    >
      {carteira.carregando && !carteira.dados ? (
        <Carregando rotulo="Abrindo a bimestral da carteira" />
      ) : carteira.erro ? (
        <Erro mensagem={carteira.erro} aoTentarDeNovo={carteira.recarregar} />
      ) : d && (
        <>
          <p style={{ margin: 0 }}>
            {d.ultima ? `Última ${data(d.ultima)}` : "Nenhuma registrada"} ·{" "}
            {d.atrasada
              ? <strong className="cartao-prazo-atrasado">⚠ venceu em {data(d.proxima)} ({d.dias_de_atraso} d)</strong>
              : <strong>próxima até {data(d.proxima)}</strong>}
          </p>
          <div>
            <span className="campo-rotulo">Pauta</span>
            <ul className="sucesso-ajustes">{d.pauta.map((p) => <li key={p}>{p}</li>)}</ul>
          </div>
          {edita && (
            <fieldset className="formulario" disabled={ocupado}>
              <legend className="campo-rotulo">Registrar a bimestral feita</legend>
              <div className="campo-bloco">
                <label className="campo-rotulo" htmlFor="ca-data">Data</label>
                <CampoDeData id="ca-data" value={campos.data} aoMudar={(v) => mudar("data", v)} />
              </div>
              <div className="campo-bloco">
                <label className="campo-rotulo" htmlFor="ca-participantes">Participantes</label>
                <input id="ca-participantes" className="entrada" maxLength={300} placeholder={d.participantes}
                  value={campos.participantes} onChange={(e) => mudar("participantes", e.target.value)} />
              </div>
              <div className="campo-bloco">
                <label className="campo-rotulo" htmlFor="ca-resumo">Overview da carteira</label>
                <textarea id="ca-resumo" className="entrada" rows={3} value={campos.resumo} onChange={(e) => mudar("resumo", e.target.value)} />
              </div>
              <div className="campo-bloco">
                <label className="campo-rotulo" htmlFor="ca-rotas">Correções de rota</label>
                <textarea id="ca-rotas" className="entrada" rows={3} placeholder="O que muda na análise dos clientes, e de quem"
                  value={campos.correcoes_de_rota} onChange={(e) => mudar("correcoes_de_rota", e.target.value)} />
              </div>
              {falha && <p className="estado estado-erro estado-texto" role="alert">✗ {falha}</p>}
              {feito && <p className="recado" role="status">✓ {feito}</p>}
            </fieldset>
          )}
          <section aria-labelledby="ca-historico">
            <h3 className="campo-rotulo" id="ca-historico">Bimestrais registradas</h3>
            {!carteira.dados?.reunioes.length ? (
              <p className="campo-ajuda">Nenhuma registrada ainda.</p>
            ) : (
              <ol className="sucesso-historico">
                {carteira.dados.reunioes.map((r) => (
                  <li key={r.id}>
                    <strong>{data(r.data)}</strong>
                    {r.participantes && <span className="campo-ajuda">{r.participantes}</span>}
                    {r.resumo && <p>{r.resumo}</p>}
                    {r.correcoes_de_rota && <p><b>Correções de rota:</b>{"\n"}{r.correcoes_de_rota}</p>}
                    {r.registrada_por && <span className="campo-ajuda">Registrada por {r.registrada_por}</span>}
                  </li>
                ))}
              </ol>
            )}
          </section>
        </>
      )}
    </PainelLateral>
  );
}
