/** A proposta nascendo direto no CRM — sem passar pela planilha nem por um
 * lead. Decisão de Eduardo em 22/09/2026 (E4).
 *
 * O grupo é reaproveitado pelo nome, ou nasce um novo — mesmo padrão da
 * conversão de lead: um campo de texto só, sem seletor de grupo existente.
 */

import { useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { Listas } from "../api/tipos";
import { PainelLateral } from "./PainelLateral";

function hoje(): string {
  return new Date().toLocaleDateString("sv"); // "sv" formata como AAAA-MM-DD
}

const CAMPOS_VAZIOS = {
  nome: "",
  nome_do_grupo: "",
  servico: "",
  tipo_servico: "",
  data_colocacao: hoje(),
  preco_mensal: "",
  preco_anual: "",
  captador: "",
  temperatura: "",
  tipo_canal: "",
  canal: "",
};

export function NovaOportunidade({
  listas,
  aoFechar,
  aoCriar,
}: {
  listas: Listas | null;
  aoFechar: () => void;
  aoCriar: () => void;
}) {
  const [campos, definirCampos] = useState(CAMPOS_VAZIOS);
  const [erro, definirErro] = useState<string | null>(null);
  const [salvando, definirSalvando] = useState(false);

  const mudar = (campo: string, valor: string) =>
    definirCampos((atual) => ({ ...atual, [campo]: valor }));

  const salvar = async () => {
    definirSalvando(true);
    definirErro(null);
    try {
      const corpo = Object.fromEntries(
        Object.entries(campos).filter(([, v]) => v !== ""),
      );
      await api.criarOportunidade(corpo);
      aoCriar();
      aoFechar();
    } catch (falha) {
      definirErro(falha instanceof ErroDaApi ? falha.message : "Falha ao salvar.");
    } finally {
      definirSalvando(false);
    }
  };

  const campo = (id: string, rotulo: string, extra?: Record<string, unknown>) => (
    <div className="campo-bloco">
      <label className="campo-rotulo" htmlFor={`n-${id}`}>
        {rotulo}
      </label>
      <input
        id={`n-${id}`}
        className="entrada"
        value={campos[id as keyof typeof campos]}
        onChange={(e) => mudar(id, e.target.value)}
        {...extra}
      />
    </div>
  );

  const seletor = (id: string, rotulo: string, opcoes: string[] | undefined, vazio: string) => (
    <div className="campo-bloco">
      <label className="campo-rotulo" htmlFor={`n-${id}`}>
        {rotulo}
      </label>
      <select
        id={`n-${id}`}
        className="selecao"
        value={campos[id as keyof typeof campos]}
        onChange={(e) => mudar(id, e.target.value)}
      >
        <option value="">{vazio}</option>
        {opcoes?.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    </div>
  );

  return (
    <PainelLateral
      titulo="Nova oportunidade"
      subtitulo="Só o nome é obrigatório"
      aoFechar={aoFechar}
      rodape={
        <>
          <button type="button" className="botao botao-secundario" onClick={aoFechar}>
            Cancelar
          </button>
          <button
            type="button"
            className="botao botao-primario"
            onClick={salvar}
            disabled={salvando || campos.nome.trim() === ""}
          >
            {salvando ? "Salvando…" : "Criar oportunidade"}
          </button>
        </>
      }
    >
      {erro && (
        <div className="estado estado-erro" role="alert">
          <p className="estado-texto">{erro}</p>
        </div>
      )}

      <div className="formulario">
        {campo("nome", "Nome da oportunidade", { placeholder: "BPO Financeiro — Delta Ltda" })}
        {campo("nome_do_grupo", "Grupo (cliente)", {
          placeholder: "Se ficar em branco, usa o nome acima",
        })}

        <div className="formulario-duplo">
          {campo("servico", "Serviço", { placeholder: "BPO Contábil" })}
          {campo("tipo_servico", "Tipo de serviço", { placeholder: "Contabilidade" })}
        </div>

        <div className="formulario-duplo">
          {campo("preco_mensal", "Preço mensal", { type: "number", step: "0.01", min: "0" })}
          {campo("preco_anual", "Preço anual", { type: "number", step: "0.01", min: "0" })}
        </div>

        {campo("data_colocacao", "Data de originação", { type: "date" })}

        <div className="formulario-duplo">
          {seletor("captador", "Captador", listas?.captadores, "Não informado")}
          {seletor("temperatura", "Temperatura", listas?.temperaturas, "Não informada")}
        </div>

        <div className="formulario-duplo">
          {seletor("tipo_canal", "Tipo de canal", listas?.tipos_de_canal, "Não informado")}
          {campo("canal", "Canal", { placeholder: "Nome de quem indicou" })}
        </div>
      </div>

      <div className="recado">
        Nasce com situação <strong>Enviar proposta</strong> e origem <strong>CRM</strong>. O
        grupo existente é reaproveitado pelo nome; se não houver, nasce um novo.
      </div>
    </PainelLateral>
  );
}
