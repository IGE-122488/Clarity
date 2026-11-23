-- Passo 3 — Agenda: consultas e notas de cada consulta
-- Cada psicólogo só vê, marca e altera as SUAS consultas, e só para os SEUS pacientes.
-- Até haver DPIA aprovada: APENAS DADOS FICTÍCIOS.

-- 1. Garantir que uma consulta só pode apontar para um paciente do mesmo psicólogo -------------------
-- (a chave estrangeira composta abaixo precisa desta restrição única)
alter table public.pacientes
  add constraint pacientes_id_psicologo_key unique (id, psicologo_id);

-- 2. Tabela -------------------------------------------------------------------------------------------
create table public.consultas (
  id            uuid primary key default gen_random_uuid(),
  psicologo_id  uuid not null default auth.uid() references auth.users (id) on delete cascade,
  paciente_id   uuid not null,
  inicio        timestamptz not null,
  fim           timestamptz not null,
  estado        text not null default 'agendada'
                check (estado in ('agendada', 'realizada', 'cancelada', 'faltou')),
  notas         text check (char_length(notas) <= 20000),
  criado_em     timestamptz not null default now(),
  atualizado_em timestamptz not null default now(),

  constraint consultas_fim_depois_inicio check (fim > inicio),
  constraint consultas_duracao_maxima check (fim - inicio <= interval '8 hours'),
  -- O paciente tem de ser do mesmo psicólogo (as regras RLS não chegam: a verificação
  -- de chaves estrangeiras ignora o RLS).
  constraint consultas_paciente_do_psicologo
    foreign key (paciente_id, psicologo_id) references public.pacientes (id, psicologo_id)
);

comment on table public.consultas is
  'Consultas da agenda de cada psicólogo, com as notas da sessão. RLS: cada psicólogo só acede às suas. Só dados fictícios até à DPIA.';
comment on column public.consultas.estado is
  'agendada | realizada | cancelada | faltou. Não há DELETE pela app: cancela-se.';

create index consultas_psicologo_inicio_idx on public.consultas (psicologo_id, inicio);
create index consultas_paciente_inicio_idx on public.consultas (paciente_id, inicio);

create trigger consultas_atualizado_em
before update on public.consultas
for each row execute function private.tocar_atualizado_em();

-- 3. Permissões (mínimas, coluna a coluna) --------------------------------------------------------------
revoke all on table public.consultas from public, anon, authenticated;
grant select on table public.consultas to authenticated;
grant insert (paciente_id, inicio, fim, estado, notas) on table public.consultas to authenticated;
-- paciente_id não se altera: para outro paciente, marca-se outra consulta.
grant update (inicio, fim, estado, notas) on table public.consultas to authenticated;

-- 4. Regras RLS ---------------------------------------------------------------------------------------
alter table public.consultas enable row level security;

create policy "Psicólogo vê as suas consultas"
on public.consultas for select
to authenticated
using ((select auth.uid()) = psicologo_id);

create policy "Psicólogo marca consultas para si"
on public.consultas for insert
to authenticated
with check ((select auth.uid()) = psicologo_id);

create policy "Psicólogo altera as suas consultas"
on public.consultas for update
to authenticated
using ((select auth.uid()) = psicologo_id)
with check ((select auth.uid()) = psicologo_id);
