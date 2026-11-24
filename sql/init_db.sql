-- =============================================================================
-- SIGMINE Histórico PA — DDL inicial PostGIS
-- Executar com: psql -U sigmine_user -d sigmine_pa -f sql/init_db.sql
-- =============================================================================

-- Extensões
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- ---------------------------------------------------------------------------
-- Tabela de staging: dados brutos carregados do shapefile ANM
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS processos_staging (
    id               SERIAL PRIMARY KEY,
    numero_processo  VARCHAR(50)  NOT NULL,
    nome             TEXT,
    fase             TEXT,
    ult_evento       TEXT,
    ult_eve_data     DATE,
    area_ha          NUMERIC(14,4),
    substancia       TEXT,
    uso_solo         TEXT,
    tipo_requerimento TEXT,
    municipio        TEXT,
    uf               VARCHAR(50),
    id_original      TEXT,
    geom             GEOMETRY(MULTIPOLYGON, 4674),
    carregado_em     TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_staging_processo
    ON processos_staging (numero_processo);
CREATE INDEX IF NOT EXISTS idx_staging_geom
    ON processos_staging USING GIST (geom);

-- ---------------------------------------------------------------------------
-- Tabela de processos atuais (snapshot mais recente validado)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS processos_atual (
    id               SERIAL PRIMARY KEY,
    numero_processo  VARCHAR(50)  NOT NULL UNIQUE,
    nome             TEXT,
    fase             TEXT,
    ult_evento       TEXT,
    ult_eve_data     DATE,
    area_ha          NUMERIC(14,4),
    substancia       TEXT,
    uso_solo         TEXT,
    tipo_requerimento TEXT,
    municipio        TEXT,
    uf               VARCHAR(50)   DEFAULT 'PA',
    geom             GEOMETRY(MULTIPOLYGON, 4674),
    criado_em        TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    atualizado_em    TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_atual_processo
    ON processos_atual (numero_processo);
CREATE INDEX IF NOT EXISTS idx_atual_geom
    ON processos_atual USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_atual_fase
    ON processos_atual (fase);
CREATE INDEX IF NOT EXISTS idx_atual_substancia
    ON processos_atual (substancia);

-- ---------------------------------------------------------------------------
-- Tabela histórica SCD Tipo 2 (Slowly Changing Dimension)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS processos_historico (
    id               BIGSERIAL PRIMARY KEY,
    numero_processo  VARCHAR(50)  NOT NULL,
    nome             TEXT,
    fase             TEXT,
    ult_evento       TEXT,
    ult_eve_data     DATE,
    area_ha          NUMERIC(14,4),
    substancia       TEXT,
    uso_solo         TEXT,
    tipo_requerimento TEXT,
    municipio        TEXT,
    uf               VARCHAR(50)   DEFAULT 'PA',
    geom             GEOMETRY(MULTIPOLYGON, 4674),
    -- Metadados SCD2
    tipo_mudanca     VARCHAR(50)  NOT NULL,  -- NOVO, FASE, TITULAR, GEOMETRIA, REMOVIDO
    valido_de        TIMESTAMP WITH TIME ZONE NOT NULL,
    valido_ate       TIMESTAMP WITH TIME ZONE,          -- NULL = registro atual
    etl_execucao_id  INTEGER
);

CREATE INDEX IF NOT EXISTS idx_hist_processo
    ON processos_historico (numero_processo);
CREATE INDEX IF NOT EXISTS idx_hist_geom
    ON processos_historico USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_hist_valido_de
    ON processos_historico (valido_de);
CREATE INDEX IF NOT EXISTS idx_hist_tipo_mudanca
    ON processos_historico (tipo_mudanca);
-- Índice para busca de registros vigentes
CREATE INDEX IF NOT EXISTS idx_hist_atual
    ON processos_historico (numero_processo, valido_ate)
    WHERE valido_ate IS NULL;

-- ---------------------------------------------------------------------------
-- Tabela de auditoria das execuções ETL
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS etl_execucoes (
    id               SERIAL PRIMARY KEY,
    iniciado_em      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    finalizado_em    TIMESTAMP WITH TIME ZONE,
    status           VARCHAR(20)  DEFAULT 'RUNNING',  -- RUNNING, SUCCESS, ERROR
    novos            INTEGER      DEFAULT 0,
    atualizados      INTEGER      DEFAULT 0,
    removidos        INTEGER      DEFAULT 0,
    total_staging    INTEGER      DEFAULT 0,
    mensagem         TEXT,
    erro             TEXT
);

-- ---------------------------------------------------------------------------
-- View: processos ativos com linha do tempo (última mudança)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_processos_linha_do_tempo AS
SELECT
    pa.*,
    h.tipo_mudanca  AS ultima_mudanca,
    h.valido_de     AS data_ultima_mudanca
FROM processos_atual pa
LEFT JOIN LATERAL (
    SELECT tipo_mudanca, valido_de
    FROM processos_historico
    WHERE numero_processo = pa.numero_processo
    ORDER BY valido_de DESC
    LIMIT 1
) h ON TRUE;

COMMENT ON TABLE processos_staging IS 'Dados brutos carregados do shapefile ANM antes de validação';
COMMENT ON TABLE processos_atual IS 'Snapshot atual dos processos minerários do Pará (ANM)';
COMMENT ON TABLE processos_historico IS 'Histórico SCD Tipo 2: todas as mudanças detectadas por execução ETL';
COMMENT ON TABLE etl_execucoes IS 'Auditoria e log de cada execução do pipeline ETL';
