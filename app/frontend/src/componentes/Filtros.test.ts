/** As duas funções puras que traduzem o estado dos filtros para a API. */

import { describe, expect, it } from "vitest";
import { FILTROS_VAZIOS, paraConsulta, temFiltro } from "./Filtros";

describe("temFiltro", () => {
  it("diz não para o estado vazio", () => {
    expect(temFiltro(FILTROS_VAZIOS)).toBe(false);
  });

  it("diz sim quando um campo qualquer está preenchido", () => {
    expect(temFiltro({ ...FILTROS_VAZIOS, captador: "EL" })).toBe(true);
  });

  it("diz sim para busca de texto sozinha", () => {
    expect(temFiltro({ ...FILTROS_VAZIOS, busca: "Sogamax" })).toBe(true);
  });
});

describe("paraConsulta", () => {
  it("some com os campos vazios em vez de mandá-los como string vazia", () => {
    // A API interpreta ausência como "sem filtro"; mandar "" filtraria por
    // captador igual a nada, o que não devolveria nada.
    const consulta = paraConsulta(FILTROS_VAZIOS);

    expect(consulta).toEqual({
      busca: undefined,
      captador: undefined,
      tipo_canal: undefined,
      temperatura: undefined,
    });
  });

  it("empacota o valor escolhido numa lista de um item", () => {
    // A API aceita vários valores por filtro (?captador=EL&captador=BO); a
    // tela hoje só deixa escolher um, mas o formato tem de bater com a API.
    const consulta = paraConsulta({ ...FILTROS_VAZIOS, captador: "EL" });

    expect(consulta.captador).toEqual(["EL"]);
  });

  it("mantém a busca como texto simples, não como lista", () => {
    const consulta = paraConsulta({ ...FILTROS_VAZIOS, busca: "Aeskins" });

    expect(consulta.busca).toBe("Aeskins");
  });
});
