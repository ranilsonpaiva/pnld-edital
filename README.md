# PNLD Edital

Sistema para ler editais PNLD (PDF), extrair critérios e validá-los com supervisão humana (HITL), gerando checklist e feedback para melhorar a extração.

## Status do MVP

- Interface web de revisão HITL (sem login por enquanto)
- Filas iniciais: Anexo 01 §§3–4 (Anos Iniciais 2027 e Anos Finais 2028–2031)
- Extrator Python de seções / itens / alíneas
- Autenticação **prevista** via `AuthProvider` + `VITE_AUTH_ENABLED` (desligada)

## Estrutura

```
apps/web                 # Interface HITL (Vite + React)
services/extractor       # Extração Anexo 01 (Python)
data/extractions          # Saídas JSON/TSV de exemplo
```

## Rodar a interface web

```bash
cd apps/web
cp ../../.env.example .env   # opcional
npm install
npm run dev
```

Abre em http://localhost:5174

### Atalhos HITL

| Tecla | Ação |
|---|---|
| `A` | Aprovar |
| `E` | Focar edição |
| `⌘/Ctrl+Enter` | Salvar edição |
| `R` | Rejeitar |
| `J` / `K` | Próximo / anterior |

Revisões ficam em `localStorage` e podem ser exportadas em JSON pela UI.

## Extrator

```bash
cd services/extractor
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# ajuste paths dos PDFs no script ou passe corpus local
python extract_anexo01.py
```

Fonte canônica dos editais: [Consultas Editais FNDE](https://www.gov.br/fnde/pt-br/acesso-a-informacao/acoes-e-programas/programas/programas-do-livro/consultas-editais/editais)

## Autenticação (previsão)

Hoje o acesso é aberto. A base já existe em `apps/web/src/auth/`:

1. `VITE_AUTH_ENABLED=false` (padrão) → UI liberada, badge “acesso aberto”
2. `VITE_AUTH_ENABLED=true` → `RequireAuth` exige usuário; stub de login dev disponível
3. Próximo passo: trocar `signInDev` por provedor real (ex.: OIDC, Auth.js, Clerk) e persistir `ReviewEvent` no backend com `reviewer_id`

## Roadmap curto

1. Viewer PDF com highlight do `page_start`
2. API + Postgres para reviews (em vez de só localStorage)
3. Ligar auth e papéis `reviewer` / `admin`
4. Loop de aprendizado (RAG com pares before→after)

## Licença

Uso interno / a definir.
