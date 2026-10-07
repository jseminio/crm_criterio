/** Configurações › Integrações (amostra aprovada por Eduardo em 07/10/2026): chave de IA, WhatsApp,
 * e-mail, questionário e disparo se cadastram, trocam e testam aqui, sem nada no painel do servidor.
 * Vale o que está na tela; sem valor na tela, o que veio do servidor; depois o padrão. Segredo nunca
 * volta do servidor: aparecem só os 4 últimos caracteres. A IA pode ser Anthropic ou OpenAI, com a
 * outra de reserva (07/10/2026). */

import { useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { CampoDeIntegracao, GrupoDeIntegracao, Integracoes, ResultadoDoTeste } from "../api/tipos";
import { dataHora } from "../formato";
import { usarDados } from "../usarDados";
import { Etiqueta } from "./Etiqueta";
import { Carregando, Erro } from "./estados";

const DE_ONDE: Record<string, string> = {
  tela: "salvo nesta tela",
  servidor: "vem do servidor; salve aqui para a tela valer",
  "padrão": "padrão do sistema",
  vazio: "não configurado",
};

export function IntegracoesDoSistema() {
  const { dados, carregando, erro, recarregar } = usarDados<Integracoes>(() => api.integracoes(), []);
  if (carregando && !dados) return <Carregando rotulo="Abrindo as integrações" />;
  if (erro) return <Erro mensagem={erro} aoTentarDeNovo={recarregar} />;
  if (!dados) return null;
  return (
    <div style={{ display: "grid", gap: "var(--e4)" }}>
      <p className="campo-ajuda" style={{ margin: 0 }}>
        As chaves ficam cifradas no banco e nunca voltam para a tela: aparecem só os 4 últimos caracteres. O que
        está salvo aqui vale mais que o painel do servidor.
      </p>
      {dados.grupos.map((g) => (
        <CartaoDeIntegracao key={g.chave} grupo={g} aoSalvar={recarregar} />
      ))}
    </div>
  );
}

function CartaoDeIntegracao({ grupo, aoSalvar }: { grupo: GrupoDeIntegracao; aoSalvar: () => void }) {
  const [rascunho, definirRascunho] = useState<Record<string, string>>({});
  const [apagar, definirApagar] = useState<string[]>([]);
  const [salvando, definirSalvando] = useState(false);
  const [falha, definirFalha] = useState<string | null>(null);
  const [feito, definirFeito] = useState<string | null>(null);
  const [teste, definirTeste] = useState<ResultadoDoTeste | null>(null);
  const [testando, definirTestando] = useState(false);
  const [para, definirPara] = useState("");

  const valorDe = (c: CampoDeIntegracao) => rascunho[c.chave] ?? (c.segredo ? "" : (c.valor ?? ""));
  const mudar = (chave: string, valor: string) => {
    definirFeito(null);
    definirRascunho({ ...rascunho, [chave]: valor });
  };
  const mudados = grupo.campos.filter((c) =>
    c.chave in rascunho && (c.segredo ? rascunho[c.chave].trim() !== "" : rascunho[c.chave] !== (c.valor ?? "")),
  );
  const mudou = mudados.length > 0 || apagar.length > 0;

  const salvar = async () => {
    definirSalvando(true);
    definirFalha(null);
    try {
      await api.salvarIntegracao(grupo.chave, {
        valores: Object.fromEntries(mudados.map((c) => [c.chave, rascunho[c.chave]])),
        apagar,
      });
      definirRascunho({});
      definirApagar([]);
      definirFeito("Salvo. Já vale para o CRM, sem reiniciar.");
      aoSalvar();
    } catch (f) {
      definirFalha(f instanceof ErroDaApi ? f.message : "Falha ao salvar.");
    } finally {
      definirSalvando(false);
    }
  };

  const rodar = async (acao: () => Promise<ResultadoDoTeste>) => {
    definirTestando(true);
    definirTeste(null);
    try {
      definirTeste(await acao());
    } catch (f) {
      definirTeste({ ok: false, mensagem: f instanceof ErroDaApi ? f.message : "Falha no teste.", segundos: 0, em: "" });
    } finally {
      definirTestando(false);
    }
  };

  const titulo = `integracao-${grupo.chave}`;
  return (
    <section className="numero" aria-labelledby={titulo}>
      <div style={{ display: "flex", alignItems: "center", gap: "var(--e2)", flexWrap: "wrap" }}>
        <h3 className="numero-rotulo" id={titulo} style={{ margin: 0, flex: 1 }}>{grupo.titulo}</h3>
        <Etiqueta texto={grupo.configurado ? "Configurado" : "Falta configurar"} />
      </div>
      <div style={{ display: "grid", gap: "var(--e3)", marginTop: "var(--e3)" }}>
        {grupo.campos.map((c) => (
          <Campo key={c.chave} campo={c} valor={valorDe(c)} aoMudar={(v) => mudar(c.chave, v)}
            vaiApagar={apagar.includes(c.chave)}
            aoApagar={() => { definirFeito(null); definirApagar([...apagar, c.chave]); }} />
        ))}
      </div>
      <div className="perfis-acoes">
        <button type="button" className="botao botao-primario" disabled={!mudou || salvando} onClick={() => void salvar()}>
          {salvando ? "Salvando…" : "Salvar"}
        </button>
        {grupo.testavel && (
          <button type="button" className="botao" disabled={testando || mudou}
            title={mudou ? "Salve antes de testar" : undefined}
            onClick={() => void rodar(() => api.testarIntegracao(grupo.chave))}>
            {testando ? "Testando…" : "Testar conexão"}
          </button>
        )}
        {mudou && <span className="campo-ajuda">· alterações ainda não salvas</span>}
        {grupo.alterado_em && (
          <span className="campo-ajuda">Última mudança: {grupo.alterado_por ? `${grupo.alterado_por}, ` : ""}{dataHora(grupo.alterado_em)}</span>
        )}
      </div>
      {grupo.envia_teste && (
        <div className="perfis-acoes">
          <input className="entrada" style={{ maxWidth: "18rem" }} value={para}
            aria-label={`${grupo.titulo}: enviar teste para`}
            placeholder={grupo.chave === "email" ? "seu@email.com.br" : "21 99999-9999"}
            onChange={(e) => definirPara(e.target.value)} />
          <button type="button" className="botao" disabled={testando || mudou || !para.trim()}
            onClick={() => void rodar(() => api.enviarTesteDeIntegracao(grupo.chave, para))}>
            {grupo.chave === "email" ? "Enviar e-mail de teste" : "Enviar modelo de teste"}
          </button>
          <span className="campo-ajuda">Manda uma mensagem de verdade, só para este destino.</span>
        </div>
      )}
      {teste && (
        <p className={teste.ok ? "recado" : "estado estado-erro estado-texto"} role={teste.ok ? "status" : "alert"}>
          {teste.ok ? "✓" : "✗"} {teste.mensagem}{teste.segundos ? ` (${String(teste.segundos).replace(".", ",")} s)` : ""}
        </p>
      )}
      {falha && <p className="estado estado-erro estado-texto" role="alert">✗ {falha}</p>}
      {feito && <p className="recado" role="status">✓ {feito}</p>}
    </section>
  );
}

function Campo({ campo, valor, aoMudar, vaiApagar, aoApagar }: {
  campo: CampoDeIntegracao; valor: string; aoMudar: (v: string) => void; vaiApagar: boolean; aoApagar: () => void;
}) {
  const id = `campo-${campo.chave}`;
  const ajuda = [DE_ONDE[campo.origem], campo.ajuda].filter(Boolean).join(" · ");
  if (campo.opcoes.length === 2 && campo.opcoes.includes("true")) {
    return (
      <label style={{ display: "flex", gap: "var(--e2)", alignItems: "center" }}>
        <input type="checkbox" checked={valor === "true"} onChange={(e) => aoMudar(e.target.checked ? "true" : "false")} />
        <span>{campo.rotulo}</span>
        <span className="campo-ajuda">{ajuda}</span>
      </label>
    );
  }
  if (campo.opcoes.length > 0) {
    return (
      <div style={{ display: "grid", gap: "var(--e1)" }}>
        <label htmlFor={id}>{campo.rotulo}</label>
        <select id={id} className="selecao" style={{ maxWidth: "18rem" }} value={valor} onChange={(e) => aoMudar(e.target.value)}>
          {campo.opcoes.map((o) => <option key={o} value={o}>{o}</option>)}
        </select>
        <span className="campo-ajuda">{ajuda}</span>
      </div>
    );
  }
  return (
    <div style={{ display: "grid", gap: "var(--e1)" }}>
      <label htmlFor={id}>{campo.rotulo}</label>
      {campo.segredo && campo.final && !vaiApagar && (
        <span className="campo-ajuda">
          Salva, termina em <strong>{campo.final}</strong> · {DE_ONDE[campo.origem]}
          {campo.origem === "tela" && (
            <> · <button type="button" className="botao botao-texto-perigo" onClick={aoApagar}>Tirar da tela</button></>
          )}
        </span>
      )}
      {campo.ilegivel && (
        <span className="estado estado-erro estado-texto">A chave salva não pode mais ser lida (o segredo do servidor mudou). Cadastre de novo.</span>
      )}
      {vaiApagar && <span className="campo-ajuda">Sai da tela ao salvar; volta a valer o servidor, se houver.</span>}
      <input id={id} className="entrada" type={campo.segredo ? "password" : "text"} autoComplete="off" value={valor}
        placeholder={campo.segredo ? (campo.final ? "Cole a nova para trocar" : "Cole aqui") : (campo.exemplo || campo.padrao)}
        onChange={(e) => aoMudar(e.target.value)} />
      {!campo.segredo && <span className="campo-ajuda">{ajuda}</span>}
      {campo.segredo && !campo.final && campo.ajuda && <span className="campo-ajuda">{campo.ajuda}</span>}
    </div>
  );
}
