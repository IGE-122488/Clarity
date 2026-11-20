-- Passo 2 — Pacientes
-- Cada psicólogo só vê, cria e altera os SEUS pacientes. Quem garante isto é a base de dados (RLS),
-- não a API: mesmo que a API tenha um erro, o Supabase não devolve pacientes de outro psicólogo.
--
-- Minimização de dados (RGPD): só guardamos o necessário para o MVP. Nada de notas clínicas aqui.
-- Até haver DPIA aprovada: APENAS DADOS FICTÍCIOS.

-- 1. Tabela ------------------------------------------------------------------------------------------
create table public.pacientes (
  id              uuid primary key default gen_random_uuid(),
  psicologo_id    uuid not null default auth.uid() references auth.users (id) on delete cascade,
  nome            text not null check (char_length(btrim(nome)) between 1 and 120),
  data_nascimento date check (data_nascimento >= date '1900-01-01'),
  ativo           boolean not null default true,
  criado_em       timestamptz not null default now(),
  atualizado_em   timestamptz not null default now()
);

comment on table public.pacientes is
  'Pacientes de cada psicólogo. RLS: cada psicólogo só acede às suas linhas. Só dados fictícios até à DPIA.';
comment on column public.pacientes.ativo is
  'false = arquivado. Não há DELETE pela app: arquivar em vez de apagar.';

-- Serve as regras RLS (psicologo_id), a chave estrangeira e a ordenação por nome.
create index pacientes_psicologo_nome_idx on public.pacientes (psicologo_id, nome);

-- 2. Atualizar "atualizado_em" automaticamente -------------------------------------------------------
-- Fica num schema que a Data API não expõe, para não poder ser chamada de fora.
create schema if not exists private;
revoke all on schema private from public, anon, authenticated;

create or replace function private.tocar_atualizado_em()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
  new.atualizado_em := now();
  return new;
end;
$$;

revoke execute on function private.tocar_atualizado_em() from public, anon, authenticated;

create trigger pacientes_atualizado_em
before update on public.pacientes
for each row execute function private.tocar_atualizado_em();

-- 3. Quem pode fazer o quê (permissões) ---------------------------------------------------------------
-- O projeto tem a concessão automática desligada, por isso damos só o mínimo, coluna a coluna:
-- ninguém consegue escolher o psicologo_id nem mexer nas datas de criação.
revoke all on table public.pacientes from public, anon, authenticated;
grant select on table public.pacientes to authenticated;
grant insert (nome, data_nascimento) on table public.pacientes to authenticated;
grant update (nome, data_nascimento, ativo) on table public.pacientes to authenticated;
-- Sem DELETE de propósito (ver comentário da coluna "ativo").

-- 4. Regras RLS ---------------------------------------------------------------------------------------
alter table public.pacientes enable row level security;

create policy "Psicólogo vê os seus pacientes"
on public.pacientes for select
to authenticated
using ((select auth.uid()) = psicologo_id);

create policy "Psicólogo cria pacientes para si"
on public.pacientes for insert
to authenticated
with check ((select auth.uid()) = psicologo_id);

create policy "Psicólogo altera os seus pacientes"
on public.pacientes for update
to authenticated
using ((select auth.uid()) = psicologo_id)
with check ((select auth.uid()) = psicologo_id);
