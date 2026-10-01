/** O grupo (o cliente) da empresa, informado por nome, com os grupos que já existem como
 * sugestão. Nome novo vira um prospect novo. O contato não tem grupo: ele é ligado só às
 * empresas (pedido de Karine em 01/10/2026).
 */

import { api } from "../api/cliente";
import { usarDados } from "../usarDados";

export function CampoDeGrupo({
  id,
  valor,
  aoMudar,
  desabilitado,
  ajuda,
}: {
  id: string;
  valor: string;
  aoMudar: (valor: string) => void;
  desabilitado?: boolean;
  ajuda?: string;
}) {
  const grupos = usarDados(() => api.grupos(), []);
  const lista = `${id}-sugestoes`;
  return (
    <div className="campo-bloco">
      <label className="campo-rotulo" htmlFor={id}>Grupo</label>
      <input id={id} className="entrada" list={lista} value={valor} disabled={desabilitado}
        onChange={(e) => aoMudar(e.target.value)} placeholder="Em branco: grupo com o nome da empresa" />
      <datalist id={lista}>
        {(grupos.dados?.itens ?? []).map((g) => <option key={g.id} value={g.nome} />)}
      </datalist>
      {ajuda && <p className="campo-ajuda">{ajuda}</p>}
    </div>
  );
}
