-- Passo 9 — Consultas que passam sozinhas a "Realizada"
-- Quando a hora de fim de uma consulta "agendada" já passou, a app marca-a como "realizada" e
-- assinala-a com estado_automatico = true. O sino pede ao psicólogo que confirme ou que a mude para
-- "faltou" ou "cancelada". Ao confirmar ou mudar o estado, estado_automatico volta a false.
--
-- Não há tarefas agendadas no servidor (isso exigiria a chave secreta): a mudança é feita pela API,
-- com o token do psicólogo, quando ele tem a app aberta. O RLS continua a limitar tudo às SUAS consultas.

alter table public.consultas
  add column estado_automatico boolean not null default false,
  add constraint consultas_estado_automatico_so_realizada
    check (not estado_automatico or estado = 'realizada');

comment on column public.consultas.estado_automatico is
  'true = passou sozinha de agendada a realizada no fim da hora e o psicólogo ainda não confirmou.';

-- Só se altera (a API marca e desmarca); ao marcar uma consulta nova fica sempre false.
grant update (estado_automatico) on table public.consultas to authenticated;
