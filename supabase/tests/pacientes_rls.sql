-- Teste das regras RLS da tabela "pacientes" (passo 2).
--
-- Como correr: Supabase → SQL Editor → New query → colar este ficheiro todo → Run.
-- Resultado esperado: uma linha "OK — todos os testes RLS passaram (nada ficou gravado)".
-- Se alguma regra estiver errada, pára com um erro que começa por "FALHOU:".
--
-- Não grava nada: cria dois psicólogos fictícios dentro de uma transação e no fim desfaz tudo.

begin;

insert into auth.users (id, email) values
  ('00000000-0000-4000-8000-00000000000a', 'teste-rls-a@example.com'),
  ('00000000-0000-4000-8000-00000000000b', 'teste-rls-b@example.com');

set local role authenticated;

-- Psicóloga A cria um paciente
select set_config('request.jwt.claims',
  '{"sub":"00000000-0000-4000-8000-00000000000a","role":"authenticated"}', true);
insert into public.pacientes (nome) values ('Paciente fictício da A');

do $$
begin
  if (select psicologo_id from public.pacientes where nome = 'Paciente fictício da A')
     is distinct from '00000000-0000-4000-8000-00000000000a' then
    raise exception 'FALHOU: o paciente não ficou associado à psicóloga que o criou';
  end if;
end $$;

-- Psicólogo B cria um paciente
select set_config('request.jwt.claims',
  '{"sub":"00000000-0000-4000-8000-00000000000b","role":"authenticated"}', true);
insert into public.pacientes (nome) values ('Paciente fictício do B');

-- 1. B só vê os seus pacientes
do $$
begin
  if (select count(*) from public.pacientes) <> 1 then
    raise exception 'FALHOU: o B vê pacientes que não são dele';
  end if;
  if exists (select 1 from public.pacientes where nome = 'Paciente fictício da A') then
    raise exception 'FALHOU: o B vê o paciente da A';
  end if;
end $$;

-- 2. B não consegue alterar o paciente da A (a alteração não encontra linhas)
do $$
declare
  n int;
begin
  update public.pacientes set nome = 'Alterado pelo B' where nome = 'Paciente fictício da A';
  get diagnostics n = row_count;
  if n <> 0 then
    raise exception 'FALHOU: o B alterou o paciente da A';
  end if;
end $$;

-- 3. B não consegue criar um paciente em nome da A
do $$
begin
  begin
    insert into public.pacientes (nome, psicologo_id)
    values ('Intruso', '00000000-0000-4000-8000-00000000000a');
    raise exception 'FALHOU: o B criou um paciente em nome da A';
  exception when insufficient_privilege then
    null; -- esperado: a coluna psicologo_id não pode ser escolhida
  end;
end $$;

-- 4. B não consegue passar o seu paciente para a A
do $$
begin
  begin
    update public.pacientes set psicologo_id = '00000000-0000-4000-8000-00000000000a';
    raise exception 'FALHOU: o B mudou o dono de um paciente';
  exception when insufficient_privilege then
    null; -- esperado
  end;
end $$;

-- 5. Apagar só apaga os pacientes do próprio psicólogo (passo 7; o teste completo, com as
--    consultas e os briefings, está em apagar_paciente_rls.sql)
do $$
declare
  antes int;
begin
  select count(*) into antes from public.pacientes;
  delete from public.pacientes where false; -- tem permissão, mesmo sem apagar nada
  if (select count(*) from public.pacientes) <> antes then
    raise exception 'FALHOU: o DELETE mexeu em pacientes';
  end if;
end $$;

-- 6. B consegue alterar e arquivar o seu paciente
do $$
declare
  n int;
begin
  update public.pacientes set nome = 'Paciente fictício do B (alterado)', ativo = false
  where nome = 'Paciente fictício do B';
  get diagnostics n = row_count;
  if n <> 1 then
    raise exception 'FALHOU: o B não conseguiu alterar o seu próprio paciente';
  end if;
end $$;

-- 7. Sem sessão (anon) não se vê nada
set local role anon;
do $$
begin
  begin
    perform 1 from public.pacientes;
    raise exception 'FALHOU: um visitante sem sessão consegue ler pacientes';
  exception when insufficient_privilege then
    null; -- esperado
  end;
end $$;

rollback;

select 'OK — todos os testes RLS passaram (nada ficou gravado)' as resultado;
