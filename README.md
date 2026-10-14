# Empreendedorismo Feminino - Bahia e Salvador

Base `fase2-bahia-v1` / entrega `fase2-bahia-aiven-v1`, atualizada em 14/10/2026. A base atual contém **somente pessoas ocupadas da Bahia (`UF=29`)**, incluindo Salvador. São **20.706 observações pessoa-trimestre**, com **3.382 observações de Salvador (`Capital=29`)**. Ambos os sexos e todas as posições na ocupação permanecem; os indicadores identificam empreendedores e empreendedoras.

| Período | Bahia, incluindo Salvador | Salvador, subconjunto |
|---|---:|---:|
| 1º trimestre de 2026 | 10.062 | 1.645 |
| 2º trimestre de 2026 | 10.644 | 1.737 |
| Total de observações | 20.706 | 3.382 |

Salvador já está incluído no total da Bahia. Os recortes não devem ser somados. Pessoas podem reaparecer nos dois períodos; os totais não correspondem a pessoas distintas no semestre.

## Entregáveis

1. **Base tratada:** Parquet e CSV, com 21 campos de origem, 5 indicadores e 2 campos de rastreabilidade. A auditoria registra hashes, contagens, exclusões geográficas, nulos e decisões. A versão nacional anterior foi substituída na versão atual do projeto pelo recorte da Bahia.
2. **Processo:** ETL, exportação, carregador PostgreSQL, verificadores, SQL e documentação disponíveis em https://github.com/yLu4n/big_data. O Parquet é versionado; o CSV pode ser reconstruído a partir dele.
3. **Banco em nuvem concluído:** serviço PostgreSQL do Aiven, banco `defaultdb`, esquema `ef`, com 20.706 observações, 2 fontes, 10 dimensões, 47 códigos e 3 views. A estrutura, campos, tipos, relacionamentos e contagens estão em `evidencias/estrutura_nuvem.json`. Todas as células do banco foram comparadas ao Parquet tratado e coincidiram. A cópia local `big_data` permanece disponível.

## Origem e transformações

Os dois TXT PNADC_012026.txt e PNADC_022026.txt foram lidos na pasta de projeto fornecida, com o layout SAS `input_PNADC_trimestral.txt` e o dicionário e disponibilidade de variáveis XLS. A fonte é atribuída ao IBGE pela documentação fornecida. Os originais não foram alterados e seus SHA-256 identificam a versão exata utilizada.

Foram lidas 1.032.879 linhas originais. O filtro `VD4002=1` excluiu 568.422 linhas fora do universo de ocupados. Depois da validação das variáveis, o filtro `UF=29` excluiu 443.751 ocupados de outras UFs, mantendo 20.706 da Bahia. Essas exclusões geográficas não são erros nem rejeições. Não foram encontrados inválidos, duplicatas ou conflitos. A nova execução partiu dos TXT originais, e todas as células foram comparadas ao recorte da versão tratada nacional anterior.

A leitura é em fluxo; SQLite serve apenas como área temporária de deduplicação em disco. A exportação usa blocos de 25.000 registros. Não há imputação, subamostragem ou agregação antes da carga. Brancos opcionais viram NULL; renda ausente não vira zero e rendas válidas não são removidas por serem altas. Identificadores permanecem como texto, preservando zeros. Peso e renda usam Decimal, sem conversão intermediária para ponto flutuante.

Duplicatas com chave e linha original idênticas são removidas. Chaves iguais com conteúdo diferente retiram todas as ocorrências da base válida para revisão. Erros de largura, tipo, domínio e identificação são registrados em `dados/rejeitados.csv`.

## Reproduzir a base da Bahia

Execute os comandos a partir da pasta do projeto. Python 3.12 e as dependências fixadas estão em `requirements.txt`.

```powershell
python -m venv .venv
& ./.venv/Scripts/python.exe -m pip install -r requirements.txt
& ./.venv/Scripts/python.exe scripts/etl.py --projeto "C:/Users/saeb/Downloads/Projeto_Empreendedorismo_Feminino" --saida dados --temporarios work
& ./.venv/Scripts/python.exe scripts/verificar_artefatos.py
```

