#!/usr/bin/env bash
# =============================================================================
# setup.sh — Provisioning idempotente do SIGMINE Histórico PA
# Executa como usuário nathan com sudo quando necessário.
# =============================================================================
set -euo pipefail

PROJECT_DIR="/home/nathan/sigmine-historico-pa"
VENV_DIR="$PROJECT_DIR/venv"
LOG_DIR="$PROJECT_DIR/logs"
DATA_DIR="$PROJECT_DIR/data/raw"
ENV_FILE="$PROJECT_DIR/.env"
DB_NAME="sigmine_pa"
DB_USER="sigmine_user"
SERVICE_NAME="sigmine"

echo "======================================================"
echo "  SIGMINE Histórico PA — Provisionamento Automático"
echo "======================================================"

# --- 1. Dependências do sistema ---
echo "[1/9] Instalando dependências do sistema…"
sudo apt-get update -qq
sudo apt-get install -y --no-install-recommends \
    python3-venv \
    python3-dev \
    libpq-dev \
    gdal-bin \
    libgdal-dev \
    python3-gdal \
    build-essential \
    git \
    curl \
    nginx \
    postgis \
    postgresql-18-postgis-3 \
    > /dev/null 2>&1 || true

echo "  ✓ Dependências do sistema instaladas"

# --- 2. Verificar PostgreSQL ---
echo "[2/9] Verificando PostgreSQL…"
if ! systemctl is-active --quiet postgresql; then
    sudo systemctl start postgresql
    sudo systemctl enable postgresql
fi
echo "  ✓ PostgreSQL ativo"

# --- 3. Criar banco e usuário dedicado ---
echo "[3/9] Criando banco de dados '$DB_NAME'…"
# Gera senha aleatória se .env não existir ainda
DB_PASS="sigmine_$(openssl rand -hex 12)"

sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASS';"

sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"

sudo -u postgres psql -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS postgis;" > /dev/null 2>&1 || true
sudo -u postgres psql -d "$DB_NAME" -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;" > /dev/null 2>&1
sudo -u postgres psql -d "$DB_NAME" -c "GRANT ALL ON SCHEMA public TO $DB_USER;" > /dev/null 2>&1

echo "  ✓ Banco '$DB_NAME' configurado"

# --- 4. Criar .env se não existir ---
echo "[4/9] Configurando arquivo .env…"
if [ ! -f "$ENV_FILE" ]; then
    SECRET_KEY=$(openssl rand -hex 32)
    cat > "$ENV_FILE" <<EOF
# SIGMINE Histórico PA — Variáveis de Ambiente (gerado por setup.sh)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=$DB_NAME
DB_USER=$DB_USER
DB_PASSWORD=$DB_PASS
FLASK_ENV=production
FLASK_SECRET_KEY=$SECRET_KEY
FLASK_HOST=0.0.0.0
FLASK_PORT=8001
ANM_PA_URL=https://dadosabertos.anm.gov.br/SIGMINE/PROCESSOS_MINERARIOS/PA.zip
DATA_RAW_DIR=$PROJECT_DIR/data/raw
LOG_DIR=$PROJECT_DIR/logs
GUNICORN_WORKERS=4
GUNICORN_BIND=0.0.0.0:8001
EOF
    echo "  ✓ .env criado com credenciais geradas automaticamente"
else
    echo "  ✓ .env já existe, mantendo configurações atuais"
fi

# --- 5. Virtualenv e dependências Python ---
echo "[5/9] Configurando virtualenv e dependências Python…"
mkdir -p "$LOG_DIR" "$DATA_DIR"

if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi

"$VENV_DIR/bin/pip" install --upgrade pip --quiet
"$VENV_DIR/bin/pip" install -r "$PROJECT_DIR/requirements.txt" --quiet

# flask-sqlalchemy separado (não está em requirements para compatibilidade)
"$VENV_DIR/bin/pip" install flask-sqlalchemy --quiet
echo "  ✓ Virtualenv configurado"

# --- 6. Inicializar banco de dados (DDL) ---
echo "[6/9] Executando DDL do banco…"
# Lê senha do .env
source <(grep -v '^#' "$ENV_FILE" | grep '=')
PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
    -f "$PROJECT_DIR/sql/init_db.sql" > /dev/null 2>&1 || true
echo "  ✓ Schema do banco criado/atualizado"

# --- 7. Configurar Nginx ---
echo "[7/9] Configurando Nginx…"
sudo cp "$PROJECT_DIR/deploy/nginx_sigmine.conf" /etc/nginx/sites-available/sigmine
sudo ln -sf /etc/nginx/sites-available/sigmine /etc/nginx/sites-enabled/sigmine
sudo nginx -t && sudo systemctl reload nginx
echo "  ✓ Nginx configurado (porta 8085)"

# --- 8. Configurar serviço systemd ---
echo "[8/9] Configurando serviço systemd…"
sudo cp "$PROJECT_DIR/deploy/sigmine.service" /etc/systemd/system/sigmine.service
sudo systemctl daemon-reload
sudo systemctl enable sigmine
sudo systemctl restart sigmine
echo "  ✓ Serviço sigmine.service ativo"

# --- 9. Configurar cron diário ---
echo "[9/9] Configurando cron ETL diário (03:00)…"
CRON_CMD="0 3 * * * $VENV_DIR/bin/python $PROJECT_DIR/scripts/run_etl.py >> $LOG_DIR/etl.log 2>&1"
(crontab -l 2>/dev/null | grep -v "run_etl.py"; echo "$CRON_CMD") | crontab -
echo "  ✓ Cron configurado"

echo ""
echo "======================================================"
echo "  Provisionamento concluído com sucesso!"
echo "  App: http://$(hostname -I | awk '{print $1}'):8085"
echo "  API: http://$(hostname -I | awk '{print $1}'):8001/api/status"
echo ""
echo "  Para executar o ETL agora:"
echo "  $VENV_DIR/bin/python $PROJECT_DIR/scripts/run_etl.py"
echo "======================================================"
