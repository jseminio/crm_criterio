/** Um gancho só para buscar dados, com os quatro estados que a tela precisa. */

import { useCallback, useEffect, useState } from "react";
import { ErroDaApi } from "./api/cliente";

export interface Busca<T> {
  dados: T | null;
  carregando: boolean;
  erro: string | null;
  recarregar: () => void;
}

export function usarDados<T>(buscar: () => Promise<T>, dependencias: unknown[]): Busca<T> {
  const [dados, definirDados] = useState<T | null>(null);
  const [carregando, definirCarregando] = useState(true);
  const [erro, definirErro] = useState<string | null>(null);
  const [tentativa, definirTentativa] = useState(0);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const executar = useCallback(buscar, dependencias);

  useEffect(() => {
    let vivo = true;
    definirCarregando(true);
    definirErro(null);
    executar()
      .then((resultado) => vivo && definirDados(resultado))
      .catch((falha) => {
        if (!vivo) return;
        definirErro(falha instanceof ErroDaApi ? falha.message : "Falha inesperada.");
      })
      .finally(() => vivo && definirCarregando(false));
    return () => {
      vivo = false;
    };
  }, [executar, tentativa]);

  return {
    dados,
    carregando,
    erro,
    recarregar: () => definirTentativa((n) => n + 1),
  };
}
