"""ETL reproduzível da PNADC: fluxo binário, validação e deduplicação em disco."""
import argparse, csv, hashlib, json, re, sqlite3
from collections import Counter
from decimal import Decimal
from pathlib import Path
import xlrd
import pyarrow as pa
import pyarrow.parquet as pq

VARS = 'Ano Trimestre UF Capital UPA Estrato V1008 V1014 V1016 V1028 V2003 V2007 V2009 V2010 VD3004 VD4002 VD4009 V4019 V4018 VD4010 VD4016'.split()
IDS = {'UPA':9,'Estrato':7,'V1008':2,'V1014':2,'V1016':1,'V2003':2}
NULLABLE = {'Capital','V4019','V4018','VD4016'}
KEY = 'Ano Trimestre UPA V1008 V1014 V1016 V2003'.split()
FLAGS = 'is_bahia is_salvador is_empreendedor is_empreendedora formalizada'.split()
COLS = [v.lower() for v in VARS] + FLAGS + ['arquivo_sha256','linha_origem']

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def metadata(project):
    inp=project/'dados_brutos/input_PNADC_trimestral.txt'
    layout={v:(int(p)-1,int(w)) for p,v,w in re.findall(r'@(\d+)\s+(\w+)\s+\$?(\d+)\.',inp.read_text(encoding='latin1'))}
    sheet=xlrd.open_workbook(project/'documentação/dicionario_PNADC_microdados_trimestral.xls').sheet_by_index(0)
    domains={}; descriptions={}; current=None
    for i in range(4,sheet.nrows):
        r=sheet.row_values(i)
        if r[2]:
            current=str(r[2]).strip(); descriptions[current]=str(r[4]).strip()
            if current in VARS: assert layout[current]==(int(r[0])-1,int(r[1])),current
        if current in VARS and str(r[5]).strip():
            code=str(r[5]).strip()
            try:
                n=Decimal(code)
                if n==int(n): domains.setdefault(current,{})[int(n)]=str(r[6]).strip()
            except Exception: pass
    s=xlrd.open_workbook(project/'documentação/Variaveis_PNADC_Trimestral.xls').sheet_by_index(0)
    heads=s.row_values(0); indexes=[heads.index('1º tri/2026'),heads.index('2º tri/2026')]
    available={str(s.cell_value(i,0)).strip():[s.cell_value(i,j) for j in indexes] for i in range(1,s.nrows)}
    assert all(available.get(v)==['X','X'] for v in VARS),'Variável indisponível'
    return layout,domains,descriptions

def schema():
    fields=[]
    for v in VARS:
        t=pa.string() if v in IDS else pa.decimal128(18,8) if v=='V1028' else pa.decimal128(12,2) if v=='VD4016' else pa.int16()
        fields.append(pa.field(v.lower(),t,nullable=v in NULLABLE))
    fields += [pa.field(v,pa.bool_(),nullable=v=='formalizada') for v in FLAGS]
    fields += [pa.field('arquivo_sha256',pa.string(),False),pa.field('linha_origem',pa.int64(),False)]
    return pa.schema(fields)

def convert(raw,layout,domains,quarter):
    d={}
    for v in VARS:
        start,width=layout[v]; text=raw[start:start+width].decode('ascii').strip()
        if not text:
            if v not in NULLABLE: raise ValueError(v+': ausente obrigatório')
            d[v]=None; continue
        if v in IDS:
            if not text.isdigit() or len(text)!=IDS[v]: raise ValueError(v+': identificador inválido')
            d[v]=text
        elif v in {'V1028','VD4016'}:
            if not re.fullmatch(r'\d+(\.\d+)?',text):raise ValueError(v+': decimal inválido')
            value=Decimal(text);scale=8 if v=='V1028' else 2
            if value.as_tuple().exponent < -scale:raise ValueError(v+': precisão inválida')
            if v=='V1028' and value<=0:raise ValueError('peso não positivo')
            d[v]=str(value.quantize(Decimal(1).scaleb(-scale)))
        else:
            if not text.isdigit():raise ValueError(v+': código não numérico')
            value=int(text)
            if v in domains and value not in domains[v]:raise ValueError(v+': código fora do dicionário')
            d[v]=value
    if (d['Ano'],d['Trimestre'])!=(2026,quarter):raise ValueError('período diverge do arquivo')
    if not 14<=d['V2009']<=130:raise ValueError('idade fora do universo de ocupados')
    if d['Capital'] is not None and d['Capital']!=d['UF']:raise ValueError('capital incompatível com UF')
    if d['UPA'][:2]!=str(d['UF']):raise ValueError('UPA incompatível com UF')
    if not 1<=int(d['V1008'])<=14 or not 1<=int(d['V2003'])<=30 or not 1<=int(d['V1016'])<=5:raise ValueError('identificação fora do domínio')
    e=d['VD4009'] in (8,9)
    d.update(is_bahia=d['UF']==29,is_salvador=d['UF']==29 and d['Capital']==29,is_empreendedor=e,is_empreendedora=e and d['V2007']==2,formalizada=(d['V4019']==1 if e and d['V4019'] in (1,2) else None))
    return {k.lower():v for k,v in d.items()}

