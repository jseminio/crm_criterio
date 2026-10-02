/** Escolha da empresa da oportunidade na base de empresas — por nome, razão social ou CNPJ.
 * O Funil não cadastra empresa: quem não está na base é cadastrado antes, em Contatos > Nova
 * empresa (Karine, 01/10/2026). Ao clicar no campo, a lista já aparece.
 */

import { useEffect, useRef, useState } from "react";
import { api } from "../api/cliente";
import type { EmpresaEncontrada } from "../api/tipos";
import { cnpj as formatarCnpj } from "../formato";
import { usarDados } from "../usarDados";

export function BuscaDeEmpresa({
  id,
  rotulo,
  escolhida,
  aoEscolher,
  desabilitado,
  ajuda,
}: {
  id: string;
  rotulo: string;
  escolhida: EmpresaEncontrada | null;
  aoEscolher: (empresa: EmpresaEncontrada) => void;
  desabilitado?: boolean;
  ajuda?: string;
}) {
  const [texto, definirTexto] = useState("");
  const [aberta, definirAberta] = useState(false);
  const [trocando, definirTrocando] = useState(escolhida === null);
  const raiz = useRef<HTMLDivElement>(null);
  const termo = texto.trim();
  const achadas = usarDados<EmpresaEncontrada[]>(
    () => (aberta ? api.buscarEmpresas(termo) : Promise.resolve([])),
    [termo, aberta],
  );

  useEffect(() => {
    if (!aberta) return;
    const fora = (e: MouseEvent) => {
      if (raiz.current && !raiz.current.contains(e.target as Node)) definirAberta(false);
    };
    document.addEventListener("mousedown", fora);
    return () => document.removeEventListener("mousedown", fora);
  }, [aberta]);

  const escolher = (e: EmpresaEncontrada) => {
    aoEscolher(e);
    definirTexto("");
    definirAberta(false);
    definirTrocando(false);
  };

  if (escolhida && !trocando) {
    return (
      <div className="campo-bloco">
        <span className="campo-rotulo">{rotulo}</span>
        <div className="recado" role="status" style={{ display: "flex", gap: "var(--e2)", alignItems: "center", justifyContent: "space-between" }}>
          <span>
            ✓ <strong>{escolhida.razao_social}</strong>
            {escolhida.cnpj && <span className="numero-nota"> · {formatarCnpj(escolhida.cnpj)}</span>}
            <span className="numero-nota"> · {escolhida.grupo_nome}</span>
          </span>
          {!desabilitado && (
            <button type="button" className="botao botao-secundario" onClick={() => { definirTrocando(true); definirAberta(true); }}>
              Trocar
            </button>
          )}
        </div>
        {ajuda && <p className="campo-ajuda">{ajuda}</p>}
      </div>
    );
  }

  const lista = achadas.dados ?? [];
  return (
    <div className="campo-bloco busca-empresa" ref={raiz}>
      <label className="campo-rotulo" htmlFor={id}>{rotulo}</label>
      <input
        id={id}
        className="entrada"
        value={texto}
        disabled={desabilitado}
        placeholder="Nome, razão social ou CNPJ"
        autoComplete="off"
        role="combobox"
        aria-expanded={aberta}
        aria-controls={`${id}-lista`}
        onFocus={() => definirAberta(true)}
        onClick={() => definirAberta(true)}
        onChange={(e) => { definirTexto(e.target.value); definirAberta(true); }}
      />
      {aberta && (
        <ul id={`${id}-lista`} className="busca-empresa-lista" role="listbox" aria-label="Empresas encontradas">
          {lista.map((e) => (
            <li key={e.id} role="option" aria-selected={false}>
              <button type="button" className="busca-empresa-item" onClick={() => escolher(e)}>
                <strong>{e.razao_social}</strong>
                {e.nome_fantasia && e.nome_fantasia !== e.razao_social && <span className="numero-nota"> ({e.nome_fantasia})</span>}
                <span className="numero-nota">
                  {e.cnpj ? ` · ${formatarCnpj(e.cnpj)}` : " · sem CNPJ"} · {e.tipo === "cliente" ? "Cliente" : "Prospect"} · {e.grupo_nome}
                </span>
              </button>
            </li>
          ))}
          {!achadas.carregando && lista.length === 0 && (
            <li className="campo-ajuda busca-empresa-vazio">
              Empresa não encontrada — cadastre em <strong>Contatos &gt; Nova empresa</strong>.
            </li>
          )}
        </ul>
      )}
      {escolhida && trocando && (
        <button type="button" className="botao botao-secundario" style={{ justifySelf: "start" }}
          onClick={() => { definirTrocando(false); definirAberta(false); }}>
          Manter {escolhida.razao_social}
        </button>
      )}
      {ajuda && <p className="campo-ajuda">{ajuda}</p>}
    </div>
  );
}
