"""Inventário do esquema e validação da carga no PostgreSQL configurado."""
import json,os
from pathlib import Path
from datetime import datetime,timezone
import psycopg

root=Path(__file__).resolve().parents[1]
audit=json.loads((root/'dados/auditoria.json').read_text(encoding='utf-8'))
params=json.loads((root/'config/postgres.local.json').read_text(encoding='utf-8'))
conn=psycopg.connect(os.environ['PGCONNECTION']) if os.environ.get('PGCONNECTION') else psycopg.connect(**params)
with conn,conn.cursor() as q:
    q.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='ef' AND table_type='BASE TABLE' ORDER BY table_name")
    names=[r[0] for r in q.fetchall()];counts={}
    for name in names:
        q.execute(f'SELECT count(*) FROM ef.{name}');counts[name]=q.fetchone()[0]
    assert counts['observacao']==audit['total'] and counts['fonte']==2
    q.execute("SELECT table_name,column_name,data_type,character_maximum_length,numeric_precision,numeric_scale,is_nullable FROM information_schema.columns WHERE table_schema='ef' ORDER BY table_name,ordinal_position")
    columns=[dict(zip([d.name for d in q.description],r)) for r in q.fetchall()]
    q.execute("SELECT c.relname AS tabela,t.conname AS nome,t.contype AS tipo,pg_get_constraintdef(t.oid) AS definicao FROM pg_constraint t JOIN pg_class c ON c.oid=t.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='ef' ORDER BY c.relname,t.conname")
    constraints=[dict(zip([d.name for d in q.description],r)) for r in q.fetchall()]
    q.execute("SELECT sum(pg_total_relation_size(c.oid)) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='ef' AND c.relkind='r'");schema_bytes=int(q.fetchone()[0])
    q.execute('SELECT ano,trimestre,count(*) FROM ef.observacao GROUP BY 1,2 ORDER BY 1,2');periods=q.fetchall();assert periods==[(f['ano'],f['trimestre'],next(s['tratados'] for s in audit['estatisticas'] if s['arquivo']==f['arquivo'])) for f in audit['fontes']]
    q.execute('SELECT count(*) FROM (SELECT ano,trimestre,upa,v1008,v1014,v1016,v2003 FROM ef.observacao GROUP BY 1,2,3,4,5,6,7 HAVING count(*)>1) a');duplicates=q.fetchone()[0];assert duplicates==0
    q.execute('SELECT count(*) FROM ef.observacao WHERE uf<>29 OR vd4002<>1 OR v1028<=0 OR v2009<14 OR is_empreendedor IS DISTINCT FROM (vd4009 IN (8,9)) OR is_empreendedora IS DISTINCT FROM (v2007=2 AND vd4009 IN (8,9))');invalid=q.fetchone()[0];assert invalid==0
    q.execute('SELECT current_database(),inet_server_addr()::text,inet_server_port()');database,address,port=q.fetchone()
    q.execute("SELECT viewname FROM pg_views WHERE schemaname='ef' ORDER BY viewname");views=[r[0] for r in q.fetchall()]
record=dict(banco=database,endereco=address,porta=port,esquema='ef',verificado_em_utc=datetime.now(timezone.utc).isoformat(),tabelas=counts,campos=columns,restricoes=constraints,views=views,bytes_esquema=schema_bytes,contagens_trimestrais=periods,duplicatas=duplicates,inconsistencias=invalid)
(root/'evidencias/estrutura_postgres.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(banco=database,tabelas=counts,views=views,bytes_esquema=schema_bytes,duplicatas=duplicates,inconsistencias=invalid),ensure_ascii=False,indent=2))
