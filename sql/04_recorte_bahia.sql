-- Aplicar depois de esvaziar a tabela, dentro da transação de carga.
ALTER TABLE ef.observacao DROP CONSTRAINT IF EXISTS ck_recorte_bahia;
ALTER TABLE ef.observacao ADD CONSTRAINT ck_recorte_bahia CHECK (uf=29);
