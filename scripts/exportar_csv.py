"""Reconstrói o CSV da entrega a partir do Parquet versionado."""
import csv
from pathlib import Path
import pyarrow.parquet as pq

def exportar(dados):
    destino=dados/'pnadc_ocupados_2026.csv';temporario=destino.with_suffix('.csv.tmp')
    arquivo=pq.ParquetFile(dados/'pnadc_ocupados_2026.parquet')
    with temporario.open('w',encoding='utf-8',newline='') as f:
        w=csv.writer(f);cols=arquivo.schema_arrow.names;w.writerow(cols)
        for batch in arquivo.iter_batches(batch_size=25000):
            for d in batch.to_pylist():
                w.writerow(['' if d[v] is None else str(d[v]).lower() if isinstance(d[v],bool) else d[v] for v in cols])
    temporario.replace(destino)

if __name__=='__main__':exportar(Path(__file__).resolve().parents[1]/'dados')
