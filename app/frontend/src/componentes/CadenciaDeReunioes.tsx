/** Configurações › Metas: quais reuniões de resultado cada classe recebe (02/10/2026). Começa com a
 * cadência aceita por Eduardo (A: todas; B: trimestral e anual; C: anual). O Funil do Sucesso do
 * Cliente cobra o que estiver aqui. Cada mudança vai para o histórico de alterações. */

import { useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { CadenciaDeReunioes as Cadencia } from "../api/tipos";
import { dataHora } from "../formato";
import { usarDados } from "../usarDados";
import { Carregando, Erro } from "./estados";

const TIPOS = [
  { chave: "mensal", nome: "Mensal" },
  { chave: "bimestral", nome: "Bimestral" },
  { chave: "trimestral", nome: "Trimestral" },
  { chave: "anual", nome: "Anual" },
];

export function CadenciaDeReunioes() {
  const { dados, carregando, erro, recarregar } = usarDados<Cadencia>(() => api.cadenciaDeReunioes(), []);
  const [rascunho, definirRascunho] = useState<Record<string, string[]> | null>(null);
  const [salvando, definirSalvando] = useState(false);
  const [falha, definirFalha] = useState<string | null>(null);
  const [feito, definirFeito] = useState<string | null>(null);

  if (carregando && !dados) return <Carregando rotulo="Abrindo a cadência das reuniões" />;
  if (erro) return <Erro mensagem={erro} aoTentarDeNovo={recarregar} />;
  if (!dados) return null;
  const atual = rascunho ?? dados.cadencia;
  const alternar = (classe: string, tipo: string, marcado: boolean) => {
    definirFeito(null);
    const tipos = marcado ? [...(atual[classe] ?? []), tipo] : (atual[classe] ?? []).filter((t) => t !== tipo);
    definirRascunho({ ...atual, [classe]: TIPOS.map((t) => t.chave).filter((t) => tipos.includes(t)) });
  };
  const classes = Object.keys(atual).sort();
  const mudou = classes.some((c) => (atual[c] ?? []).join() !== (dados.cadencia[c] ?? []).join());
  const vazia = classes.find((c) => !(atual[c] ?? []).length);

  const salvar = async () => {
    definirSalvando(true);
    definirFalha(null);
    try {
      await api.mudarCadenciaDeReunioes(atual);
      definirRascunho(null);
      recarregar();
      definirFeito("Cadência salva. O Funil do Sucesso do Cliente já cobra as reuniões novas.");
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
        Quais reuniões o Funil do Sucesso do Cliente cobra de cada classe do Score. Cada uma vence pelo intervalo dela
        (1, 2, 3 ou 12 meses), contado da última registrada.
      </p>
      <table className="tabela cadencia">
        <thead>
          <tr><th>Classe</th>{TIPOS.map((t) => <th key={t.chave}>{t.nome}</th>)}</tr>
        </thead>
        <tbody>
          {classes.map((c) => (
            <tr key={c}>
              <td><strong>{c}</strong></td>
              {TIPOS.map((t) => (
                <td key={t.chave}>
                  <input type="checkbox" aria-label={`Classe ${c}: ${t.nome}`} checked={(atual[c] ?? []).includes(t.chave)}
                    onChange={(e) => alternar(c, t.chave, e.target.checked)} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="perfis-acoes">
        <button type="button" className="botao botao-primario" disabled={!mudou || !!vazia || salvando} onClick={() => void salvar()}>
          {salvando ? "Salvando…" : "Salvar cadência"}
        </button>
        {mudou && !vazia && <span className="campo-ajuda">· alterações ainda não salvas</span>}
        {vazia && <span className="campo-ajuda">· a classe {vazia} precisa de ao menos uma reunião</span>}
        {dados.alterado_em && (
          <span className="campo-ajuda">Última mudança: {dados.alterado_por ? `${dados.alterado_por}, ` : ""}{dataHora(dados.alterado_em)}</span>
        )}
      </div>
      {falha && <p className="estado estado-erro estado-texto" role="alert">✗ {falha}</p>}
      {feito && <p className="recado" role="status">✓ {feito}</p>}
    </section>
  );
}
