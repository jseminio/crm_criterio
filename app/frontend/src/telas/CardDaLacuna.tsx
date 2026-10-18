/** O card certo para uma lacuna, aberto já no campo (amostra aprovada por Eduardo em 18/10/2026): a oportunidade, o
 * contrato (e o encerramento dele), a empresa com os contatos, ou o grupo (cliente). Usado pelo "ir à lacuna" da
 * Integralidade do cadastro e pelo quadro de lacunas do card do grupo. */

import { api } from "../api/cliente";
import type { ContratoDetalhe, EntidadeDeContato, GrupoResumo, Lacuna, Listas } from "../api/tipos";
import { PainelLateral } from "../componentes/PainelLateral";
import { Carregando, Erro } from "../componentes/estados";
import { usarDados } from "../usarDados";
import { EdicaoDeContrato } from "./Contratos";
import { DetalheDaOportunidade } from "./DetalheDaOportunidade";
import { DetalheDoContato } from "./DetalheDoContato";
import { DetalheDoGrupo } from "./DetalheDoGrupo";

/** O mínimo para abrir o card da lacuna: a composição da Integralidade manda isto, o card do grupo manda a `Lacuna`. */
export type AlvoDaLacuna = Pick<Lacuna, "cadastro" | "registro_id" | "chave" | "grupo_id" | "empresa_id" | "contrato_id">;

/** Dá para abrir? Contato sem empresa não tem card de empresa onde morar. */
export function lacunaTemCard(l: AlvoDaLacuna): boolean {
  if (l.cadastro === "Oportunidade") return l.registro_id !== null;
  if (l.cadastro === "Contrato" || l.cadastro === "Encerramento") return l.contrato_id !== null;
  if (l.cadastro === "Empresa" || l.cadastro === "Contato") return l.empresa_id !== null && l.grupo_id !== null;
  return l.grupo_id !== null;
}

function Abrindo({ rotulo, erro, aoTentar, aoFechar }: { rotulo: string; erro: string | null; aoTentar: () => void; aoFechar: () => void }) {
  return (
    <PainelLateral titulo={rotulo} aoFechar={aoFechar}>
      {erro ? <Erro mensagem={erro} aoTentarDeNovo={aoTentar} /> : <Carregando rotulo={rotulo} />}
    </PainelLateral>
  );
}

export function CardDoGrupoPeloId({ grupoId, listas, foco, aoFechar }: {
  grupoId: number; listas: Listas | null; foco?: string; aoFechar: () => void;
}) {
  const { dados, erro, recarregar } = usarDados<GrupoResumo>(() => api.grupo(grupoId), [grupoId]);
  if (!dados) return <Abrindo rotulo="Abrindo o grupo" erro={erro} aoTentar={recarregar} aoFechar={aoFechar} />;
  return <DetalheDoGrupo grupo={dados} listas={listas} foco={foco} aoFechar={aoFechar} aoMudar={() => undefined} />;
}

function CardDoContrato({ contratoId, listas, foco, aoFechar }: {
  contratoId: number; listas: Listas | null; foco?: string; aoFechar: () => void;
}) {
  const { dados, erro, recarregar } = usarDados<ContratoDetalhe>(() => api.contrato(contratoId), [contratoId]);
  if (!dados) return <Abrindo rotulo="Abrindo o contrato" erro={erro} aoTentar={recarregar} aoFechar={aoFechar} />;
  return (
    <EdicaoDeContrato contrato={dados} foco={foco} motivos={listas?.motivos_de_encerramento ?? []}
      iniciativas={listas?.iniciativas_de_encerramento ?? []} aoFechar={aoFechar} aoSalvar={() => undefined} />
  );
}

function CardDaEmpresa({ grupoId, empresaId, listas, foco, aoFechar }: {
  grupoId: number; empresaId: number; listas: Listas | null;
  foco?: { cadastro: "Empresa" | "Contato"; registro_id: number; chave: string }; aoFechar: () => void;
}) {
  // O grupo é cliente ou prospect: procura nos dois (um vem vazio).
  const { dados, erro, recarregar } = usarDados<EntidadeDeContato | "sem-empresa">(async () => {
    const [clientes, prospects] = await Promise.all([api.empresasDoGrupo("cliente", grupoId), api.empresasDoGrupo("prospect", grupoId)]);
    return [...clientes.itens, ...prospects.itens].find((e) => e.empresa_id === empresaId) ?? "sem-empresa";
  }, [grupoId, empresaId]);
  if (dados === "sem-empresa") {
    return <Abrindo rotulo="Abrindo a empresa" erro="A empresa não foi encontrada: pode ter sido excluída ou mudado de grupo."
      aoTentar={recarregar} aoFechar={aoFechar} />;
  }
  if (!dados) return <Abrindo rotulo="Abrindo a empresa" erro={erro} aoTentar={recarregar} aoFechar={aoFechar} />;
  return <DetalheDoContato entidade={dados} listas={listas} foco={foco} aoFechar={aoFechar} aoMudar={recarregar} />;
}

export function CardDaLacuna({ lacuna, listas, aoFechar }: { lacuna: AlvoDaLacuna; listas: Listas | null; aoFechar: () => void }) {
  const l = lacuna;
  if (l.cadastro === "Oportunidade" && l.registro_id !== null) {
    return <DetalheDaOportunidade id={l.registro_id} listas={listas} foco={l.chave} aoFechar={aoFechar} aoSalvar={() => undefined} />;
  }
  if ((l.cadastro === "Contrato" || l.cadastro === "Encerramento") && l.contrato_id !== null) {
    return <CardDoContrato contratoId={l.contrato_id} listas={listas} foco={l.cadastro === "Contrato" ? l.chave : undefined} aoFechar={aoFechar} />;
  }
  if ((l.cadastro === "Empresa" || l.cadastro === "Contato") && l.empresa_id !== null && l.grupo_id !== null && l.registro_id !== null) {
    return (
      <CardDaEmpresa grupoId={l.grupo_id} empresaId={l.empresa_id} listas={listas}
        foco={{ cadastro: l.cadastro, registro_id: l.registro_id, chave: l.chave }} aoFechar={aoFechar} />
    );
  }
  if (l.grupo_id !== null) return <CardDoGrupoPeloId grupoId={l.grupo_id} listas={listas} foco={l.chave} aoFechar={aoFechar} />;
  return null;
}
