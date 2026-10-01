// Função do site (Lovable Cloud) que o CRM chama na busca de questionários — 01/10/2026.
// Cópia de referência: o que vale é o que está publicado no projeto Lovable, em
// supabase/functions/questionarios-crm/index.ts, com `verify_jwt = false` no supabase/config.toml
// (a função se autentica pela senha). Segredo no Lovable: CRM_QUESTIONARIO_SENHA (openssl rand -hex 32),
// a mesma senha de CRM_QUESTIONARIO_CHAVE no backend/.env do CRM. Sem CORS: só o CRM chama.
//
// GET: questionários pendentes (importado_crm_em vazio), do mais antigo ao mais novo, até 50.
// POST {id, importado_crm_em}: marca um questionário como importado no CRM.
import { createClient } from "npm:@supabase/supabase-js@2";

const TABELA = "questionarios_proposta";

function resposta(corpo: unknown, status = 200): Response {
  return new Response(corpo === null ? null : JSON.stringify(corpo), {
    status,
    headers: corpo === null ? {} : { "Content-Type": "application/json" },
  });
}

async function iguais(a: string, b: string): Promise<boolean> {
  const enc = new TextEncoder();
  const [ha, hb] = await Promise.all([
    crypto.subtle.digest("SHA-256", enc.encode(a)),
    crypto.subtle.digest("SHA-256", enc.encode(b)),
  ]);
  const x = new Uint8Array(ha), y = new Uint8Array(hb);
  let diff = 0;
  for (let i = 0; i < x.length; i++) diff |= x[i] ^ y[i];
  return diff === 0;
}

Deno.serve(async (req) => {
  const senha = Deno.env.get("CRM_QUESTIONARIO_SENHA") ?? "";
  const recebida = req.headers.get("x-crm-senha") ?? "";
  if (senha.length < 32 || !(await iguais(recebida, senha))) {
    return resposta({ erro: "senha ausente ou incorreta" }, 401);
  }
  const sb = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!, {
    auth: { persistSession: false },
  });

  if (req.method === "GET") {
    const { data, error } = await sb.from(TABELA).select("*").is("importado_crm_em", null)
      .order("criado_em", { ascending: true }).limit(50);
    if (error) return resposta({ erro: "falha ao ler os questionários" }, 500);
    return resposta(data ?? []);
  }

  if (req.method === "POST") {
    let corpo: { id?: unknown; importado_crm_em?: unknown };
    try {
      corpo = await req.json();
    } catch {
      return resposta({ erro: "corpo inválido" }, 400);
    }
    const quando = typeof corpo.importado_crm_em === "string" ? new Date(corpo.importado_crm_em) : null;
    if (typeof corpo.id !== "string" || !corpo.id || !quando || isNaN(quando.getTime())) {
      return resposta({ erro: "informe id e importado_crm_em" }, 400);
    }
    const { data, error } = await sb.from(TABELA).update({ importado_crm_em: quando.toISOString() })
      .eq("id", corpo.id).select("id");
    if (error) return resposta({ erro: "falha ao marcar" }, 500);
    if (!data || data.length === 0) return resposta({ erro: "questionário não encontrado" }, 404);
    return resposta(null, 204);
  }

  return resposta({ erro: "método não permitido" }, 405);
});
