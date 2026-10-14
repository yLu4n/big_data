-- Executar depois da carga; os valores observados constam nas evidências.
SELECT ano,trimestre,count(*) FROM ef.observacao GROUP BY 1,2 ORDER BY 1,2;
SELECT count(*) AS total FROM ef.observacao; -- esperado: 464457
SELECT arquivo,count(*) FROM ef.observacao o JOIN ef.fonte f ON f.sha256=o.arquivo_sha256 GROUP BY arquivo;
SELECT count(*) AS grupos_duplicados FROM (
 SELECT ano,trimestre,upa,v1008,v1014,v1016,v2003
 FROM ef.observacao GROUP BY 1,2,3,4,5,6,7 HAVING count(*)>1
) d; -- esperado: 0
SELECT count(*) AS inconsistencias FROM ef.observacao
WHERE vd4002<>1 OR v1028<=0 OR v2009<14
 OR is_empreendedor IS DISTINCT FROM (vd4009 IN (8,9))
 OR is_empreendedora IS DISTINCT FROM (v2007=2 AND vd4009 IN (8,9));
SELECT count(*) FILTER (WHERE vd4016 IS NULL) AS renda_ausente,
 count(*) FILTER (WHERE vd4016=0) AS renda_zero,
 count(*) FILTER (WHERE is_empreendedor AND formalizada IS NULL) AS cnpj_ausente
 FROM ef.observacao;
SELECT pg_total_relation_size('ef.observacao') AS bytes_tabela_indices,
 pg_database_size(current_database()) AS bytes_banco;
SELECT ssl,version,cipher FROM pg_stat_ssl WHERE pid=pg_backend_pid();
SELECT * FROM ef.v_resumo_geografico ORDER BY ano,trimestre,recorte,sexo;
