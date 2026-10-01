/** Contatos > Nova empresa: dados cadastrais, endereço e os contatos vinculados.
 *
 * Os contatos vêm da base única (a pessoa é cadastrada antes, em "Nova pessoa") e podem estar
 * em várias empresas; cada empresa pode ter vários contatos principais. O grupo (o cliente) é
 * reaproveitado pelo nome ou nasce um prospect novo. Pedido de Karine em 30/09/2026.
 */

import { useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { PessoaDeContato } from "../api/tipos";
import { BuscaDeContato } from "../componentes/BuscaDeContato";
import { PainelLateral } from "../componentes/PainelLateral";

const UFS = "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split(" ");

const VAZIO = {
  razao_social: "", cnpj: "", logradouro: "", numero: "", complemento: "", bairro: "", municipio: "", uf: "", cep: "",
};

type Vinculado = { pessoa: PessoaDeContato; principal: boolean };

export function NovaEmpresa({ aoFechar, aoCriar }: { aoFechar: () => void; aoCriar: () => void }) {
  const [c, definirC] = useState(VAZIO);
  const [vinculados, definirVinculados] = useState<Vinculado[]>([]);
  const [erro, definirErro] = useState<string | null>(null);
  const [salvando, definirSalvando] = useState(false);
  const mudar = (k: keyof typeof VAZIO, v: string) => definirC((a) => ({ ...a, [k]: v }));

  const campo = (k: keyof typeof VAZIO, rotulo: string) => (
    <div className="campo-bloco">
      <label className="campo-rotulo" htmlFor={`ne-${k}`}>{rotulo}</label>
      <input id={`ne-${k}`} className="entrada" value={c[k]} onChange={(e) => mudar(k, e.target.value)} />
    </div>
  );

  const salvar = async () => {
    definirSalvando(true);
    definirErro(null);
    try {
      const dados: Record<string, unknown> = Object.fromEntries(
        Object.entries(c).map(([k, v]) => [k, v.trim() === "" ? null : v.trim()]),
      );
      dados.contatos = vinculados.map((v) => ({ pessoa_id: v.pessoa.id, principal: v.principal }));
      await api.criarEmpresa(dados);
      aoCriar();
      aoFechar();
    } catch (f) {
      definirErro(f instanceof ErroDaApi ? f.message : "Falha ao salvar.");
    } finally {
      definirSalvando(false);
    }
  };

  return (
    <PainelLateral
      titulo="Nova empresa"
      subtitulo="Dados, endereço e os contatos já cadastrados"
      aoFechar={aoFechar}
      rodape={
        <>
          <button type="button" className="botao botao-secundario" onClick={aoFechar}>Cancelar</button>
          <button type="button" className="botao botao-primario" onClick={salvar}
            disabled={salvando || c.razao_social.trim() === ""}>
            {salvando ? "Salvando…" : "Salvar empresa"}
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
        <h3 style={{ fontSize: 14 }}>Empresa e endereço</h3>
        <div className="formulario-duplo">{campo("razao_social", "Razão social")}{campo("cnpj", "CNPJ")}</div>
        <div className="formulario-duplo">{campo("logradouro", "Logradouro")}{campo("numero", "Número")}</div>
        <div className="formulario-duplo">{campo("complemento", "Complemento")}{campo("bairro", "Bairro")}</div>
        <div className="formulario-duplo">
          {campo("municipio", "Município")}
          <div className="campo-bloco">
            <label className="campo-rotulo" htmlFor="ne-uf">UF</label>
            <select id="ne-uf" className="selecao" value={c.uf} onChange={(e) => mudar("uf", e.target.value)}>
              <option value="">—</option>
              {UFS.map((u) => <option key={u} value={u}>{u}</option>)}
            </select>
          </div>
        </div>
        <div className="formulario-duplo">{campo("cep", "CEP")}<span /></div>

        <h3 style={{ fontSize: 14 }}>Contato(s) vinculado(s)</h3>
        <BuscaDeContato
          id="ne-busca-contato"
          jaVinculados={vinculados.map((v) => v.pessoa.id)}
          aoEscolher={(pessoa) => definirVinculados((a) => [...a, { pessoa, principal: false }])}
        />
        {vinculados.length === 0 ? (
          <p className="campo-ajuda" style={{ margin: 0 }}>Nenhum contato vinculado ainda.</p>
        ) : (
          <ul className="contatos-lista" aria-label="Contatos vinculados">
            {vinculados.map((v) => (
              <li key={v.pessoa.id} className="contato-item">
                <div>
                  <strong>{v.principal ? "★ " : ""}{v.pessoa.nome}</strong>
                  {v.principal && <span className="etiqueta etiqueta-neutra" style={{ marginLeft: 6 }}>Principal</span>}
                </div>
                <div className="sugestao-acoes" style={{ justifyContent: "flex-start" }}>
                  <label style={{ display: "flex", gap: "var(--e1)", alignItems: "center", fontSize: 13 }}>
                    <input type="checkbox" checked={v.principal}
                      onChange={(e) => definirVinculados((a) => a.map((x) => (x.pessoa.id === v.pessoa.id ? { ...x, principal: e.target.checked } : x)))} />
                    Contato principal
                  </label>
                  <button type="button" className="botao botao-secundario"
                    onClick={() => definirVinculados((a) => a.filter((x) => x.pessoa.id !== v.pessoa.id))}>
                    Desvincular
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="recado">
        A empresa entra como <strong>prospect</strong>, num grupo com o mesmo nome — ou no grupo que já
        existir com esse nome. Pode haver mais de um contato principal.
      </div>
    </PainelLateral>
  );
}
