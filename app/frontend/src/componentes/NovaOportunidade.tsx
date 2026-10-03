/** A proposta nascendo direto no CRM — sem passar pela planilha nem por um
 * lead. Decisão de Eduardo em 22/09/2026 (E4).
 *
 * A empresa é escolhida na base de empresas (nome, razão social ou CNPJ) e o grupo
 * vem dela; o Funil não cadastra empresa — quem não está na base é cadastrado antes,
 * em Contatos > Nova empresa (Karine, 01/10/2026).
 *
 * Serviço recorrente (C1) pede a quantidade de parcelas, e o preço anual
 * passa a ser mensal × parcelas, travado. Pedido de Karine em 30/09/2026; o
 * servidor refaz a conta e ignora qualquer anual digitado.
 *
 * Desde 03/10/2026 (Eduardo), contábil e DP têm 13 mensalidades no ano e
 * financeiro 12: nesses serviços as parcelas saem do serviço e não se pedem.
 *
 * Reajuste: o índice do contrato (IPCA, IGP-M ou sem reajuste), para
 * qualquer serviço. Só registra o índice; não calcula. Pedido de Karine em
 * 30/09/2026.
 */

import { useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { EmpresaEncontrada, Listas, ServicoDoCatalogo } from "../api/tipos";
import { BuscaDeEmpresa } from "./BuscaDeEmpresa";
import { precoPelasParcelas } from "../parcelas";
import { usarDados } from "../usarDados";
import { EscolhaDeServico } from "./CatalogoDeServicos";
import { PainelLateral } from "./PainelLateral";
import { CampoDeData } from "./CampoDeData";

function hoje(): string {
  return new Date().toLocaleDateString("sv"); // "sv" formata como AAAA-MM-DD
}

const CAMPOS_VAZIOS = {
  nome: "",
  servico: "",
  servico_descricao: "",
  servico_tema: "",
  tipo_servico: "",
  data_colocacao: hoje(),
  preco_mensal: "",
  preco_anual: "",
  quantidade_parcelas: "",
  reajuste: "",
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
  const [empresa, definirEmpresa] = useState<EmpresaEncontrada | null>(null);
  const escolherEmpresa = (e: EmpresaEncontrada) => {
    // O nome acompanha a empresa enquanto ninguém o personalizou.
    definirCampos((atual) => ({
      ...atual,
      nome: atual.nome.trim() === "" || atual.nome === empresa?.razao_social ? e.razao_social : atual.nome,
    }));
    definirEmpresa(e);
  };
  const { dados: catalogo } = usarDados<ServicoDoCatalogo[]>(() => api.servicos(), []);
  const doCatalogo = catalogo?.find((s) => s.nome === campos.servico);
  const recorrente = doCatalogo?.recorrente ?? false;
  const meses = doCatalogo?.meses_no_ano ?? null;
  const parcelas = meses ? String(meses) : campos.quantidade_parcelas;
  const anualCalculado = precoPelasParcelas(campos.preco_mensal, parcelas);

  const mudar = (campo: string, valor: string) =>
    definirCampos((atual) => ({ ...atual, [campo]: valor }));

  const salvar = async () => {
    definirSalvando(true);
    definirErro(null);
    try {
      const valores = recorrente
        ? { ...campos, quantidade_parcelas: parcelas, preco_anual: anualCalculado }
        : { ...campos, quantidade_parcelas: "" };
      const corpo = Object.fromEntries(
        Object.entries(valores).filter(([, v]) => v !== ""),
      );
      await api.criarOportunidade({ ...corpo, empresa_id: empresa?.id });
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
            disabled={salvando || campos.nome.trim() === "" || empresa === null}
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
        <BuscaDeEmpresa
          id="n-empresa"
          rotulo="Empresa"
          escolhida={empresa}
          aoEscolher={escolherEmpresa}
          ajuda={empresa ? undefined : "Não achou? Cadastre em Contatos > Nova empresa."}
        />
        {campo("nome", "Nome da oportunidade", { placeholder: "BPO Financeiro — Delta Ltda" })}

        <div className="formulario-duplo">
          <EscolhaDeServico
            id="n-servico"
            rotulo="Serviço"
            valor={campos.servico}
            descricao={campos.servico_descricao}
            tema={campos.servico_tema}
            aoEscolher={(nome, texto, tema) => {
              mudar("servico", nome);
              mudar("servico_descricao", texto);
              mudar("servico_tema", tema);
            }}
          />
          {campo("tipo_servico", "Tipo de serviço", { placeholder: "Contabilidade" })}
        </div>

        {recorrente ? (
          <>
            <div className="formulario-duplo">
              {campo("preco_mensal", "Preço mensal", { type: "number", step: "0.01", min: "0" })}
              {!meses &&
                campo("quantidade_parcelas", "Quantidade de parcelas", {
                  type: "number",
                  step: "1",
                  min: "1",
                  max: "120",
                  placeholder: "12",
                })}
            </div>
            <div className="campo-bloco">
              <label className="campo-rotulo" htmlFor="n-preco_anual">
                Preço anual
              </label>
              <input
                id="n-preco_anual"
                className="entrada"
                type="number"
                value={anualCalculado}
                readOnly
                aria-describedby="n-preco_anual-ajuda"
              />
              <p id="n-preco_anual-ajuda" className="campo-ajuda">
                {meses
                  ? `${campos.servico}: preço mensal × ${meses}. Não se ajusta à mão.`
                  : "Serviço recorrente: calculado como preço mensal × quantidade de parcelas. Não se ajusta à mão."}
              </p>
            </div>
          </>
        ) : (
          <div className="formulario-duplo">
            {campo("preco_mensal", "Preço mensal", { type: "number", step: "0.01", min: "0" })}
            {campo("preco_anual", "Preço anual", { type: "number", step: "0.01", min: "0" })}
          </div>
        )}

        {seletor("reajuste", "Reajuste", listas?.indices_de_reajuste, "Não informado")}

        <div className="campo-bloco">
          <label className="campo-rotulo" htmlFor="n-data_colocacao">Data de originação</label>
          <CampoDeData id="n-data_colocacao" value={campos.data_colocacao} aoMudar={(v) => mudar("data_colocacao", v)} />
        </div>

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
