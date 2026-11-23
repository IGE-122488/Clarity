import os

# Valores fictícios para os testes: nunca chaves reais.
os.environ.setdefault("SUPABASE_URL", "https://exemplo.supabase.co")
os.environ.setdefault("SUPABASE_PUBLISHABLE_KEY", "sb_publishable_teste")
os.environ.setdefault("APP_ENV", "development")

# A IA nunca é chamada a sério nos testes (sem custos nem dados a sair do PC).
for _variavel in ("AZURE_OPENAI_BASE_URL", "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_DEPLOYMENT"):
    os.environ.pop(_variavel, None)
