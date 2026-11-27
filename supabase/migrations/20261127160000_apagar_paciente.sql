-- Passo 7 — Apagar um paciente e todos os seus dados (RGPD, direito ao apagamento)
-- Um só DELETE no paciente apaga, na mesma transação, as consultas (com as notas) e os briefings.
-- Ou fica tudo apagado, ou nada.
--
-- Continua sem haver DELETE direto de consultas nem de briefings: só se apagam com o paciente.
-- As chaves estrangeiras apagam em cascata mesmo sem DELETE nessas tabelas (são ações da própria
-- base de dados). Como as chaves incluem o psicologo_id, só apagam linhas do mesmo psicólogo.

-- 1. Consultas e briefings apagados com o paciente -----------------------------------------------------
alter table public.consultas
  drop constraint consultas_paciente_do_psicologo,
  add constraint consultas_paciente_do_psicologo
    foreign key (paciente_id, psicologo_id) references public.pacientes (id, psicologo_id)
    on delete cascade;

alter table public.briefings
  drop constraint briefings_consulta_do_psicologo,
  add constraint briefings_consulta_do_psicologo
    foreign key (consulta_id, psicologo_id) references public.consultas (id, psicologo_id)
    on delete cascade;

-- 2. O psicólogo pode apagar os SEUS pacientes ---------------------------------------------------------
grant delete on table public.pacientes to authenticated;

create policy "Psicólogo apaga os seus pacientes"
on public.pacientes for delete
to authenticated
using ((select auth.uid()) = psicologo_id);

comment on column public.pacientes.ativo is
  'false = arquivado. Apagar definitivamente (RGPD) apaga também as consultas, notas e briefings.';
comment on column public.consultas.estado is
  'agendada | realizada | cancelada | faltou. Não há DELETE direto: cancela-se. Só se apaga com o paciente.';
