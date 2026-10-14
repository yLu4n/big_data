"""Confere hashes, tipos e igualdade integral CSV/Parquet em blocos."""
import argparse,csv,hashlib,json
from decimal import Decimal
from pathlib import Path
import pyarrow.parquet as pq

def hash_file(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def verify(root):
    data=root/'dados';audit=json.loads((data/'auditoria.json').read_text(encoding='utf-8'))
    for name,expected in audit['artefatos'].items():
        p=data/name
        assert p.stat().st_size==expected['bytes'],name
        assert hash_file(p)==expected['sha256'],name
    p=pq.ParquetFile(data/'pnadc_ocupados_2026.parquet')
    assert p.metadata.num_rows==audit['total']
    assert len(p.schema_arrow)==28
    total=0;by_quarter={};keys=set()
    with (data/'pnadc_ocupados_2026.csv').open(encoding='utf-8',newline='') as f:
        reader=csv.DictReader(f)
        assert reader.fieldnames==p.schema_arrow.names
        for batch in p.iter_batches(batch_size=25000):
            for row in batch.to_pylist():
                original=next(reader)
                for col,value in row.items():
                    expected='' if value is None else str(value).lower() if isinstance(value,bool) else str(value)
                    assert original[col]==expected,(total,col)
                assert row['uf']==29
                assert row['vd4002']==1 and row['v1028']>0 and row['v2009']>=14
                assert row['is_empreendedor']==(row['vd4009'] in (8,9))
                assert row['is_empreendedora']==(row['v2007']==2 and row['vd4009'] in (8,9))
                assert row['is_bahia']==(row['uf']==29)
                assert row['is_salvador']==(row['uf']==29 and row['capital']==29)
                key=tuple(row[v] for v in ['ano','trimestre','upa','v1008','v1014','v1016','v2003'])
                assert key not in keys;keys.add(key)
                total+=1;by_quarter[row['trimestre']]=by_quarter.get(row['trimestre'],0)+1
        assert next(reader,None) is None
    expected={f['trimestre']:next(s['tratados'] for s in audit['estatisticas'] if s['arquivo']==f['arquivo']) for f in audit['fontes']}
    assert by_quarter==expected and total==audit['total']
    result=dict(total=total,colunas=28,por_trimestre=by_quarter,hashes='OK',csv_parquet='Todas as células iguais',unicidade='OK',indicadores='OK',recorte_uf_29='OK')
    evidence=root/'evidencias';evidence.mkdir(exist_ok=True)
    (evidence/'verificacao_artefatos.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--entrega',type=Path,default=Path(__file__).resolve().parents[1]);a=p.parse_args();verify(a.entrega)
