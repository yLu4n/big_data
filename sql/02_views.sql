CREATE OR REPLACE VIEW ef.v_recortes AS
 SELECT o.*,r.recorte FROM ef.observacao o
 CROSS JOIN LATERAL (
   SELECT 'Brasil'::text AS recorte
   UNION ALL SELECT 'Bahia' WHERE o.is_bahia
   UNION ALL SELECT 'Salvador' WHERE o.is_salvador
 ) r;

-- Brasil, Bahia e Salvador se sobrepõem: nunca somar os recortes.
CREATE OR REPLACE VIEW ef.v_resumo_geografico AS
 SELECT ano,trimestre,recorte,v2007 AS sexo,
 count(*) AS observacoes_amostra,
 sum(v1028) AS ocupados_estimados,
 count(*) FILTER (WHERE is_empreendedor) AS empreendedores_amostra,
 sum(v1028) FILTER (WHERE is_empreendedor) AS empreendedores_estimados,
 count(*) FILTER (WHERE is_empreendedora) AS empreendedoras_amostra,
 sum(v1028) FILTER (WHERE is_empreendedora) AS empreendedoras_estimadas,
 sum(v1028*vd4016) FILTER (WHERE is_empreendedor AND vd4016 IS NOT NULL)
 /NULLIF(sum(v1028) FILTER (WHERE is_empreendedor AND vd4016 IS NOT NULL),0)
 AS renda_media_empreendedores,
 count(*) FILTER (WHERE is_empreendedor AND vd4016 IS NOT NULL) AS rendas_informadas,
 sum(v1028) FILTER (WHERE is_empreendedor AND vd4016 IS NOT NULL) AS peso_rendas_informadas,
 sum(v1028) FILTER (WHERE is_empreendedor AND formalizada IS TRUE) AS formalizados_estimados,
 sum(v1028) FILTER (WHERE is_empreendedor AND formalizada IS FALSE) AS sem_cnpj_estimados,
 count(*) FILTER (WHERE is_empreendedor AND formalizada IS NULL) AS cnpj_ausente_amostra
 FROM ef.v_recortes GROUP BY ano,trimestre,recorte,v2007;

CREATE OR REPLACE VIEW ef.v_perfil_empreendedores AS
 SELECT ano,trimestre,recorte,v2007 AS sexo,v2010 AS cor_raca,
 vd3004 AS escolaridade,vd4009 AS posicao,vd4010 AS atividade,formalizada,
 count(*) AS observacoes_amostra,sum(v1028) AS pessoas_estimadas,
 sum(v1028*vd4016) FILTER (WHERE vd4016 IS NOT NULL)
 /NULLIF(sum(v1028) FILTER (WHERE vd4016 IS NOT NULL),0) AS renda_media_ponderada,
 count(vd4016) AS rendas_informadas
 FROM ef.v_recortes WHERE is_empreendedor
 GROUP BY ano,trimestre,recorte,v2007,v2010,vd3004,vd4009,vd4010,formalizada;
