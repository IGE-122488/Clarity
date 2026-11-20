## O que muda

<!-- Descrição curta e a tarefa do Jira a que corresponde -->

## Como testar

<!-- Passos para quem faz a revisão -->

## Checklist

- [ ] Só usei **dados fictícios** (nenhuma nota ou nome real de pacientes)
- [ ] Nenhuma chave secreta no código nem em ficheiros `.env` com commit
- [ ] API: `ruff check .`, `ruff format --check .` e `pytest` passam
- [ ] Frontend: `npm run lint` e `npm run build` passam
- [ ] Sem `print()` / `console.log` com dados de pacientes
- [ ] Se mexe na base de dados: tem migração e regras RLS testadas
