# Clarity — web app

Web app do projeto Clarity (CVPBT Grupo 13 / GPTSI Grupo 17, ISCTE): importa as notas do psicólogo, propõe resumos de sessão que o psicólogo valida e prepara um briefing antes de cada consulta.

> **Regra do projeto:** até existir a avaliação de impacto (RGPD), **só se usam dados fictícios**. Nenhuma nota real de pacientes entra nesta app, nem em desenvolvimento nem em pré-visualizações.

## Arquitetura

```
Browser ──► frontend/ (React, JavaScript)  ── só ecrãs e login
              │  login ──► Supabase Auth
              │  tudo o resto ──► /api/...  (com o token do psicólogo)
              ▼
            api/ (FastAPI, Python) ── toda a lógica: pacientes, notas, OCR, IA, briefing
              │  usa o token do psicólogo ──► Supabase (PostgreSQL com RLS, Storage) na UE
              └► Azure AI (OCR e resumos) · Brevo (avisos por email, sem dados clínicos)
```

| Pasta | Linguagem | O que tem |
|---|---|---|
| `frontend/` | JavaScript (React + Vite) | Ecrãs e login. Não tem regras de negócio. |
| `api/` | Python 3.12 (FastAPI) | Toda a lógica e todas as chamadas a serviços externos. |
| `supabase/` | SQL | Migrações da base de dados e regras RLS (passo 2). |

Os dois são publicados **no mesmo projeto Vercel** (ver `vercel.json`): `/api/...` vai para o Python, o resto vai para o React.

**Porque é que a API usa o token do psicólogo e não uma chave de administrador?** Para que as regras RLS da base de dados continuem a proteger os dados mesmo que haja um erro no código Python: cada psicólogo só vê os seus pacientes.

## Desenvolvimento local (dois terminais no VS Code)

Requisitos: **Python 3.12** e **Node 22**.

**Terminal 1 — API (Python):**

```powershell
cd api
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
copy .env.example .env            # macOS/Linux: cp .env.example .env  → preencher
uvicorn app.main:app --reload --port 8000 --env-file .env
```

Documentação interativa da API: <http://localhost:8000/api/docs>

Testar a ligação à IA do briefing (passo 4), com o `api/.env` preenchido: `python scripts/testar_ia.py`

Testar o OCR (passo 5) com uma fotografia de notas fictícias: `python scripts/testar_ocr.py caminho\para\foto.jpg`

> Se o PowerShell bloquear o `activate`, corram uma vez `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` e tentem de novo.

**Terminal 2 — Frontend (React):**

```powershell
cd frontend
npm install
copy .env.example .env.local      # preencher
npm run dev                       # http://localhost:5173
```

Façam commit do `frontend/package-lock.json` gerado pelo `npm install`: o CI precisa dele.

Em desenvolvimento, o Vite reencaminha `/api/...` para a API na porta 8000.

A página **/estado** mostra se a API em Python responde e se a ligação ao Supabase funciona. Depois de iniciar sessão com uma conta de teste, o botão "Testar a minha sessão" confirma o caminho completo: React → Supabase Auth → API em Python.

## Testes e verificações

| Onde | Comando |
|---|---|
| `api/` | `ruff check .` · `ruff format .` · `pytest` |
| `frontend/` | `npm run lint` · `npm run build` |

O CI (GitHub Actions) corre tudo isto em cada pull request.

## Ambientes

| Ambiente | Onde | Supabase | Dados |
|---|---|---|---|
| Desenvolvimento | computador de cada um | **clarity-dev** | fictícios |
| Pré-visualização | Vercel, um link por pull request | **clarity-dev** | fictícios |
| Produção | Vercel, ramo `main` | **clarity-prod** | fictícios até à avaliação de impacto |

## Configuração inicial (uma vez)

1. **GitHub:** push deste código para `main`. Proteger o ramo `main`: pull request obrigatório, 1 aprovação, checks do CI a passar.
2. **Supabase:** criar `clarity-dev` e `clarity-prod` numa **região da UE**. Copiar o *Project URL* e a *Publishable key* de cada um. Criar 1–2 contas de teste com emails fictícios em *Authentication → Users*.
3. **Vercel:** *Add New → Project* → importar o repositório. O `vercel.json` define os dois serviços (frontend e api).
   - *Settings → Environment Variables*:
     - **Production:** `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY` do `clarity-prod`; `APP_ENV=production`; `VITE_APP_ENV=production`.
     - **Preview:** as mesmas variáveis com os valores do `clarity-dev`; `APP_ENV=preview`; `VITE_APP_ENV=preview`.
   - *Settings → Functions → Region:* escolher **Frankfurt (fra1)**, para a API em Python correr na UE, junto do Supabase.
   - Ativar *Deployment Protection* nas pré-visualizações.
4. **Supabase Auth:** em *Authentication → URL Configuration*, pôr o domínio da Vercel como *Site URL* e acrescentar `http://localhost:5173` às *Redirect URLs*.

## Como trabalhamos

- Um ramo por tarefa: `feat/importar-notas`, `fix/briefing-hora`.
- Pull request para `main`, com o template preenchido e revisão de 1 colega.
- O CI tem de passar antes do merge; cada pull request gera um link de pré-visualização na Vercel.

## Segurança desde o primeiro dia

- A chave **publishable** pode estar no browser; a proteção vem das regras **RLS**. A chave **secret / service_role** nunca entra no frontend nem no repositório.
- A API recusa pedidos sem sessão válida (`401 É necessário iniciar sessão.`) e nunca guarda respostas em cache (`Cache-Control: no-store`).
- `print()` e `console.log` estão proibidos pelo lint, para que nenhum dado de paciente vá parar aos logs.
- A documentação interativa da API (`/api/docs`) é desligada em produção.
- Permissões do browser: câmara permitida (fotografar notas); microfone bloqueado no MVP (a gravação só entra no produto final).
