CREATE SCHEMA IF NOT EXISTS ef;

CREATE TABLE IF NOT EXISTS ef.fonte (
 arquivo VARCHAR(80) NOT NULL UNIQUE,
 sha256 CHAR(64) PRIMARY KEY CHECK (sha256 ~ '^[0-9a-f]{64}$'),
 bytes BIGINT NOT NULL CHECK (bytes>0),
 ano SMALLINT NOT NULL,
 trimestre SMALLINT NOT NULL CHECK (trimestre BETWEEN 1 AND 4)
);

CREATE TABLE IF NOT EXISTS ef.dim_uf (codigo SMALLINT PRIMARY KEY,rotulo TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS ef.dim_capital (codigo SMALLINT PRIMARY KEY,rotulo TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS ef.dim_v2007 (codigo SMALLINT PRIMARY KEY,rotulo TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS ef.dim_v2010 (codigo SMALLINT PRIMARY KEY,rotulo TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS ef.dim_v4018 (codigo SMALLINT PRIMARY KEY,rotulo TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS ef.dim_v4019 (codigo SMALLINT PRIMARY KEY,rotulo TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS ef.dim_vd3004 (codigo SMALLINT PRIMARY KEY,rotulo TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS ef.dim_vd4002 (codigo SMALLINT PRIMARY KEY,rotulo TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS ef.dim_vd4009 (codigo SMALLINT PRIMARY KEY,rotulo TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS ef.dim_vd4010 (codigo SMALLINT PRIMARY KEY,rotulo TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS ef.observacao (
 ano SMALLINT NOT NULL,
 trimestre SMALLINT NOT NULL,
 uf SMALLINT NOT NULL REFERENCES ef.dim_uf(codigo),
 capital SMALLINT REFERENCES ef.dim_capital(codigo),
 upa VARCHAR(9) NOT NULL,
 estrato VARCHAR(7) NOT NULL,
 v1008 VARCHAR(2) NOT NULL,
 v1014 VARCHAR(2) NOT NULL,
 v1016 VARCHAR(1) NOT NULL,
 v1028 NUMERIC(18,8) NOT NULL,
 v2003 VARCHAR(2) NOT NULL,
 v2007 SMALLINT NOT NULL REFERENCES ef.dim_v2007(codigo),
 v2009 SMALLINT NOT NULL,
 v2010 SMALLINT NOT NULL REFERENCES ef.dim_v2010(codigo),
 vd3004 SMALLINT NOT NULL REFERENCES ef.dim_vd3004(codigo),
 vd4002 SMALLINT NOT NULL REFERENCES ef.dim_vd4002(codigo),
 vd4009 SMALLINT NOT NULL REFERENCES ef.dim_vd4009(codigo),
 v4019 SMALLINT REFERENCES ef.dim_v4019(codigo),
 v4018 SMALLINT REFERENCES ef.dim_v4018(codigo),
 vd4010 SMALLINT NOT NULL REFERENCES ef.dim_vd4010(codigo),
 vd4016 NUMERIC(12,2),
 is_bahia BOOLEAN NOT NULL,
 is_salvador BOOLEAN NOT NULL,
 is_empreendedor BOOLEAN NOT NULL,
 is_empreendedora BOOLEAN NOT NULL,
 formalizada BOOLEAN,
 arquivo_sha256 CHAR(64) NOT NULL REFERENCES ef.fonte(sha256),
 linha_origem BIGINT NOT NULL CHECK (linha_origem>0),
 PRIMARY KEY (ano,trimestre,upa,v1008,v1014,v1016,v2003),
 UNIQUE (arquivo_sha256,linha_origem),
 CHECK (ano=2026 AND trimestre IN (1,2)),
 CONSTRAINT ck_recorte_bahia CHECK (uf=29),
 CHECK (vd4002=1),
 CHECK (v2009 BETWEEN 14 AND 130),
 CHECK (v1028>0),
 CHECK (vd4016>=0),
 CHECK (capital IS NULL OR capital=uf),
 CHECK (upa ~ '^[0-9]{9}$' AND estrato ~ '^[0-9]{7}$'),
 CHECK (left(upa,2)=uf::text),
 CHECK (v1008 ~ '^[0-9]{2}$' AND v1014 ~ '^[0-9]{2}$' AND v1016 ~ '^[1-5]$' AND v2003 ~ '^[0-9]{2}$'),
 CHECK (v1008::integer BETWEEN 1 AND 14 AND v2003::integer BETWEEN 1 AND 30),
 CHECK (is_bahia=(uf=29)),
 CHECK (is_salvador=(uf=29 AND COALESCE(capital=29,FALSE))),
 CHECK (is_empreendedor=(vd4009 IN (8,9))),
 CHECK (is_empreendedora=(v2007=2 AND vd4009 IN (8,9))),
 CHECK (formalizada IS NOT DISTINCT FROM CASE WHEN vd4009 IN (8,9) AND v4019 IN (1,2) THEN v4019=1 ELSE NULL END)
);

CREATE INDEX IF NOT EXISTS ix_observacao_recorte ON ef.observacao (ano,trimestre,uf,v2007);

CREATE INDEX IF NOT EXISTS ix_empreendedoras ON ef.observacao (ano,trimestre,uf,capital) WHERE is_empreendedora;