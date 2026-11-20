# Supabase

Esta pasta vai guardar a configuração e as **migrações** da base de dados (passo 2: tabelas, autenticação e RLS).

Ainda não tem `config.toml` de propósito: deve ser criado pela própria CLI da Supabase, para corresponder à versão que estiverem a usar.

```bash
npx supabase --version          # confirmar a versão da CLI
npx supabase init               # cria supabase/config.toml
npx supabase login              # usa um token com permissões limitadas, não o token clássico
npx supabase link --project-ref <ref-do-projeto-dev>
```

Regras:

- Todas as alterações à base de dados entram por **migração** (`npx supabase migration new <nome>`), nunca à mão no dashboard de produção.
- **RLS ativo em todas as tabelas** do schema `public`, com políticas `TO authenticated` + condição de dono (`(select auth.uid()) = psicologo_id`).
- A chave **secret / service_role** nunca vai para o frontend nem para o repositório. Só existe nas Edge Functions (como secret).
