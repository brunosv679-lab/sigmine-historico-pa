# SIGMINE Histórico PA

> Sistema de monitoramento histórico dos processos minerários do **Pará (PA)** com dados reais da **ANM** (Agência Nacional de Mineração), stack geoespacial PostGIS e interface web interativa.

---

## 📐 Arquitetura MVC

```
sigmine-historico-pa/
├── app/
│   ├── models/        ← Consultas SQL/GeoSQL (bindparams, anti-SQLi)
│   ├── services/      ← ETL: download, limpeza espacial, detecção de mudanças
│   ├── controllers/   ← Blueprints Flask (web + API REST/GeoJSON)
│   └── views/         ← Templates Jinja2 + Leaflet + Chart.js
├── sql/               ← DDL PostGIS (staging, atual, histórico SCD2, auditoria)
├── deploy/            ← Nginx + systemd/Gunicorn
└── scripts/           ← CLI ETL agendável no cron
```

## 🗄️ Modelo de Dados

| Tabela | Função |
|---|---|
| `processos_staging` | Dados brutos do shapefile ANM |
| `processos_atual` | Snapshot vigente dos processos |
| `processos_historico` | **SCD Tipo 2**: linha do tempo de cada mudança |
| `etl_execucoes` | Auditoria de cada execução do pipeline |

**Tipos de mudança detectados:** `NOVO`, `FASE`, `TITULAR`, `GEOMETRIA`, `REMOVIDO`

## 🚀 Instalação Rápida

```bash
# 1. Clonar e entrar no projeto
cd /home/nathan/sigmine-historico-pa

# 2. Provisionar tudo (idempotente)
bash setup.sh

# 3. Executar ETL manual (1ª carga)
venv/bin/python scripts/run_etl.py

# 4. Backfill demo (opcional, para histórico sintético)
venv/bin/python scripts/run_etl.py --backfill-demo
```

## ⚙️ Configuração

Copie `.env.example` → `.env` e preencha:
```bash
cp .env.example .env
# Edite .env com suas credenciais reais
```

## 🌐 Endpoints

| Endpoint | Descrição |
|---|---|
| `GET /` | Mapa Leaflet interativo com filtros e linha do tempo |
| `GET /dinamica` | Gráficos Chart.js e mapa de dinâmica |
| `GET /api/processos?bbox=...` | GeoJSON paginado por bbox |
| `GET /api/historico/<processo>` | Linha do tempo SCD2 de um processo |
| `GET /api/dinamica?tipo=NOVO` | Geometrias por tipo de mudança |
| `GET /api/stats/novos-por-mes` | Agregado mensal |
| `GET /api/stats/por-substancia` | Ranking de substâncias |
| `GET /api/stats/mudancas` | Contagem por tipo de mudança |
| `GET /api/status` | Status da API |
| `GET /health` | Health check |

## 🔒 Segurança

- Credenciais em `.env` (ignorado no git) — nunca hardcoded
- Todas as consultas SQL usam **bindparams** (prevenção de SQL Injection)
- `.gitignore` exclui `.env`, `venv/`, dados brutos e logs

## 📅 ETL Automatizado

O cron executa diariamente às 03:00:
```
0 3 * * * /home/nathan/sigmine-historico-pa/venv/bin/python \
    /home/nathan/sigmine-historico-pa/scripts/run_etl.py
```

## 🧪 Testes

```bash
venv/bin/pytest tests/ -v
```

## 📦 Stack

- **Backend:** Python 3.14 · Flask 3 · SQLAlchemy 2 · GeoAlchemy2
- **Banco:** PostgreSQL 18 · PostGIS 3
- **Geoespacial:** Fiona · Shapely · GDAL
- **Frontend:** Leaflet.js · Chart.js · Bootstrap 5 (dark)
- **Infra:** Gunicorn · Nginx · systemd · cron

## 📄 Fonte dos Dados

[ANM — SIGMINE Processos Minerários PA](https://dadosabertos.anm.gov.br/SIGMINE/PROCESSOS_MINERARIOS/PA.zip)
