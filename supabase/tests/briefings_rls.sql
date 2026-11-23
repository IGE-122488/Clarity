-- Teste das regras da tabela "briefings" (passo 4 — briefing pré-sessão).
--
-- Como correr: Supabase → SQL Editor → New query → colar este ficheiro todo → Run.
-- Resultado esperado: uma linha "OK — todos os testes dos briefings passaram (nada ficou gravado)".
-- Se alguma regra estiver errada, pára com um erro que começa por "FALHOU:".
--
-- Não grava nada: cria dois psicólogos fictícios dentro de uma transação e no fim desfaz tudo.

begin;

insert into auth.users (id, email) values
  ('00000000-0000-4000-8000-00000000000a', 'teste-rls-a@example.com'),
  ('00000000-0000-4000-8000-00000000000b', 'teste-rls-b@example.com');

set local role authenticated;

-- A cria um paciente, uma consulta e o briefing dessa consulta
select set_config('request.jwt.claims',
  '{"sub":"00000000-0000-4000-8000-00000000000a","role":"authenticated"}', true);
insert into public.pacientes (nome) values ('Paciente fictício da A');
insert into public.consultas (paciente_id, inicio, fim)
  select id, '2030-01-07 10:00+00', '2030-01-07 10:50+00'
    from public.pacientes where nome = 'Paciente fictício da A';
select set_config('teste.consulta_a', (select id::text from public.consultas), true);
-- segunda consulta da A, ainda sem briefing
insert into public.consultas (paciente_id, inicio, fim)
  select id, '2030-01-14 10:00+00', '2030-01-14 10:50+00'
    from public.pacientes where nome = 'Paciente fictício da A';
select set_config('teste.consulta_a_sem_briefing',
  (select id::text from public.consultas where inicio = '2030-01-14 10:00+00'), true);
insert into public.briefings (consulta_id, texto, modelo, sessoes_usadas)
  values (current_setting('teste.consulta_a')::uuid, 'Briefing fictício da A', 'modelo-teste', 2);

-- B cria um paciente e uma consulta
select set_config('request.jwt.claims',
  '{"sub":"00000000-0000-4000-8000-00000000000b","role":"authenticated"}', true);
insert into public.pacientes (nome) values ('Paciente fictício do B');
insert into public.consultas (paciente_id, inicio, fim)
  select id, '2030-01-07 11:00+00', '2030-01-07 11:50+00'
    from public.pacientes where nome = 'Paciente fictício do B';
select set_config('teste.consulta_b', (select id::text from public.consultas), true);

-- 1. B não vê o briefing da A
do $$
begin
  if exists (select 1 from public.briefings) then
    raise exception 'FALHOU: o B vê briefings que não são dele';
  end if;
end $$;

-- 2. B não consegue criar um briefing para uma consulta da A
do $$
begin
  begin
    insert into public.briefings (consulta_id, texto, modelo)
    values (current_setting('teste.consulta_a_sem_briefing')::uuid, 'Escrito pelo B', 'modelo-teste');
    raise exception 'FALHOU: o B criou um briefing para uma consulta da A';
  exception when foreign_key_violation or insufficient_privilege then
    null; -- esperado
  end;
end $$;

-- 3. B não consegue alterar o briefing da A (a alteração não encontra linhas)
do $$
declare
  n int;
begin
  update public.briefings set texto = 'Escrito pelo B', revisto = true;
  get diagnostics n = row_count;
  if n <> 0 then
    raise exception 'FALHOU: o B alterou o briefing da A';
  end if;
end $$;

-- 4. B cria o briefing da sua consulta, mas só um por consulta
insert into public.briefings (consulta_id, texto, modelo)
  values (current_setting('teste.consulta_b')::uuid, 'Briefing fictício do B', 'modelo-teste');
do $$
begin
  begin
    insert into public.briefings (consulta_id, texto, modelo)
    values (current_setting('teste.consulta_b')::uuid, 'Segundo briefing', 'modelo-teste');
    raise exception 'FALHOU: aceitou dois briefings para a mesma consulta';
  exception when unique_violation then
    null; -- esperado
  end;
end $$;

-- 5. B não consegue mudar a consulta nem o dono de um briefing, nem marcá-lo revisto ao criar
do $$
begin
  begin
    update public.briefings set consulta_id = current_setting('teste.consulta_a')::uuid;
    raise exception 'FALHOU: o B mudou a consulta de um briefing';
  exception when insufficient_privilege then
    null; -- esperado
  end;
  begin
    update public.briefings set psicologo_id = '00000000-0000-4000-8000-00000000000a';
    raise exception 'FALHOU: o B mudou o dono de um briefing';
  exception when insufficient_privilege then
    null; -- esperado
  end;
  begin
    insert into public.briefings (consulta_id, texto, modelo, revisto)
    values (current_setting('teste.consulta_b')::uuid, 'x', 'modelo-teste', true);
    raise exception 'FALHOU: foi possível criar um briefing já marcado como revisto';
  exception when insufficient_privilege then
    null; -- esperado
  end;
end $$;

-- 6. O texto não pode ficar vazio
do $$
begin
  begin
    update public.briefings set texto = '';
    raise exception 'FALHOU: aceitou um briefing sem texto';
  exception when check_violation then
    null; -- esperado
  end;
end $$;

-- 7. B consegue editar, marcar como revisto e gerar de novo o seu briefing
do $$
declare
  n int;
begin
  update public.briefings
     set texto = 'Briefing editado pelo B', revisto = true,
         modelo = 'modelo-teste-2', sessoes_usadas = 3, gerado_em = now();
  get diagnostics n = row_count;
  if n <> 1 then
    raise exception 'FALHOU: o B não conseguiu alterar o seu próprio briefing';
  end if;
end $$;

-- 8. Não se apagam briefings pela app
do $$
begin
  begin
    delete from public.briefings;
    raise exception 'FALHOU: foi possível apagar briefings';
  exception when insufficient_privilege then
    null; -- esperado
  end;
end $$;

-- 9. Sem sessão (anon) não se vê nada
set local role anon;
do $$
begin
  begin
    perform 1 from public.briefings;
    raise exception 'FALHOU: um visitante sem sessão consegue ler briefings';
  exception when insufficient_privilege then
    null; -- esperado
  end;
end $$;

rollback;

select 'OK — todos os testes dos briefings passaram (nada ficou gravado)' as resultado;
