"""Carga transacional. PGCONNECTION fornece o DSN, nunca salvo na entrega."""
import argparse, csv, json, os
from datetime import datetime, timezone
from pathlib import Path
import psycopg
from psycopg.conninfo import conninfo_to_dict

def load(root,local,config=None,substituir=False):
    if not (root/'dados/pnadc_ocupados_2026.csv').exists():
        from exportar_csv import exportar
        exportar(root/'dados')
    dsn=os.environ.get('PGCONNECTION') if config is None else None
    if dsn:params=conninfo_to_dict(dsn)
    else:
        config=config or root/'config/postgres.local.json'
        params=json.loads(config.read_text(encoding='utf-8'))
        if 'password' in params:raise SystemExit('Não guarde senha no arquivo de configuração; use PGPASSWORD ou o iniciador PowerShell.')
    params.setdefault('connect_timeout','10')
    if not local:
        if params.get('sslmode') not in ('require','verify-full'):
            raise SystemExit('Carga em nuvem exige sslmode=require ou verify-full.')
        if params.get('sslmode')=='verify-full' and not params.get('sslrootcert'):
            raise SystemExit('Informe sslrootcert para usar verify-full com o CA do serviço.')
    with psycopg.connect(**params) as conn:
        with conn.cursor() as cur:
            cur.execute((root/'sql/01_estrutura.sql').read_text(encoding='utf-8'))
            with (root/'dados/referencias.csv').open(encoding='utf-8',newline='') as f: refs=list(csv.DictReader(f))
            dims=sorted({r['variavel'] for r in refs})
            tables=['observacao','fonte']+['dim_'+v for v in dims]
            for table in tables:
                cur.execute(f'SELECT EXISTS(SELECT 1 FROM ef.{table} LIMIT 1)')
                if cur.fetchone()[0] and not substituir:
                    raise SystemExit('O esquema ef já contém dados. Use --substituir somente para uma recarga intencional.')
            cur.execute('TRUNCATE TABLE '+','.join(['ef.observacao','ef.fonte']+['ef.dim_'+v for v in dims]))
            cur.execute((root/'sql/04_recorte_bahia.sql').read_text(encoding='utf-8'))
            for r in refs:cur.execute(f"INSERT INTO ef.dim_{r['variavel']} (codigo,rotulo) VALUES (%s,%s)",(r['codigo'],r['rotulo']))
            for filename,table in [('fontes.csv','fonte'),('pnadc_ocupados_2026.csv','observacao')]:
                with (root/'dados'/filename).open('r',encoding='utf-8',newline='') as f:
                    cols=next(csv.reader(f))
                    with cur.copy(f"COPY ef.{table} ({','.join(cols)}) FROM STDIN WITH (FORMAT CSV, NULL '')") as copy:
                        while block:=f.read(1024*1024):copy.write(block)
            cur.execute((root/'sql/02_views.sql').read_text(encoding='utf-8'))
            cur.execute('ANALYZE ef.observacao')
            expected=json.loads((root/'dados/auditoria.json').read_text(encoding='utf-8'))['total']
            cur.execute('SELECT count(*) FROM ef.observacao');actual=cur.fetchone()[0]
            if actual!=expected:raise ValueError('Contagem de carga divergente')
            cur.execute('SELECT ano,trimestre,count(*) FROM ef.observacao GROUP BY 1,2 ORDER BY 1,2');counts=cur.fetchall()
            cur.execute("SELECT pg_total_relation_size('ef.observacao'),pg_database_size(current_database())");size=cur.fetchone()
            cur.execute('SELECT version()');version=cur.fetchone()[0]
            cur.execute('SELECT count(*) FROM ef.fonte');nsources=cur.fetchone()[0]
            nrefs=len(refs)
            cur.execute('SELECT * FROM ef.v_resumo_geografico ORDER BY ano,trimestre,recorte,sexo');cols=[c.name for c in cur.description];summary=cur.fetchall()
            cur.execute("SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()");ssl=cur.fetchone()
            if not local and (not ssl or not ssl[0]):raise ValueError('Conexão de nuvem sem SSL')
        # Só gera evidências depois de COMMIT bem-sucedido.
        conn.commit()
        with conn.cursor() as cur:
            cur.execute("SELECT pg_total_relation_size('ef.observacao'),pg_database_size(current_database())")
            size=cur.fetchone()
    evidence=root/'evidencias';evidence.mkdir(exist_ok=True)
    prefix='local' if local else 'nuvem'
    record=dict(ambiente=prefix,sslmode=params.get('sslmode'),certificado_verificado=params.get('sslmode')=='verify-full',host=params.get('host','localhost'),porta=params.get('port','5432'),banco=params.get('dbname'),schema='ef',executado_em_utc=datetime.now(timezone.utc).isoformat(),total=actual,por_trimestre=counts,fontes=nsources,referencias=nrefs,bytes_tabela_indices=size[0],bytes_banco=size[1],postgresql=version,ssl=ssl[0] if ssl else False)
    (evidence/f'carga_{prefix}.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    with (evidence/f'resumo_{prefix}.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.writer(f);w.writerow(cols);w.writerows(summary)
    print(json.dumps(record,ensure_ascii=False,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description='Substitui o conteúdo das tabelas ef dentro de uma transação. Use banco exclusivo do projeto.')
    p.add_argument('--entrega',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--local',action='store_true');p.add_argument('--config',type=Path);p.add_argument('--substituir',action='store_true');a=p.parse_args();load(a.entrega,a.local,a.config,a.substituir)