`--projeto` recebe a pasta que contém `dados_brutos` e `documentação`. O ETL agora aplica `UF=29` automaticamente; não é necessário fornecer um filtro adicional. A saída mantém os nomes `pnadc_ocupados_2026.csv` e `pnadc_ocupados_2026.parquet`, mas seu conteúdo é exclusivamente da Bahia. Ao executar em uma pasta antiga, o ETL substitui esses arquivos; backups e relatórios antigos precisam ser atualizados separadamente.

## Conexão Aiven - dados disponíveis em nuvem

A conexão está configurada em `config/postgres.aiven.json`, sem senha:

- Host: `pg-3746e955-bigdatalkb.f.aivencloud.com`
- Porta: `22835`
- Banco: `defaultdb`
- Usuário: `avnadmin`
- Esquema: `ef`
- SSL: `require`, conforme os parâmetros fornecidos.

A carga foi realizada e validada em 14/10/2026. A conexão confirmou TLS 1.3. Nenhum certificado CA foi fornecido: `require` criptografa a conexão, mas esta configuração não faz a validação de identidade do servidor com um CA. Caso o CA seja fornecido depois, o carregador também permite `verify-full` com `sslrootcert`.

Para uma recarga intencional, a partir da pasta do projeto:

```powershell
./scripts/conectar_e_carregar_aiven.ps1 -Substituir
```

O script solicita a senha de avnadmin e não a grava em arquivo. Para um banco ainda vazio, omita `-Substituir`. Alternativamente, com `PGPASSWORD` configurada na sessão:

```powershell
& ./.venv/Scripts/python.exe scripts/carregar_postgres.py --config config/postgres.aiven.json --substituir
& ./.venv/Scripts/python.exe scripts/verificar_postgres.py --config config/postgres.aiven.json --nuvem
```

A opção `--config` explícita tem precedência sobre `PGCONNECTION`. Sem `--config`, essa variável pode fornecer a conexão; se estiver ausente, usa-se o perfil local. Evidências de nuvem são gravadas em arquivos separados das evidências locais. A carga continua transacional, protegida por `--substituir` e por `CHECK (uf=29)`.

No pgAdmin ou em outro cliente PostgreSQL, utilize os campos do arquivo Aiven, informe a senha e configure SSL Require. As tabelas estão em `Schemas > ef > Tables`. Consulta de conferência:

```sql
SELECT ano,trimestre,count(*) FROM ef.observacao GROUP BY ano,trimestre;
SELECT count(*) FROM ef.observacao WHERE capital=29;
SELECT * FROM ef.v_resumo_geografico ORDER BY ano,trimestre,recorte,sexo;
```

## Conexão local e carga

A configuração sem senha está em `config/postgres.local.json`: host localhost, porta 5432, banco big_data e usuário postgres. Para recarregar o esquema `ef` já existente, execute:

```powershell
./scripts/conectar_e_carregar.ps1 -Substituir
```

O script solicita a senha. Como alternativa, configure `PGPASSWORD` na sessão e execute:

```powershell
& ./.venv/Scripts/python.exe scripts/carregar_postgres.py --local --substituir
& ./.venv/Scripts/python.exe scripts/verificar_postgres.py
```

A substituição é transacional e limitada às tabelas do esquema `ef`. O carregador esvazia as tabelas, aplica `sql/04_recorte_bahia.sql`, carrega os dados e valida a contagem. A restrição `CHECK (uf=29)` impede inserir observações de outras UFs. Sem `--substituir`, tabelas já populadas não são recarregadas. As demais tabelas já existentes no banco, incluindo o esquema `empreendedorismo`, não são geridas por esta entrega.

Quando o CSV não estiver disponível no clone, o carregador o reconstrói automaticamente do Parquet. Não grave a senha no código ou no Git. Sem `--config`, `PGCONNECTION` pode fornecer a conexão. O perfil Aiven é selecionado explicitamente pelo iniciador de nuvem; os modos de nuvem permitidos são `require` e `verify-full` com certificado CA.

