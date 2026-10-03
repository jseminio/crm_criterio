/** Configurações › Metas: a reunião de resultado de cada classe e a intenção dela (03/10/2026, aprovado
 * por Eduardo). Uma reunião por classe: A mensal, B trimestral, C semestral. A intenção aparece no topo
 * do funil da classe. O Funil do Sucesso do Cliente cobra o que estiver aqui; cada mudança vai para o
 * histórico de alterações. A bimestral é interna, da carteira, e fica fora das classes. */

import { useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { CadenciaDeReunioes as Cadencia } from "../api/tipos";
import { dataHora } from "../formato";
import { usarDados } from "../usarDados";
import { Carregando, Erro } from "./estados";

const TIPOS = [
  { chave: "mensal", nome: "Mensal" },
  { chave: "trimestral", nome: "Trimestral" },
  { chave: "semestral", nome: "Semestral" },
];

type Rascunho = { cadencia: Record<string, string>; intencao: Record<string, string> };

export function CadenciaDeReunioes() {
  const { dados, carregando, erro, recarregar } = usarDados<Cadencia>(() => api.cadenciaDeReunioes(), []);
  const [rascunho, definirRascunho] = useState<Rascunho | null>(null);
  const [salvando, definirSalvando] = useState(false);
  const [falha, definirFalha] = useState<string | null>(null);
  const [feito, definirFeito] = useState<string | null>(null);

  if (carregando && !dados) return <Carregando rotulo="Abrindo a cadência das reuniões" />;
  if (erro) return <Erro mensagem={erro} aoTentarDeNovo={recarregar} />;
  if (!dados) return null;
  const classes = Object.keys(dados.cadencia).sort();
  const gravado: Rascunho = {
    cadencia: Object.fromEntries(classes.map((c) => [c, dados.cadencia[c]?.[0] ?? ""])),
    intencao: Object.fromEntries(classes.map((c) => [c, dados.intencao[c] ?? ""])),
  };
  const atual = rascunho ?? gravado;
  const mudar = (parte: keyof Rascunho, classe: string, valor: string) => {
    definirFeito(null);
    definirRascunho({ ...atual, [parte]: { ...atual[parte], [classe]: valor } });
  };
  const mudadas = (parte: keyof Rascunho) => classes.filter((c) => atual[parte][c] !== gravado[parte][c]);
  // Uma classe com mais de uma reunião (gravada antes) só muda se a pessoa escolher outra.
  const mudou = mudadas("cadencia").length + mudadas("intencao").length > 0;

  const salvar = async () => {
    definirSalvando(true);
    definirFalha(null);
    try {
      await api.mudarCadenciaDeReunioes({
        cadencia: Object.fromEntries(mudadas("cadencia").map((c) => [c, [atual.cadencia[c]]])),
        intencao: Object.fromEntries(mudadas("intencao").map((c) => [c, atual.intencao[c]])),
      });
      definirRascunho(null);
      recarregar();
      definirFeito("Salvo. O Funil do Sucesso do Cliente já cobra as reuniões e mostra a intenção nova.");
    } catch (f) {
      definirFalha(f instanceof ErroDaApi ? f.message : "Falha ao salvar a cadência.");
    } finally {
      definirSalvando(false);
    }
  };

  return (
    <section className="numero" aria-labelledby="cadencia-titulo">
      <h3 className="numero-rotulo" id="cadencia-titulo">Reuniões de resultado por classe</h3>
      <p className="campo-ajuda">
        Uma reunião por classe; em todas, as lacunas técnicas do cliente viram oferta. Ela vence pelo intervalo
        (1, 3 ou 6 meses), contado da última registrada. A intenção aparece no topo do funil da classe; apagada,
        volta ao texto padrão.
      </p>
      <table className="tabela cadencia">
        <thead>
          <tr><th>Classe</th><th>Reunião</th><th className="cadencia-intencao">Intenção da classe</th></tr>
        </thead>
        <tbody>
          {classes.map((c) => (
            <tr key={c}>
              <td><strong>{c}</strong></td>
              <td>
                <select className="selecao" aria-label={`Classe ${c}: reunião`} value={atual.cadencia[c]}
                  onChange={(e) => mudar("cadencia", c, e.target.value)}>
                  {!TIPOS.some((t) => t.chave === atual.cadencia[c]) && <option value={atual.cadencia[c]}>—</option>}
                  {TIPOS.map((t) => <option key={t.chave} value={t.chave}>{t.nome}</option>)}
                </select>
              </td>
              <td>
                <textarea className="entrada" rows={4} aria-label={`Classe ${c}: intenção`} value={atual.intencao[c]}
                  onChange={(e) => mudar("intencao", c, e.target.value)} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="perfis-acoes">
        <button type="button" className="botao botao-primario" disabled={!mudou || salvando} onClick={() => void salvar()}>
          {salvando ? "Salvando…" : "Salvar"}
        </button>
        {mudou && <span className="campo-ajuda">· alterações ainda não salvas</span>}
        {dados.alterado_em && (
          <span className="campo-ajuda">Última mudança: {dados.alterado_por ? `${dados.alterado_por}, ` : ""}{dataHora(dados.alterado_em)}</span>
        )}
      </div>
      <p className="campo-ajuda" style={{ margin: 0 }}>
        Reunião bimestral da carteira (interna, Head do BPO e CEO da Critério): a cada 2 meses, fora das classes.
      </p>
      {falha && <p className="estado estado-erro estado-texto" role="alert">✗ {falha}</p>}
      {feito && <p className="recado" role="status">✓ {feito}</p>}
    </section>
  );
}
