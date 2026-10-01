-- Banco do questionário para proposta, no projeto Supabase da Critério (01/10/2026).
-- Cole tudo no SQL Editor do Supabase e clique em Run. Pode rodar mais de uma vez sem estragar nada.
--
-- Regras: o site (chave publicável) só INSERE, e só com o consentimento LGPD marcado. Ninguém de
-- fora lê, altera ou apaga. Quem lê e marca como importado é só o CRM, com a chave secreta.

create table if not exists public.questionarios_proposta (
  id uuid primary key default gen_random_uuid(),
  criado_em timestamptz not null default now(),
  versao_questionario text not null,
  razao_social text not null,
  cnpj text not null,
  nome_fantasia text,
  contato_nome text not null,
  contato_cargo text not null,
  contato_celular text not null,
  contato_email text not null,
  servicos text[] not null default '{}',
  respostas jsonb not null,
  avaliacao jsonb not null,
  porte_sugerido text,
  nota_complexidade integer,
  nota_risco integer,
  horas_propostas_mes numeric,
  consentimento_lgpd boolean not null,
  consentimento_em timestamptz not null,
  pdf_base64 text,
  importado_crm_em timestamptz
);

create index if not exists questionarios_proposta_pendentes
  on public.questionarios_proposta (criado_em) where importado_crm_em is null;

alter table public.questionarios_proposta enable row level security;

-- O site só pode inserir; select/update/delete ficam sem permissão para anon e authenticated.
revoke all on public.questionarios_proposta from anon, authenticated;
grant insert on public.questionarios_proposta to anon, authenticated;

drop policy if exists "insercao publica do questionario" on public.questionarios_proposta;
create policy "insercao publica do questionario" on public.questionarios_proposta
  for insert to anon, authenticated
  with check (consentimento_lgpd = true and importado_crm_em is null);