def run(project,out,scratch):
    out.mkdir(parents=True,exist_ok=True);scratch.mkdir(parents=True,exist_ok=True)
    layout,domains,desc=metadata(project)
    stage=scratch/'stage.sqlite';stage.unlink(missing_ok=True)
    db=sqlite3.connect(stage);db.execute('CREATE TABLE rows(k TEXT PRIMARY KEY, data TEXT, digest TEXT, source TEXT, line INTEGER, conflict INTEGER DEFAULT 0)')
    stats=[];sources=[];rej_file=(out/'rejeitados.csv').open('w',encoding='utf-8',newline='');rej=csv.writer(rej_file);rej.writerow(['arquivo','linha','motivo','registro_sha256'])
    for quarter in (1,2):
        path=project/f'dados_brutos/PNADC_0{quarter}2026.txt';h=hashlib.sha256();c=Counter();widths=Counter()
        with path.open('rb') as f:
            for line,full in enumerate(f,1):
                h.update(full);raw=full.rstrip(b'\r\n');c['originais']+=1;widths[len(raw)]+=1
                digest=None
                try:
                    if len(raw)!=3478:raise ValueError('largura diferente de 3478')
                    a,w=layout['VD4002'];occ=raw[a:a+w].strip()
                    if occ not in (b'',b'1',b'2'):raise ValueError('VD4002 fora do domínio')
                    if occ!=b'1':c['fora_universo']+=1;continue
                    c['ocupados']+=1;d=convert(raw,layout,domains,quarter)
                    if d['uf']!=29:c['fora_recorte_geografico']+=1;continue
                    key='|'.join(str(d[v.lower()]) for v in KEY);digest=hashlib.sha256(raw).hexdigest()
                    try:db.execute('INSERT INTO rows(k,data,digest,source,line) VALUES(?,?,?,?,?)',(key,json.dumps(d),digest,path.name,line));c['inseridos']+=1
                    except sqlite3.IntegrityError:
                        old=db.execute('SELECT digest,conflict FROM rows WHERE k=?',(key,)).fetchone()
                        if old[0]==digest:c['duplicatas_identicas']+=1
                        else:
                            db.execute('UPDATE rows SET conflict=1 WHERE k=?',(key,));c['conflitos_adicionais']+=1
                            rej.writerow([path.name,line,'chave repetida com conteúdo diferente',digest])
                except (ValueError,UnicodeError) as e:
                    c['invalidos']+=1;rej.writerow([path.name,line,str(e),digest or hashlib.sha256(raw).hexdigest()])
                if line%25000==0:db.commit()
        db.commit();c['conflitos_primeiros']=db.execute('SELECT COUNT(*) FROM rows WHERE source=? AND conflict=1',(path.name,)).fetchone()[0]
        c['tratados']=db.execute('SELECT COUNT(*) FROM rows WHERE source=? AND conflict=0',(path.name,)).fetchone()[0]
        assert c['originais']==c['fora_universo']+c['fora_recorte_geografico']+c['invalidos']+c['duplicatas_identicas']+c['conflitos_adicionais']+c['conflitos_primeiros']+c['tratados']
        stats.append(dict(arquivo=path.name,larguras=dict(widths),**c));sources.append(dict(arquivo=path.name,sha256=h.hexdigest(),bytes=path.stat().st_size,ano=2026,trimestre=quarter));print(stats[-1],flush=True)
    for source,line,digest in db.execute('SELECT source,line,digest FROM rows WHERE conflict=1'):rej.writerow([source,line,'primeira ocorrência de chave em conflito',digest])
    rej_file.close()
    hashes={s['arquivo']:s['sha256'] for s in sources};nulls=Counter();flags=Counter()
    with (out/'pnadc_ocupados_2026.csv').open('w',encoding='utf-8',newline='') as f, pq.ParquetWriter(out/'pnadc_ocupados_2026.parquet',schema(),compression='zstd') as writer:
        csvout=csv.writer(f);csvout.writerow(COLS);cursor=db.execute('SELECT data,source,line FROM rows WHERE conflict=0 ORDER BY source,line')
        while batch:=cursor.fetchmany(25000):
            records=[]
            for payload,source,line in batch:
                d=json.loads(payload);d.update(arquivo_sha256=hashes[source],linha_origem=line)
                csvout.writerow(['' if d[v] is None else str(d[v]).lower() if isinstance(d[v],bool) else d[v] for v in COLS])
                for v in COLS:
                    if d[v] is None:nulls[v]+=1
                for v in FLAGS:
                    if d[v] is True:flags[v]+=1
                for v in ('v1028','vd4016'):
                    if d[v] is not None:d[v]=Decimal(d[v])
                records.append(d)
            writer.write_table(pa.Table.from_pylist(records,schema=schema()))
    with (out/'referencias.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.writer(f);w.writerow(['variavel','codigo','rotulo'])
        for v,codes in domains.items():
            for code,label in codes.items():
                if v in {'UF','Capital'} and code!=29:continue
                w.writerow([v.lower(),code,label])
    with (out/'fontes.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(sources[0]));w.writeheader();w.writerows(sources)
    data_dict=[]
    for v in VARS:
        data_dict.append(dict(campo=v.lower(),descricao=desc[v],posicao=layout[v][0]+1,largura=layout[v][1],tipo_sql=f'VARCHAR({IDS[v]})' if v in IDS else 'NUMERIC(18,8)' if v=='V1028' else 'NUMERIC(12,2)' if v=='VD4016' else 'SMALLINT',nulo=v in NULLABLE))
    for v in FLAGS:data_dict.append(dict(campo=v,descricao='Indicador derivado conforme levantamento',tipo_sql='BOOLEAN',nulo=v=='formalizada'))
    data_dict += [dict(campo='arquivo_sha256',descricao='SHA-256 do TXT original',tipo_sql='CHAR(64)',nulo=False),dict(campo='linha_origem',descricao='Linha original, iniciada em 1',tipo_sql='BIGINT',nulo=False)]
    (out/'dicionario_tratado.json').write_text(json.dumps(data_dict,ensure_ascii=False,indent=2),encoding='utf-8')
    docs=[project/'dados_brutos/input_PNADC_trimestral.txt',*sorted((project/'documentação').glob('*.xls'))]
    gerados={'dicionario_tratado.json','fontes.csv','pnadc_ocupados_2026.csv','pnadc_ocupados_2026.parquet','referencias.csv','rejeitados.csv'}
    audit=dict(versao='fase2-bahia-v1',recorte_geografico={'uf':29,'descricao':'Toda a Bahia, incluindo Salvador','regra_salvador':'UF=29 AND Capital=29'},estatisticas=stats,fontes=sources,documentacao=[dict(arquivo=p.name,sha256=sha(p)) for p in docs],nulos=dict(nulls),indicadores_verdadeiros=dict(flags),total=sum(s['tratados'] for s in stats),nuvem='O ETL não realiza carga; consulte evidencias/carga_nuvem.json para a comprovação da carga no Aiven',artefatos={p.name:dict(bytes=p.stat().st_size,sha256=sha(p)) for p in out.glob('*') if p.is_file() and p.name in gerados})
    (out/'auditoria.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8');db.close()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--projeto',type=Path,required=True);p.add_argument('--saida',type=Path,default=Path('dados'));p.add_argument('--temporarios',type=Path,default=Path('work'));a=p.parse_args();run(a.projeto,a.saida,a.temporarios)
