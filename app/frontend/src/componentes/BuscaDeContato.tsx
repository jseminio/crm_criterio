/** Busca na base única de contatos, por nome, e-mail ou telefone, para vincular uma pessoa
 * já cadastrada a uma empresa — sem cadastrar de novo. Pedido de Karine em 30/09/2026.
 */

import { useState } from "react";
import { api } from "../api/cliente";
import type { PessoaDeContato } from "../api/tipos";
import { usarDados } from "../usarDados";

export function BuscaDeContato({
  id,
  jaVinculados,
  aoEscolher,
}: {
  id: string;
  /** Quem já está vinculado some da lista. */
  jaVinculados: number[];
  aoEscolher: (pessoa: PessoaDeContato) => void;
}) {
  const [texto, definirTexto] = useState("");
  const termo = texto.trim();
  const achados = usarDados<PessoaDeContato[]>(
    () => (termo.length < 2 ? Promise.resolve([]) : api.buscarPessoas(termo)),
    [termo],
  );
  const lista = (achados.dados ?? []).filter((p) => !jaVinculados.includes(p.id));

  return (
    <div style={{ display: "grid", gap: "var(--e2)" }}>
      <div className="campo-bloco">
        <label className="campo-rotulo" htmlFor={id}>Buscar por nome, e-mail ou telefone</label>
        <input id={id} className="entrada" value={texto} onChange={(e) => definirTexto(e.target.value)}
          placeholder="digite ao menos 2 letras" />
      </div>
      {termo.length >= 2 && !achados.carregando && lista.length === 0 && (
        <p className="campo-ajuda" style={{ margin: 0 }}>Nenhum contato encontrado. Cadastre a pessoa em “Nova pessoa”.</p>
      )}
      {lista.length > 0 && (
        <ul className="contatos-lista" aria-label="Contatos encontrados">
          {lista.map((p) => (
            <li key={p.id} className="contato-item">
              <div>
                <strong>{p.nome}</strong>
                {p.cargo && <span className="numero-nota"> · {p.cargo}</span>}
              </div>
              <div className="numero-nota">
                {[p.email, p.telefone].filter(Boolean).join(" · ") || "sem e-mail nem telefone"}
                {" · "}
                {p.empresas && p.empresas.length > 0 ? p.empresas.map((e) => e.razao_social).join(", ") : "sem empresa"}
              </div>
              <button type="button" className="botao botao-secundario" onClick={() => { aoEscolher(p); definirTexto(""); }}>
                Vincular
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
