/** Painel "Parâmetros de cálculo" da tela Carteira — pesos do Score, cortes, réguas de
 * rentabilidade e a matriz de horas/mix de equipe por Porte, editáveis e gravadas no banco
 * (decisão de Eduardo, 28/09/2026: "existe a possibilidade deles variarem").
 *
 * Vale para **toda a carteira**, não para um grupo — por isso vive uma vez só na tela Carteira
 * (ao lado de "Exportar para conferência"), não dentro do painel "Avaliar" de cada grupo (de onde
 * saiu em 28/09/2026, mesma decisão: "isso afeta todo o índice", não é avaliação individual).
 * Salvar aqui grava uma **versão nova** (nunca sobrescreve a anterior, mesmo princípio das notas),
 * com autor e motivo obrigatórios — é o log de quem mudou o quê, sempre visível em "Vigente
 * desde/por" abaixo. Os valores iniciais vêm de `Classificacao_Grupo_COMPLETO.xlsx` (aba
 * Parâmetros) e `Rentabilidade_Grupo_COMPLETO.xlsx` (abas "2. Matriz Horas", "3. Fator de Atrito" e
 * "6. Régua Rentab."), conferidos célula a célula.
 */

import { useEffect, useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { EdicaoDeParametros, Parametros } from "../api/tipos";

const CARGOS = [
  "Sócio Sênior", "Sócio Júnior/Gerente", "Supervisor/Especialista",
  "Analista Sênior", "Analista Pleno", "Analista Júnior",
] as const;

const PORTES = ["Micro", "Pequeno", "Médio", "Grande", "Extra Grande"] as const;

const TAXA_POR_CARGO = {
  "Sócio Sênior": "taxa_socio_senior", "Sócio Júnior/Gerente": "taxa_socio_junior",
  "Supervisor/Especialista": "taxa_supervisor", "Analista Sênior": "taxa_analista_senior",
  "Analista Pleno": "taxa_analista_pleno", "Analista Júnior": "taxa_analista_junior",
} as const;

const HORAS_POR_PORTE = {
  Micro: "horas_micro", Pequeno: "horas_pequeno", Médio: "horas_medio",
  Grande: "horas_grande", "Extra Grande": "horas_extra_grande",
} as const;

type Campos = Omit<EdicaoDeParametros, "autor" | "motivo" | "mix">;

function paraCampos(p: Parametros): Campos {
  const { id: _id, criado_em: _c, mix: _m, custo_hora: _ch, autor: _a, motivo: _mo, ...resto } = p;
  const numerico: Record<string, number> = {};
  for (const [k, v] of Object.entries(resto)) numerico[k] = typeof v === "string" ? Number(v) : (v as number);
  return numerico as unknown as Campos;
}

function formatoPercentual(v: number): string {
  return (v * 100).toLocaleString("pt-BR", { minimumFractionDigits: 0, maximumFractionDigits: 2 }) + "%";
}

function CampoPercentual({ rotulo, valor, aoMudar }: { rotulo: string; valor: number; aoMudar: (v: number) => void }) {
  return (
    <label className="campo-bloco">
      <span className="campo-rotulo">{rotulo}</span>
      <input
        className="entrada" type="number" step="0.01" min={0} max={100}
        value={Number.isFinite(valor) ? Math.round(valor * 10000) / 100 : ""}
        onChange={(e) => aoMudar(e.target.value === "" ? 0 : Number(e.target.value) / 100)}
      />
    </label>
  );
}

const GRUPOS = [
  { chave: "pesos", rotulo: "Pesos do Score" },
  { chave: "cortes", rotulo: "Cortes e travas" },
  { chave: "rentabilidade", rotulo: "Rentabilidade" },
  { chave: "matriz", rotulo: "Matriz por Porte" },
] as const;
type Grupo = (typeof GRUPOS)[number]["chave"];

export function AbaDeParametros() {
  const [grupo, definirGrupo] = useState<Grupo>("pesos");
  const [carregando, definirCarregando] = useState(true);
  const [erro, definirErro] = useState<string | null>(null);
  const [erroDeValidacao, definirErroDeValidacao] = useState<string | null>(null);
  const [atual, definirAtual] = useState<Parametros | null>(null);
  const [campos, definirCampos] = useState<Campos | null>(null);
  const [mix, definirMix] = useState<Record<string, number>>({});
  const [autor, definirAutor] = useState("");
  const [motivo, definirMotivo] = useState("");
  const [salvando, definirSalvando] = useState(false);
  const [salvo, definirSalvo] = useState(false);

  useEffect(() => {
    api.parametrosAtuais()
      .then((p) => {
        definirAtual(p);
        definirCampos(paraCampos(p));
        const m: Record<string, number> = {};
        for (const c of p.mix) m[`${c.porte}|${c.cargo}`] = Number(c.mix_percentual);
        definirMix(m);
      })
      .catch((e) => definirErro(e instanceof ErroDaApi ? e.message : "Falha ao carregar os parâmetros."))
      .finally(() => definirCarregando(false));
  }, []);

  if (carregando) return <p className="campo-ajuda">Carregando parâmetros…</p>;
  if (erro || !campos) {
    return (
      <div className="estado estado-erro" role="alert">
        <p className="estado-texto">{erro ?? "Falha ao carregar os parâmetros."}</p>
      </div>
    );
  }

  const somaDosPesos = ["peso_receita", "peso_rentabilidade", "peso_cross_sell", "peso_complexidade",
    "peso_disciplina", "peso_risco", "peso_adimplencia"].reduce((s, k) => s + (campos[k as keyof Campos] as number), 0);
  const pesosFecham100 = Math.abs(somaDosPesos - 1) < 0.0005;

  const somaDoMixPorPorte = (porte: string) =>
    CARGOS.reduce((s, c) => s + (mix[`${porte}|${c}`] ?? 0), 0);
  const todoMixFecha100 = PORTES.every((p) => Math.abs(somaDoMixPorPorte(p) - 1) < 0.0005);

  const alterar = <K extends keyof Campos>(campo: K, valor: number) =>
    definirCampos({ ...campos, [campo]: valor });

  const alterarMix = (porte: string, cargo: string, valor: number) =>
    definirMix({ ...mix, [`${porte}|${cargo}`]: valor });

  const custoHoraDoPorte = (porte: string) =>
    CARGOS.reduce((s, c) => s + (mix[`${porte}|${c}`] ?? 0) * (campos[TAXA_POR_CARGO[c] as keyof Campos] as number), 0);

  const podeSalvar = autor.trim().length >= 2 && motivo.trim().length >= 3 && pesosFecham100 && todoMixFecha100 && !salvando;

  const salvar = async () => {
    definirSalvando(true);
    definirErro(null);
    definirErroDeValidacao(null);
    definirSalvo(false);
    try {
      const corpo: EdicaoDeParametros = {
        autor: autor.trim(), motivo: motivo.trim(), ...campos,
        mix: PORTES.flatMap((porte) => CARGOS.map((cargo) => ({ porte, cargo, mix_percentual: mix[`${porte}|${cargo}`] ?? 0 }))),
      };
      const nova = await api.editarParametros(corpo);
      definirAtual(nova);
      definirCampos(paraCampos(nova));
      definirSalvo(true);
      definirMotivo("");
    } catch (e) {
      if (e instanceof ErroDaApi && e.status === 422) definirErroDeValidacao(e.message);
      else definirErro("Falha ao salvar os parâmetros.");
    } finally {
      definirSalvando(false);
    }
  };

  return (
    <section className="avaliacao-secao">
      <h3>Parâmetros de cálculo</h3>
      <p className="campo-ajuda" style={{ marginTop: 0 }}>
        Valem para <strong>toda a carteira</strong> — é o que mede o Índice de Saúde. Salvar aqui grava uma versão nova —
        a anterior fica no histórico, e as classificações já feitas não mudam. Vigente desde{" "}
        {atual && new Date(atual.criado_em).toLocaleString("pt-BR")}, por {atual?.autor}.
      </p>

      <div className="abas abas-avaliacao" role="tablist" aria-label="Grupos de parâmetros de cálculo">
        {GRUPOS.map((g) => (
          <button
            key={g.chave} type="button" role="tab" className="aba"
            aria-selected={grupo === g.chave} onClick={() => definirGrupo(g.chave)}
          >
            {g.rotulo}
            {g.chave === "pesos" && !pesosFecham100 && " ⚠"}
            {g.chave === "matriz" && !todoMixFecha100 && " ⚠"}
          </button>
        ))}
      </div>

      {grupo === "pesos" && (
        <div className="avaliacao-secao">
          <h3>Pesos do Score {!pesosFecham100 && <span style={{ color: "var(--vermelho-alerta, #c0392b)" }}>— soma {formatoPercentual(somaDosPesos)}, precisa fechar 100%</span>}</h3>
          <CampoPercentual rotulo="Receita" valor={campos.peso_receita} aoMudar={(v) => alterar("peso_receita", v)} />
          <CampoPercentual rotulo="Rentabilidade" valor={campos.peso_rentabilidade} aoMudar={(v) => alterar("peso_rentabilidade", v)} />
          <CampoPercentual rotulo="Cross-sell" valor={campos.peso_cross_sell} aoMudar={(v) => alterar("peso_cross_sell", v)} />
          <CampoPercentual rotulo="Complexidade (invertida)" valor={campos.peso_complexidade} aoMudar={(v) => alterar("peso_complexidade", v)} />
          <CampoPercentual rotulo="Disciplina" valor={campos.peso_disciplina} aoMudar={(v) => alterar("peso_disciplina", v)} />
          <CampoPercentual rotulo="Risco técnico (invertido)" valor={campos.peso_risco} aoMudar={(v) => alterar("peso_risco", v)} />
          <CampoPercentual rotulo="Adimplência" valor={campos.peso_adimplencia} aoMudar={(v) => alterar("peso_adimplencia", v)} />
        </div>
      )}

      {grupo === "cortes" && (
        <div className="avaliacao-secao">
          <h3>Cortes de classe e travas</h3>
          <label className="campo-bloco">
            <span className="campo-rotulo">Corte A — Score mínimo</span>
            <input className="entrada" type="number" step="0.01" value={campos.corte_a}
              onChange={(e) => alterar("corte_a", Number(e.target.value))} />
          </label>
          <label className="campo-bloco">
            <span className="campo-rotulo">Corte B — Score mínimo</span>
            <input className="entrada" type="number" step="0.01" value={campos.corte_b}
              onChange={(e) => alterar("corte_b", Number(e.target.value))} />
          </label>
          <label className="campo-bloco">
            <span className="campo-rotulo">Trava de inadimplência — nota ≤</span>
            <input className="entrada" type="number" min={1} max={5} value={campos.trava_de_adimplencia}
              onChange={(e) => alterar("trava_de_adimplencia", Number(e.target.value))} />
          </label>
          <label className="campo-bloco">
            <span className="campo-rotulo">Churn alto — nota ≥</span>
            <input className="entrada" type="number" min={1} max={5} value={campos.churn_alto}
              onChange={(e) => alterar("churn_alto", Number(e.target.value))} />
          </label>
        </div>
      )}

      {grupo === "rentabilidade" && (
        <div className="avaliacao-secao">
          <h3>Rentabilidade — imposto, atrito e margem</h3>
          <CampoPercentual rotulo="Imposto" valor={campos.imposto} aoMudar={(v) => alterar("imposto", v)} />
          <label className="campo-bloco">
            <span className="campo-rotulo">Teto de atrito (soma dos três quesitos)</span>
            <input className="entrada" type="number" step="0.1" value={campos.teto_de_atrito}
              onChange={(e) => alterar("teto_de_atrito", Number(e.target.value))} />
          </label>
          <p className="campo-ajuda" style={{ marginBottom: 0 }}>Acréscimo de horas por nota (1 a 5), igual nos três quesitos:</p>
          <div className="par">
            {([1, 2, 3, 4, 5] as const).map((n) => (
              <CampoPercentual key={n} rotulo={`Nota ${n}`} valor={campos[`atrito_nota_${n}` as keyof Campos] as number}
                aoMudar={(v) => alterar(`atrito_nota_${n}` as keyof Campos, v)} />
            ))}
          </div>
          <p className="campo-ajuda" style={{ marginBottom: 0 }}>Corte de margem mínima para cada nota (nota 1 = abaixo do corte da nota 2):</p>
          <div className="par">
            {([2, 3, 4, 5] as const).map((n) => (
              <CampoPercentual key={n} rotulo={`Nota ${n}`} valor={campos[`corte_margem_${n}` as keyof Campos] as number}
                aoMudar={(v) => alterar(`corte_margem_${n}` as keyof Campos, v)} />
            ))}
          </div>
        </div>
      )}

      {grupo === "matriz" && (
        <div className="avaliacao-secao">
          <h3>Matriz de horas e mix de equipe por Porte</h3>
          <p className="campo-ajuda" style={{ marginTop: 0 }}>
            O custo/hora ponderado é calculado (taxa × mix, somado por Porte) — nunca digitado solto. A soma do mix
            de cada Porte precisa fechar 100%.
          </p>
          <p className="campo-ajuda" style={{ marginBottom: 0 }}>Taxa por hora (não varia por Porte):</p>
          <div className="par">
            {CARGOS.map((cargo) => (
              <label key={cargo} className="campo-bloco">
                <span className="campo-rotulo">{cargo}</span>
                <input className="entrada" type="number" step="0.01" value={campos[TAXA_POR_CARGO[cargo] as keyof Campos] as number}
                  onChange={(e) => alterar(TAXA_POR_CARGO[cargo] as keyof Campos, Number(e.target.value))} />
              </label>
            ))}
          </div>
          <div className="tabela-rolagem">
            <table className="tabela">
              <thead>
                <tr>
                  <th>Porte</th>
                  <th className="tabela-numero">Horas/mês</th>
                  {CARGOS.map((c) => <th key={c} className="tabela-numero">{c}</th>)}
                  <th className="tabela-numero">Soma</th>
                  <th className="tabela-numero">Custo/hora</th>
                </tr>
              </thead>
              <tbody>
                {PORTES.map((porte) => {
                  const soma = somaDoMixPorPorte(porte);
                  const fecha = Math.abs(soma - 1) < 0.0005;
                  return (
                    <tr key={porte}>
                      <td>{porte}</td>
                      <td className="tabela-numero">
                        <input className="entrada" type="number" min={1} style={{ width: 64 }}
                          value={campos[HORAS_POR_PORTE[porte] as keyof Campos] as number}
                          onChange={(e) => alterar(HORAS_POR_PORTE[porte] as keyof Campos, Number(e.target.value))} />
                      </td>
                      {CARGOS.map((cargo) => (
                        <td key={cargo} className="tabela-numero">
                          <input
                            className="entrada" type="number" step="0.01" min={0} max={100} style={{ width: 60 }}
                            value={Math.round((mix[`${porte}|${cargo}`] ?? 0) * 10000) / 100}
                            onChange={(e) => alterarMix(porte, cargo, e.target.value === "" ? 0 : Number(e.target.value) / 100)}
                          />
                        </td>
                      ))}
                      <td className="tabela-numero" style={{ color: fecha ? undefined : "var(--vermelho-alerta, #c0392b)" }}>
                        {formatoPercentual(soma)}
                      </td>
                      <td className="tabela-numero">
                        {custoHoraDoPorte(porte).toLocaleString("pt-BR", { style: "currency", currency: "BRL" })}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {erroDeValidacao && (
        <div className="estado estado-erro" role="alert"><p className="estado-texto">{erroDeValidacao}</p></div>
      )}
      {erro && <div className="estado estado-erro" role="alert"><p className="estado-texto">{erro}</p></div>}
      {salvo && <p className="campo-ajuda">Nova versão salva.</p>}

      <label className="campo-bloco">
        <span className="campo-rotulo">Quem está alterando</span>
        <input className="entrada" value={autor} onChange={(e) => definirAutor(e.target.value)} placeholder="Nome de quem preencheu" />
      </label>
      <label className="campo-bloco">
        <span className="campo-rotulo">Motivo da mudança</span>
        <input className="entrada" value={motivo} onChange={(e) => definirMotivo(e.target.value)} placeholder="Por que os parâmetros mudaram" />
      </label>
      <button type="button" className="botao botao-primario" disabled={!podeSalvar} onClick={salvar}>
        {salvando ? "Salvando…" : "Salvar nova versão dos parâmetros"}
      </button>
    </section>
  );
}
