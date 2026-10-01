/** Campo de data sempre no padrão brasileiro (dd/mm/aaaa), qualquer que seja o idioma do
 * navegador. O `<input type="date">` nativo segue o idioma do sistema — num Windows em inglês
 * aparecia mm/dd/aaaa (Karine, 01/10/2026).
 *
 * Por dentro o valor continua ISO (aaaa-mm-dd), o mesmo que a API grava: quem usa o campo não
 * muda. As barras entram sozinhas ao digitar, e o 📅 abre um calendário em português. Data que
 * não existe (31/02) não é repassada: o campo avisa "data inválida".
 */

import { useEffect, useRef, useState } from "react";
import { brParaIso, isoParaBr, mascarar } from "../dataBr";

const MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto",
  "Setembro", "Outubro", "Novembro", "Dezembro"];
const DIAS = ["D", "S", "T", "Q", "Q", "S", "S"];

const doisDigitos = (n: number) => String(n).padStart(2, "0");

export function CampoDeData({
  id,
  value,
  aoMudar,
  disabled,
  className = "entrada",
  ...resto
}: {
  id?: string;
  value: string | null | undefined;
  aoMudar: (iso: string) => void;
  disabled?: boolean;
  className?: string;
  "aria-label"?: string;
  "aria-describedby"?: string;
}) {
  const [texto, definirTexto] = useState(isoParaBr(value));
  const [aberto, definirAberto] = useState(false);
  const raiz = useRef<HTMLDivElement>(null);
  const hojeIso = new Date().toLocaleDateString("sv");
  const base = (value || hojeIso).slice(0, 7);
  const [mesVisto, definirMesVisto] = useState(base);

  // O valor de fora mudou (outro registro aberto, formulário limpo): o texto acompanha.
  // Ajuste durante a renderização, como a documentação do React recomenda, em vez de um efeito.
  const [valorVisto, definirValorVisto] = useState(value);
  if (value !== valorVisto) {
    definirValorVisto(value);
    if (brParaIso(texto) !== (value || null)) definirTexto(isoParaBr(value));
  }

  useEffect(() => {
    if (!aberto) return;
    const fora = (e: MouseEvent) => {
      if (raiz.current && !raiz.current.contains(e.target as Node)) definirAberto(false);
    };
    document.addEventListener("mousedown", fora);
    return () => document.removeEventListener("mousedown", fora);
  }, [aberto]);

  const digitar = (bruto: string) => {
    const t = mascarar(bruto);
    definirTexto(t);
    if (t === "") aoMudar("");
    else {
      const iso = brParaIso(t);
      if (iso) aoMudar(iso);
    }
  };

  const invalido = texto.length === 10 && brParaIso(texto) === null;
  const [ano, mes] = mesVisto.split("-").map(Number);
  const primeiroDia = new Date(ano, mes - 1, 1).getDay();
  const diasNoMes = new Date(ano, mes, 0).getDate();
  const andar = (delta: number) => {
    const d = new Date(ano, mes - 1 + delta, 1);
    definirMesVisto(`${d.getFullYear()}-${doisDigitos(d.getMonth() + 1)}`);
  };
  const escolher = (dia: number) => {
    const iso = `${ano}-${doisDigitos(mes)}-${doisDigitos(dia)}`;
    definirTexto(isoParaBr(iso));
    aoMudar(iso);
    definirAberto(false);
  };

  return (
    <div className="campo-data" ref={raiz}>
      <div className="campo-data-linha">
        <input
          id={id}
          className={className}
          inputMode="numeric"
          placeholder="dd/mm/aaaa"
          maxLength={10}
          value={texto}
          disabled={disabled}
          aria-invalid={invalido || undefined}
          onChange={(e) => digitar(e.target.value)}
          {...resto}
        />
        <button type="button" className="botao botao-secundario campo-data-botao" disabled={disabled}
          aria-label="Abrir calendário" aria-expanded={aberto}
          onClick={() => { definirMesVisto(base); definirAberto((a) => !a); }}>
          📅
        </button>
      </div>
      {invalido && <p className="campo-ajuda campo-data-erro" role="alert">Data inválida.</p>}
      {aberto && (
        <div className="campo-data-calendario" role="dialog" aria-label="Calendário">
          <div className="campo-data-cabecalho">
            <button type="button" className="botao botao-secundario" aria-label="Mês anterior" onClick={() => andar(-1)}>‹</button>
            <strong>{MESES[mes - 1]} {ano}</strong>
            <button type="button" className="botao botao-secundario" aria-label="Próximo mês" onClick={() => andar(1)}>›</button>
          </div>
          <div className="campo-data-grade">
            {DIAS.map((d, i) => <span key={i} className="campo-data-semana">{d}</span>)}
            {Array.from({ length: primeiroDia }, (_, i) => <span key={`v${i}`} />)}
            {Array.from({ length: diasNoMes }, (_, i) => {
              const dia = i + 1;
              const iso = `${ano}-${doisDigitos(mes)}-${doisDigitos(dia)}`;
              return (
                <button key={dia} type="button" aria-label={isoParaBr(iso)}
                  className={`campo-data-dia${iso === value ? " campo-data-escolhido" : ""}${iso === hojeIso ? " campo-data-hoje" : ""}`}
                  onClick={() => escolher(dia)}>
                  {dia}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
