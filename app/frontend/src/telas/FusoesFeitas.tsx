/** As fusões já feitas, com o botão **Desfazer** (precaução pedida por Eduardo, 26/09/2026).
 *
 * Desfazer devolve ao grupo absorvido exatamente o que a fusão tirou dele e o reabre. O que foi
 * criado no principal depois da fusão fica onde está. Pede confirmação em dois passos.
 */

import { useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { FusaoFeita } from "../api/tipos";
import { dataHora } from "../formato";
import { usarDados } from "../usarDados";

function resumo(f: FusaoFeita): string {
  const partes = [
    [f.empresas, "empresa", "empresas"], [f.oportunidades, "proposta", "propostas"],
    [f.contatos, "contato", "contatos"], [f.contratos, "contrato", "contratos"],
  ]
    .filter(([n]) => (n as number) > 0)
    .map(([n, um, varios]) => `${n} ${n === 1 ? um : varios}`);
  return partes.length ? partes.join(", ") : "nada para mover";
}

function Linha({ fusao, aoDesfazer }: { fusao: FusaoFeita; aoDesfazer: () => void }) {
  const [confirmando, definirConfirmando] = useState(false);
  const [desfazendo, definirDesfazendo] = useState(false);
  const [erro, definirErro] = useState<string | null>(null);

  const desfazer = async () => {
    definirDesfazendo(true);
    definirErro(null);
    try {
      await api.desfazerFusao(fusao.id);
      aoDesfazer();
    } catch (f) {
      definirErro(f instanceof ErroDaApi ? f.message : "Falha ao desfazer.");
      definirConfirmando(false);
    } finally {
      definirDesfazendo(false);
    }
  };

  return (
    <li className="fusao-linha">
      <div>
        <strong>{fusao.absorvido_nome}</strong> → {fusao.principal_nome}
        <span className="numero-nota">
          {" "}· {resumo(fusao)} · {dataHora(fusao.feita_em)}
          {fusao.reconstruida && " · registro refeito do backup"}
        </span>
      </div>
      {erro && <p role="alert" className="estado-texto">{erro}</p>}
      {!fusao.pode_desfazer ? (
        <span className="numero-nota">não dá para desfazer</span>
      ) : confirmando ? (
        <div className="sugestao-acoes">
          <button type="button" className="botao botao-secundario" onClick={() => definirConfirmando(false)}>Cancelar</button>
          <button type="button" className="botao botao-primario" disabled={desfazendo} onClick={desfazer}>
            {desfazendo ? "Desfazendo…" : `Confirmar: devolver ${resumo(fusao)}`}
          </button>
        </div>
      ) : (
        <button type="button" className="botao botao-secundario" onClick={() => definirConfirmando(true)}>Desfazer</button>
      )}
    </li>
  );
}

export function FusoesFeitas({ aoMudar, versao }: { aoMudar: () => void; versao: number }) {
  const { dados, recarregar } = usarDados<FusaoFeita[]>(() => api.fusoesFeitas(), [versao]);
  const [aberto, definirAberto] = useState(false);
  if (!dados || dados.length === 0) return null;

  return (
    <section className="recado" aria-label="Fusões feitas">
      <button type="button" className="link-de-tabela" aria-expanded={aberto} onClick={() => definirAberto((a) => !a)}>
        {aberto ? "Ocultar" : "Ver"} as {dados.length} fusões feitas (dá para desfazer)
      </button>
      {aberto && (
        <>
          <p className="numero-nota">
            Desfazer devolve ao grupo absorvido o que a fusão tirou dele e o reabre. O que foi criado no
            grupo principal depois da fusão fica onde está.
          </p>
          <ul className="fusoes">
            {dados.map((f) => (
              <Linha key={f.id} fusao={f} aoDesfazer={() => { recarregar(); aoMudar(); }} />
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
