-- Teste das regras do estado automático das consultas (passo 9).
--
-- Como correr: Supabase → SQL Editor → New query → colar este ficheiro todo → Run.
-- Resultado esperado: uma linha "OK — todos os testes do estado automático passaram (nada ficou gravado)".
-- Se alguma regra estiver errada, pára com um erro que começa por "FALHOU:".
--
-- Não grava nada: cria dois psicólogos fictícios dentro de uma transação e no fim desfaz tudo.

begin;

insert into auth.users (id, email) values
  ('00000000-0000-4000-8000-00000000000a', 'teste-rls-a@example.com'),
  ('00000000-0000-4000-8000-00000000000b', 'teste-rls-b@example.com');

set local role authenticated;

-- A tem uma consulta já terminada, ainda "agendada"
select set_config('request.jwt.claims',
  '{"sub":"00000000-0000-4000-8000-00000000000a","role":"authenticated"}', true);
insert into public.pacientes (nome) values ('Paciente fictício da A');
insert into public.consultas (paciente_id, inicio, fim)
  select id, now() - interval '2 hours', now() - interval '1 hour' from public.pacientes;

-- 1. Uma consulta nova começa sempre sem estado automático
do $$
begin
  if (select estado_automatico from public.consultas) then
    raise exception 'FALHOU: consulta nova com estado_automatico = true';
  end if;
  begin
    insert into public.consultas (paciente_id, inicio, fim, estado_automatico)
      select id, now() + interval '1 day', now() + interval '1 day 50 minutes', true from public.pacientes;
    raise exception 'FALHOU: foi possível marcar uma consulta já com estado_automatico';
  exception when insufficient_privilege then
    null; -- esperado
  end;
end $$;

-- 2. Passar a "realizada" automaticamente funciona; "faltou" com estado_automatico é recusado
update public.consultas set estado = 'realizada', estado_automatico = true;
do $$
begin
  begin
    update public.consultas set estado = 'faltou';
    raise exception 'FALHOU: estado_automatico ficou true numa consulta "faltou"';
  exception when check_violation then
    null; -- esperado
  end;
end $$;

-- 3. O B não vê nem altera a consulta da A
select set_config('request.jwt.claims',
  '{"sub":"00000000-0000-4000-8000-00000000000b","role":"authenticated"}', true);
do $$
declare alteradas int;
begin
  update public.consultas set estado_automatico = false;
  get diagnostics alteradas = row_count;
  if alteradas <> 0 then
    raise exception 'FALHOU: o B alterou uma consulta da A';
  end if;
end $$;

-- 4. A confirma: estado_automatico volta a false
select set_config('request.jwt.claims',
  '{"sub":"00000000-0000-4000-8000-00000000000a","role":"authenticated"}', true);
update public.consultas set estado = 'realizada', estado_automatico = false;
do $$
begin
  if (select estado_automatico from public.consultas) then
    raise exception 'FALHOU: a confirmação não ficou registada';
  end if;
end $$;

select 'OK — todos os testes do estado automático passaram (nada ficou gravado)' as resultado;

rollback;
