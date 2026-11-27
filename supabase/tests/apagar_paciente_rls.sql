-- Teste das regras para apagar um paciente (passo 7 — RGPD).
--
-- Como correr: Supabase → SQL Editor → New query → colar este ficheiro todo → Run.
-- Resultado esperado: uma linha "OK — todos os testes de apagar pacientes passaram (nada ficou gravado)".
-- Se alguma regra estiver errada, pára com um erro que começa por "FALHOU:".
--
-- Não grava nada: cria dois psicólogos fictícios dentro de uma transação e no fim desfaz tudo.

begin;

insert into auth.users (id, email) values
  ('00000000-0000-4000-8000-00000000000a', 'teste-rls-a@example.com'),
  ('00000000-0000-4000-8000-00000000000b', 'teste-rls-b@example.com');

set local role authenticated;

-- A cria dois pacientes; o primeiro tem duas consultas e um briefing
select set_config('request.jwt.claims',
  '{"sub":"00000000-0000-4000-8000-00000000000a","role":"authenticated"}', true);
insert into public.pacientes (nome) values ('Paciente fictício da A'), ('Outro paciente da A');
select set_config('teste.paciente_a',
  (select id::text from public.pacientes where nome = 'Paciente fictício da A'), true);
insert into public.consultas (paciente_id, inicio, fim, estado, notas)
  values (current_setting('teste.paciente_a')::uuid, '2030-01-07 10:00+00', '2030-01-07 10:50+00',
          'realizada', 'Notas fictícias'),
         (current_setting('teste.paciente_a')::uuid, '2030-01-14 10:00+00', '2030-01-14 10:50+00',
          'agendada', null);
insert into public.consultas (paciente_id, inicio, fim)
  select id, '2030-01-08 10:00+00', '2030-01-08 10:50+00'
    from public.pacientes where nome = 'Outro paciente da A';
insert into public.briefings (consulta_id, texto, modelo, sessoes_usadas)
  select id, 'Briefing fictício da A', 'modelo-teste', 1
    from public.consultas where inicio = '2030-01-14 10:00+00';

-- B cria um paciente com uma consulta
select set_config('request.jwt.claims',
  '{"sub":"00000000-0000-4000-8000-00000000000b","role":"authenticated"}', true);
insert into public.pacientes (nome) values ('Paciente fictício do B');
insert into public.consultas (paciente_id, inicio, fim)
  select id, '2030-01-07 11:00+00', '2030-01-07 11:50+00' from public.pacientes;

-- 1. B não consegue apagar o paciente da A (o RLS esconde-o: 0 linhas apagadas)
do $$
declare apagados int;
begin
  delete from public.pacientes where id = current_setting('teste.paciente_a')::uuid;
  get diagnostics apagados = row_count;
  if apagados <> 0 then
    raise exception 'FALHOU: o B apagou um paciente da A';
  end if;
end $$;

-- 2. Ninguém apaga consultas nem briefings diretamente (só com o paciente)
do $$
begin
  begin
    delete from public.consultas;
    raise exception 'FALHOU: foi possível apagar consultas diretamente';
  exception when insufficient_privilege then
    null; -- esperado
  end;
  begin
    delete from public.briefings;
    raise exception 'FALHOU: foi possível apagar briefings diretamente';
  exception when insufficient_privilege then
    null; -- esperado
  end;
end $$;

-- 3. A apaga o seu paciente: as consultas e o briefing desse paciente desaparecem
select set_config('request.jwt.claims',
  '{"sub":"00000000-0000-4000-8000-00000000000a","role":"authenticated"}', true);
do $$
declare apagados int;
begin
  delete from public.pacientes where id = current_setting('teste.paciente_a')::uuid;
  get diagnostics apagados = row_count;
  if apagados <> 1 then
    raise exception 'FALHOU: a A não conseguiu apagar o seu paciente';
  end if;
  if exists (select 1 from public.consultas
             where paciente_id = current_setting('teste.paciente_a')::uuid) then
    raise exception 'FALHOU: ficaram consultas do paciente apagado';
  end if;
  if exists (select 1 from public.briefings) then
    raise exception 'FALHOU: ficou o briefing do paciente apagado';
  end if;
end $$;

-- 4. O outro paciente da A continua lá, com a sua consulta
do $$
begin
  if (select count(*) from public.pacientes) <> 1 or (select count(*) from public.consultas) <> 1 then
    raise exception 'FALHOU: apagar um paciente apagou dados de outro paciente da A';
  end if;
end $$;

-- 5. Os dados do B ficaram intactos
select set_config('request.jwt.claims',
  '{"sub":"00000000-0000-4000-8000-00000000000b","role":"authenticated"}', true);
do $$
begin
  if (select count(*) from public.pacientes) <> 1 or (select count(*) from public.consultas) <> 1 then
    raise exception 'FALHOU: apagar o paciente da A mexeu nos dados do B';
  end if;
end $$;

select 'OK — todos os testes de apagar pacientes passaram (nada ficou gravado)' as resultado;

rollback;
