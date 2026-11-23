-- Passo 4 — Briefing pré-sessão gerado por IA
-- Um briefing por consulta: resumo das notas das sessões anteriores do mesmo paciente,
-- gerado a pedido do psicólogo, que o pode editar e marcar como revisto.
-- Cada psicólogo só vê e altera os SEUS briefings, e só para as SUAS consultas.
-- Até haver DPIA aprovada: APENAS DADOS FICTÍCIOS.

-- 1. Garantir que um briefing só pode apontar para uma consulta do mesmo psicólogo -------------------
-- (a chave estrangeira composta abaixo precisa desta restrição única)
alter table public.consultas
  add constraint consultas_id_psicologo_key unique (id, psicologo_id);

-- 2. Tabela -------------------------------------------------------------------------------------------
create table public.briefings (
  id             uuid primary key default gen_random_uuid(),
  psicologo_id   uuid not null default auth.uid() references auth.users (id) on delete cascade,
  consulta_id    uuid not null,
  texto          text not null check (char_length(texto) between 1 and 20000),
  revisto        boolean not null default false,
  modelo         text not null check (char_length(modelo) between 1 and 100),
  sessoes_usadas integer not null default 0 check (sessoes_usadas between 0 and 50),
  gerado_em      timestamptz not null default now(),
  criado_em      timestamptz not null default now(),
  atualizado_em  timestamptz not null default now(),

  constraint briefings_um_por_consulta unique (consulta_id),
  -- A consulta tem de ser do mesmo psicólogo (as regras RLS não chegam: a verificação
  -- de chaves estrangeiras ignora o RLS).
  constraint briefings_consulta_do_psicologo
    foreign key (consulta_id, psicologo_id) references public.consultas (id, psicologo_id)
);

comment on table public.briefings is
  'Briefing pré-sessão gerado por IA (um por consulta), editável e revisto pelo psicólogo. RLS: cada psicólogo só acede aos seus. Só dados fictícios até à DPIA.';
comment on column public.briefings.revisto is
  'true depois de o psicólogo ler e confirmar o texto. Volta a false quando o briefing é gerado de novo.';
comment on column public.briefings.sessoes_usadas is
  'Quantas notas de sessões anteriores foram enviadas à IA para gerar este texto.';

create trigger briefings_atualizado_em
before update on public.briefings
for each row execute function private.tocar_atualizado_em();

-- 3. Permissões (mínimas, coluna a coluna) --------------------------------------------------------------
revoke all on table public.briefings from public, anon, authenticated;
grant select on table public.briefings to authenticated;
grant insert (consulta_id, texto, modelo, sessoes_usadas) on table public.briefings to authenticated;
-- consulta_id não se altera. Gerar de novo = atualizar texto, modelo, sessoes_usadas, gerado_em
-- e voltar a pôr revisto = false.
grant update (texto, revisto, modelo, sessoes_usadas, gerado_em)
  on table public.briefings to authenticated;

-- 4. Regras RLS ---------------------------------------------------------------------------------------
alter table public.briefings enable row level security;

create policy "Psicólogo vê os seus briefings"
on public.briefings for select
to authenticated
using ((select auth.uid()) = psicologo_id);

create policy "Psicólogo cria briefings para si"
on public.briefings for insert
to authenticated
with check ((select auth.uid()) = psicologo_id);

create policy "Psicólogo altera os seus briefings"
on public.briefings for update
to authenticated
using ((select auth.uid()) = psicologo_id)
with check ((select auth.uid()) = psicologo_id);
