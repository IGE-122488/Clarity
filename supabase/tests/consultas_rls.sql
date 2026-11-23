-- Teste das regras da tabela "consultas" (passo 3 — agenda).
--
-- Como correr: Supabase → SQL Editor → New query → colar este ficheiro todo → Run.
-- Resultado esperado: uma linha "OK — todos os testes das consultas passaram (nada ficou gravado)".
-- Se alguma regra estiver errada, pára com um erro que começa por "FALHOU:".
--
-- Não grava nada: cria dois psicólogos fictícios dentro de uma transação e no fim desfaz tudo.

begin;

insert into auth.users (id, email) values
  ('00000000-0000-4000-8000-00000000000a', 'teste-rls-a@example.com'),
  ('00000000-0000-4000-8000-00000000000b', 'teste-rls-b@example.com');

set local role authenticated;

-- A cria um paciente e uma consulta
select set_config('request.jwt.claims',
  '{"sub":"00000000-0000-4000-8000-00000000000a","role":"authenticated"}', true);
insert into public.pacientes (nome) values ('Paciente fictício da A');
-- guarda o id do paciente da A para o usar mais abaixo como o B
select set_config('teste.paciente_a',
  (select id::text from public.pacientes where nome = 'Paciente fictício da A'), true);
insert into public.consultas (paciente_id, inicio, fim, notas)
  values (current_setting('teste.paciente_a')::uuid,
          '2030-01-07 10:00+00', '2030-01-07 10:50+00', 'Notas fictícias da A');

-- B cria um paciente e uma consulta
select set_config('request.jwt.claims',
  '{"sub":"00000000-0000-4000-8000-00000000000b","role":"authenticated"}', true);
insert into public.pacientes (nome) values ('Paciente fictício do B');
select set_config('teste.paciente_b',
  (select id::text from public.pacientes where nome = 'Paciente fictício do B'), true);
insert into public.consultas (paciente_id, inicio, fim)
  values (current_setting('teste.paciente_b')::uuid, '2030-01-07 11:00+00', '2030-01-07 11:50+00');

-- 1. B só vê as suas consultas (e não vê as notas da A)
do $$
begin
  if (select count(*) from public.consultas) <> 1 then
    raise exception 'FALHOU: o B vê consultas que não são dele';
  end if;
  if exists (select 1 from public.consultas where notas = 'Notas fictícias da A') then
    raise exception 'FALHOU: o B vê as notas da A';
  end if;
end $$;

-- 2. B não consegue marcar uma consulta para o paciente da A
do $$
begin
  begin
    insert into public.consultas (paciente_id, inicio, fim)
    values (current_setting('teste.paciente_a')::uuid, '2030-01-08 10:00+00', '2030-01-08 10:50+00');
    raise exception 'FALHOU: o B marcou uma consulta para o paciente da A';
  exception when foreign_key_violation or insufficient_privilege then
    null; -- esperado
  end;
end $$;

-- 3. B não consegue alterar as consultas da A (a alteração não encontra linhas)
do $$
declare
  n int;
begin
  update public.consultas set notas = 'Escrito pelo B' where notas = 'Notas fictícias da A';
  get diagnostics n = row_count;
  if n <> 0 then
    raise exception 'FALHOU: o B alterou uma consulta da A';
  end if;
end $$;

-- 4. B não consegue mudar o paciente nem o dono de uma consulta
do $$
begin
  begin
    update public.consultas set paciente_id = current_setting('teste.paciente_a')::uuid;
    raise exception 'FALHOU: o B mudou o paciente de uma consulta';
  exception when insufficient_privilege or foreign_key_violation then
    null; -- esperado
  end;
  begin
    update public.consultas set psicologo_id = '00000000-0000-4000-8000-00000000000a';
    raise exception 'FALHOU: o B mudou o dono de uma consulta';
  exception when insufficient_privilege then
    null; -- esperado
  end;
end $$;

-- 5. Não se apagam consultas pela app (cancela-se)
do $$
begin
  begin
    delete from public.consultas;
    raise exception 'FALHOU: foi possível apagar consultas';
  exception when insufficient_privilege then
    null; -- esperado
  end;
end $$;

-- 6. As datas têm de fazer sentido e o estado tem de ser válido
do $$
begin
  begin
    insert into public.consultas (paciente_id, inicio, fim)
    values (current_setting('teste.paciente_b')::uuid, '2030-01-09 11:00+00', '2030-01-09 10:00+00');
    raise exception 'FALHOU: aceitou uma consulta que acaba antes de começar';
  exception when check_violation then
    null; -- esperado
  end;
  begin
    update public.consultas set estado = 'inventado';
    raise exception 'FALHOU: aceitou um estado inválido';
  exception when check_violation then
    null; -- esperado
  end;
end $$;

-- 7. B consegue remarcar, escrever notas e cancelar a sua consulta
do $$
declare
  n int;
begin
  update public.consultas
     set inicio = '2030-01-07 15:00+00', fim = '2030-01-07 15:50+00',
         notas = 'Notas fictícias do B', estado = 'cancelada';
  get diagnostics n = row_count;
  if n <> 1 then
    raise exception 'FALHOU: o B não conseguiu alterar a sua própria consulta';
  end if;
end $$;

-- 8. Sem sessão (anon) não se vê nada
set local role anon;
do $$
begin
  begin
    perform 1 from public.consultas;
    raise exception 'FALHOU: um visitante sem sessão consegue ler consultas';
  exception when insufficient_privilege then
    null; -- esperado
  end;
end $$;

rollback;

select 'OK — todos os testes das consultas passaram (nada ficou gravado)' as resultado;
