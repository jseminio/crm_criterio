/** Configurações › Propostas (01/10/2026): as duas matrizes em PowerPoint, a troca de matriz, o
 * próximo número da sequência PROP CCE RJ, quem revisa e envia e o preço de tabela dos planos
 * financeiros. Trocar a matriz é subir o .pptx novo: o CRM confere os marcadores antes de usar. */

import { useEffect, useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { ConfiguracaoDeProposta, MatrizesDeProposta as Matrizes, TipoDeMatriz } from "../api/tipos";
import { data, fracaoEmPercentual } from "../formato";
import { Recolhivel } from "./Recolhivel";
import { Carregando, Erro } from "./estados";
import { LinkDeArquivo } from "./LinkDeArquivo";
import { usarAcesso } from "../entrada";

const TIPOS: TipoDeMatriz[] = ["Contábil", "Financeiro"];
const chave = (n: string) => `{{${n}}}`;

type Rascunho = { proximo_numero: string; revisores: string; plano_bpo: string; plano_plus: string; plano_cfo: string };

function rascunhoDe(c: ConfiguracaoDeProposta): Rascunho {
  return {
    proximo_numero: String(c.proximo_numero), revisores: c.revisores.join(", "),
    plano_bpo: c.plano_bpo, plano_plus: c.plano_plus, plano_cfo: c.plano_cfo,
  };
}

export function MatrizesDeProposta() {
  const [matrizes, definirMatrizes] = useState<Matrizes | null>(null);
  const [config, definirConfig] = useState<ConfiguracaoDeProposta | null>(null);
  const [rascunho, definirRascunho] = useState<Rascunho | null>(null);
  const [quem, definirQuem] = useState("");
  const comLogin = usarAcesso().eu.modo === "microsoft";
  const [erroAoAbrir, definirErroAoAbrir] = useState<string | null>(null);
  const [erro, definirErro] = useState<string | null>(null);
  const [feito, definirFeito] = useState<string | null>(null);
  const [ocupado, definirOcupado] = useState(false);

  const carregar = () => {
    definirErroAoAbrir(null);
    Promise.all([api.matrizesDeProposta(), api.configuracaoDeProposta()])
      .then(([m, c]) => {
        definirMatrizes(m);
        definirConfig(c);
        definirRascunho(rascunhoDe(c));
        definirQuem((atual) => (c.revisores.includes(atual) ? atual : (c.revisores[0] ?? "")));
      })
      .catch((f) => definirErroAoAbrir(f instanceof ErroDaApi ? f.message : "Falha ao abrir as matrizes."));
  };
  useEffect(carregar, []);

  if (erroAoAbrir) return <Erro mensagem={erroAoAbrir} aoTentarDeNovo={carregar} />;
  if (!matrizes || !config || !rascunho) return <Carregando rotulo="Abrindo as matrizes de proposta" />;

  const subir = async (tipo: TipoDeMatriz, arquivo: File | null) => {
    if (!arquivo) return;
    definirOcupado(true);
    definirErro(null);
    definirFeito(null);
    try {
      const m = await api.subirMatriz(tipo, arquivo, quem);
      definirFeito(
        m.utilizavel
          ? `Matriz ${tipo} trocada: ${m.nome_arquivo}, com os ${m.obrigatorios} marcadores obrigatórios.`
          : `Matriz ${tipo} gravada, mas não será usada até corrigir os marcadores abaixo.`,
      );
      carregar();
    } catch (falha) {
      definirErro(falha instanceof ErroDaApi ? falha.message : "Falha ao subir a matriz.");
    } finally {
      definirOcupado(false);
    }
  };

  const salvar = async () => {
    definirOcupado(true);
    definirErro(null);
    definirFeito(null);
    try {
      const c = await api.editarConfiguracaoDeProposta({
        proximo_numero: Number(rascunho.proximo_numero),
        revisores: rascunho.revisores.split(",").map((n) => n.trim()).filter(Boolean),
        plano_bpo: rascunho.plano_bpo, plano_plus: rascunho.plano_plus, plano_cfo: rascunho.plano_cfo,
      });
      definirConfig(c);
      definirRascunho(rascunhoDe(c));
      definirFeito("Configuração das propostas salva.");
    } catch (falha) {
      definirErro(falha instanceof ErroDaApi ? falha.message : "Falha ao salvar.");
    } finally {
      definirOcupado(false);
    }
  };

  const mudar = (campo: keyof Rascunho) => (e: { target: { value: string } }) =>
    definirRascunho({ ...rascunho, [campo]: e.target.value });

  return (
    <section className="numero matrizes-de-proposta" aria-label="Propostas">
      <h3 className="numero-rotulo">Propostas: matrizes e numeração</h3>
      <p>
        Cada proposta sai de uma matriz em PowerPoint com marcadores como {chave("cliente")}. Trocar a matriz é subir o .pptx
        novo: o CRM confere os marcadores, e matriz com marcador faltando não é usada.
      </p>
      {erro && <p role="alert" className="estado-texto">{erro}</p>}
      {feito && <p role="status">{feito}</p>}

      {!comLogin && (
        <label className="campo" style={{ maxWidth: 240 }}>
          <span className="campo-rotulo">Quem está subindo a matriz</span>
          <select className="entrada" value={quem} onChange={(e) => definirQuem(e.target.value)}>
            {config.revisores.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
        </label>
      )}

      <table className="tabela" aria-label="Matrizes de proposta">
        <thead>
          <tr>
            <th scope="col">Matriz</th>
            <th scope="col">Arquivo em uso</th>
            <th scope="col">Marcadores</th>
            <th scope="col" aria-label="Ações" />
          </tr>
        </thead>
        <tbody>
          {TIPOS.map((tipo) => {
            const m = matrizes.em_uso[tipo];
            return (
              <tr key={tipo}>
                <td>{tipo}</td>
                <td>
                  {m ? (
                    <>
                      {m.nome_arquivo}
                      <span className="celula-fonte">enviada por {m.enviada_por} em {data(m.enviada_em)}</span>
                    </>
                  ) : (
                    <span className="campo-ajuda">nenhuma ainda: a proposta {tipo} não sai até subir uma</span>
                  )}
                </td>
                <td>
                  {m && m.utilizavel && <span className="marcador-ok">✓ {m.encontrados} de {m.obrigatorios} obrigatórios</span>}
                  {m && !m.utilizavel && (
                    <>
                      {m.faltando.length > 0 && <span className="marcador-falta">✗ falta {m.faltando.map(chave).join(", ")}</span>}
                      {m.desconhecidos.length > 0 && (
                        <span className="marcador-falta celula-fonte">✗ desconhecido {m.desconhecidos.map(chave).join(", ")}</span>
                      )}
                      <span className="celula-fonte">não será usada até corrigir</span>
                    </>
                  )}
                </td>
                <td>
                  <label className="link-de-tabela">
                    {m ? "Trocar matriz" : "Subir matriz"}
                    <input
                      type="file" accept=".pptx" hidden disabled={ocupado || (!quem && !comLogin)}
                      aria-label={`${m ? "Trocar" : "Subir"} a matriz ${tipo}`}
                      onChange={(e) => { void subir(tipo, e.target.files?.[0] ?? null); e.target.value = ""; }}
                    />
                  </label>
                  {m && (
                    <>
                      {" · "}
                      <LinkDeArquivo className="link-de-tabela" href={`/api/propostas/matrizes/${m.id}/pptx`} nome={m.nome_arquivo}>Baixar</LinkDeArquivo>
                    </>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      <div className="proposta-grade">
        <label className="campo">
          <span className="campo-rotulo">Próximo número de proposta</span>
          <input className="entrada" type="number" min="1" value={rascunho.proximo_numero} onChange={mudar("proximo_numero")} />
          <span className="campo-ajuda">
            Sequência única para Contábil e Financeiro; o ano vem da data da proposta.
            {config.ultimo_usado ? ` Último usado: ${config.ultimo_usado}.` : ""}
          </span>
        </label>
        <label className="campo">
          <span className="campo-rotulo">Quem revisa e envia</span>
          <input className="entrada" value={rascunho.revisores} onChange={mudar("revisores")} />
          <span className="campo-ajuda">nomes separados por vírgula</span>
        </label>
        <div className="campo">
          <span className="campo-rotulo">Alíquota estimada</span>
          <strong>{fracaoEmPercentual(config.imposto, 0)}</strong>
          <span className="campo-ajuda">é o imposto de Carteira › Parâmetros de cálculo</span>
        </div>
        <label className="campo">
          <span className="campo-rotulo">BPO Financeiro (R$/mês)</span>
          <input className="entrada" type="number" min="0" step="0.01" value={rascunho.plano_bpo} onChange={mudar("plano_bpo")} />
        </label>
        <label className="campo">
          <span className="campo-rotulo">BPO Financeiro PLUS (R$/mês)</span>
          <input className="entrada" type="number" min="0" step="0.01" value={rascunho.plano_plus} onChange={mudar("plano_plus")} />
        </label>
        <label className="campo">
          <span className="campo-rotulo">CFO as a Service (R$/mês)</span>
          <input className="entrada" type="number" min="0" step="0.01" value={rascunho.plano_cfo} onChange={mudar("plano_cfo")} />
        </label>
      </div>
      <div>
        <button type="button" className="botao botao-secundario" onClick={() => void salvar()} disabled={ocupado}>
          Salvar configuração das propostas
        </button>
      </div>

      <Recolhivel titulo="Lista de marcadores" resumo="o que cada {{marcador}} da matriz recebe">
        <table className="tabela" aria-label="Marcadores das matrizes">
          <thead>
            <tr>
              <th scope="col">Marcador</th>
              <th scope="col">O que entra no lugar</th>
              <th scope="col">Obrigatório em</th>
            </tr>
          </thead>
          <tbody>
            {matrizes.marcadores.map((m) => (
              <tr key={m.nome}>
                <td><code>{chave(m.nome)}</code></td>
                <td>{m.descricao}</td>
                <td>{m.obrigatorio_em.length ? m.obrigatorio_em.join(" e ") : "opcional"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Recolhivel>
    </section>
  );
}
