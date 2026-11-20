# Supabase

Esta pasta guarda as **migrações** da base de dados (`migrations/`) e os **testes das regras RLS** (`tests/`).

## Aplicar uma migração ao projeto de desenvolvimento (`clarity-dev`)

Por agora, sem CLI:

1. Supabase → projeto `clarity-dev` → **SQL Editor** → **New query**.
2. Colar o ficheiro de `migrations/` todo → **Run**. Tem de dar `Success. No rows returned`.
3. Correr o teste correspondente de `tests/` (ver abaixo).

Cada migração corre **uma só vez** por projeto. Correr outra vez dá erro (`already exists`), o que é normal.

| Migração | O que faz |
| --- | --- |
| `20261120180000_pacientes.sql` | Tabela `pacientes`, permissões e regras RLS (cada psicólogo só vê os seus) |

## Testar as regras RLS

SQL Editor → New query → colar `tests/pacientes_rls.sql` → **Run**.

- Tem de aparecer `OK — todos os testes RLS passaram (nada ficou gravado)`.
- Se aparecer um erro que começa por `FALHOU:`, a regra correspondente está errada. Não avançar.
- O teste não grava nada: cria dois psicólogos fictícios dentro de uma transação e desfaz tudo no fim.

## Regras

- Todas as alterações à base de dados entram por **migração** neste repositório. Nada de criar tabelas à mão no dashboard sem ficar aqui registado.
- **RLS ativo em todas as tabelas** do schema `public`, com políticas `TO authenticated` + condição de dono (`(select auth.uid()) = psicologo_id`).
- Permissões mínimas, coluna a coluna (o projeto tem a concessão automática desligada).
- A chave **secret / service_role** nunca vai para o frontend nem para o repositório.
- **Apenas dados fictícios** até haver DPIA aprovada.

## Mais tarde: CLI da Supabase

Quando houver mais do que um ambiente (desenvolvimento e produção), passar a aplicar as migrações com a CLI:

```bash
npx supabase init
npx supabase login              # com um token de permissões limitadas
npx supabase link --project-ref <ref-do-projeto>
npx supabase db push
```