## Modelo, tipos e regras

O esquema contém `fonte`, `observacao` e as dimensões `dim_uf`, `dim_capital`, `dim_v2007`, `dim_v2010`, `dim_vd3004`, `dim_vd4002`, `dim_vd4009`, `dim_v4019`, `dim_v4018` e `dim_vd4010`. Os catálogos de UF e capital contêm apenas o código 29; os demais preservam os códigos do dicionário, inclusive categorias que podem não ter ocorrência nesta amostra.

Cada dimensão tem `codigo SMALLINT PRIMARY KEY` e `rotulo TEXT NOT NULL`. `fonte` usa SHA-256 como chave primária. `observacao` usa `(ano,trimestre,upa,v1008,v1014,v1016,v2003)` como chave composta e se relaciona às dimensões e à fonte por chaves estrangeiras. Há índices para período, geografia, sexo e empreendedoras. Os campos, tipos, posições e larguras constam de `dados/dicionario_tratado.json` e `sql/01_estrutura.sql`.

Peso: NUMERIC(18,8). Renda: NUMERIC(12,2). Identificadores: VARCHAR com a largura da origem. Códigos: SMALLINT. Indicadores: BOOLEAN. Hash da origem: CHAR(64); linha de origem: BIGINT.

Empreendedor: `VD4009 IN (8,9)`; empreendedora: essa condição e `V2007=2`. Salvador: `UF=29 AND Capital=29`. Formalização representa CNPJ, com base em V4019, apenas entre empreendedores; fora desse universo ou sem resposta, fica NULL. V4018 é uma faixa, não uma quantidade exata.

As views oferecem **somente Bahia e Salvador**; não há resumo Brasil com dados incompletos. Estimativas pontuais usam soma de V1028; a renda média usa soma(peso × renda) / soma(peso) apenas para observações com renda informada no mesmo grupo. Rendas são habituais do trabalho principal e nominais. Erros padrão, intervalos de confiança e comparações reais de renda exigem etapas adicionais de desenho amostral e deflacionamento. Os originais preservam os pesos replicados; UPA, estrato e peso calibrado permanecem na base compacta.

## Consultas

```sql
-- Toda a base atual: apenas Bahia, incluindo Salvador.
SELECT * FROM ef.observacao;

-- Salvador.
SELECT * FROM ef.observacao WHERE uf=29 AND capital=29;

-- Bahia fora de Salvador: NULL em Capital permanece no restante do estado.
SELECT * FROM ef.observacao WHERE uf=29 AND capital IS DISTINCT FROM 29;

SELECT uf,capital,count(*) FROM ef.observacao GROUP BY uf,capital;
```

## Evidências e distribuição

`verificacao_artefatos.json` confere hashes, tipos, igualdade integral CSV/Parquet, chaves, indicadores e UF. `comparacao_recorte.json` confirma a igualdade integral com o recorte UF=29 da versão anterior. `carga_local.json`, `estrutura_postgres.json`, `validacao_local.txt`, `resumo_local.csv` e `restauracao_backup.txt` comprovam a carga e a restauração da versão Bahia. `auditoria.json` identifica entradas e saídas; o manifesto do pacote inclui o backup e o relatório.

As evidências `carga_nuvem.json`, `estrutura_nuvem.json`, `validacao_nuvem.txt`, `resumo_nuvem.csv` e `comparacao_integral_aiven.json` comprovam a carga no Aiven, TLS e igualdade integral com a base tratada.

O ZIP inclui CSV, Parquet, backup local (`empreendedorismo_feminino.dump`), backup do Aiven (`empreendedorismo_feminino_aiven.dump`), relatório, scripts, SQL e evidências. O Git versiona o Parquet e os metadados; exclui CSV volumoso, backup, senha, ambiente virtual e temporários. `.gitattributes` mantém os bytes necessários à conferência de hashes. O relatório conserva as seis páginas solicitadas, sem os tópicos e a página 7 removidos anteriormente.
