# Empreendedorismo Feminino no Brasil - Entrega técnica fase 2

Equipe indicada no levantamento: Kauã Kley, Luan Victor e Beatriz Costa.

Entrega produzida a partir dos arquivos fornecidos, em 13/10/2026. A base `fase2-v1`, com a entrega de conexão revisada `fase2-v2`, reúne 464.457 observações de pessoas ocupadas: 228.357 no 1º trimestre e 236.100 no 2º trimestre de 2026. São observações de pessoa por trimestre, não pessoas distintas no semestre.

## Situação dos entregáveis

1. **Base tratada concluída:** CSV e Parquet com 21 campos de origem, 5 indicadores e 2 campos de rastreabilidade.
2. **Processo concluído e documentado:** scripts Python, SQL, dicionário, auditoria e evidências. Código, documentação e Parquet publicados em https://github.com/yLu4n/big_data, branch `main`. O Parquet compacto acompanha o código; o CSV pode ser reconstruído automaticamente na carga.
3. **Banco PostgreSQL carregado em `localhost:5432/big_data`, esquema `ef`:** 464.457 observações, 2 fontes, 10 dimensões e 99 códigos. Estrutura, chaves, restrições e views validadas; backup do esquema disponível. **Hospedagem em nuvem pendente:** o usuário informou que ainda não existe serviço Aiven. A validação local não comprova armazenamento em nuvem.

## Arquivos

- `Relatorio_Tecnico_Fase_2.pdf`: relatório para apresentação da atividade.
- `dados/pnadc_ocupados_2026.parquet`: base tipada e compactada com Zstandard.
- `dados/pnadc_ocupados_2026.csv`: a mesma base, UTF-8, vírgula, decimal com ponto, nulos vazios e booleanos `true`/`false`.
- `dados/empreendedorismo_feminino.dump`: backup PostgreSQL em formato custom, com estrutura e dados; exige `pg_restore` compatível com PostgreSQL 18 ou posterior.
- `dados/fontes.csv`, `referencias.csv`, `dicionario_tratado.json`, `auditoria.json` e `rejeitados.csv`: proveniência, rótulos, tipos, contagens, hashes e quarentena.
- `scripts/etl.py`: leitura posicional e tratamento em fluxo; usa SQLite somente como área temporária de deduplicação em disco.
- `scripts/carregar_postgres.py`: carga atômica e evidências; lê conexão de `config/postgres.local.json` ou da variável de ambiente `PGCONNECTION`; a senha não é versionada.
- `scripts/verificar_artefatos.py`: hashes e comparação integral das células CSV/Parquet, chaves e indicadores.
- `scripts/verificar_postgres.py`: verifica contagens, tipos, restrições e relacionamentos no banco configurado.
- `scripts/conectar_e_carregar.ps1`: solicita a senha e executa a carga local.
- `config/postgres.local.json`: host, porta, banco e usuário da conexão fornecida, sem senha.
- `sql/`: estrutura, views e consultas de validação.
- `evidencias/`: resultados executados no ambiente local.

A restauração do backup extraído do esquema `ef` do `big_data` em um segundo banco vazio foi executada com sucesso: 228.357 e 236.100 observações por trimestre e 12 linhas na view de resumo geográfico. A conferência adicional de 186 observações contra as linhas dos TXT originais também passou. Os resultados estão em `restauracao_backup.txt` e `conferencia_origem.json`.

Os originais permanecem intactos na pasta de projeto fornecida. Não foram incluídos no ZIP por ocuparem 3,59 GB. Seus hashes SHA-256 identificam precisamente a versão usada. A atribuição ao IBGE é baseada na documentação fornecida; não foi feito novo download nem comprovada externamente a autenticidade desses arquivos.

## Reproduzir o tratamento

Requisitos: Python 3.12 e bibliotecas do `requirements.txt`. Em PowerShell, a partir desta pasta:

```powershell
python -m venv .venv
& ./.venv/Scripts/python.exe -m pip install -r requirements.txt
& ./.venv/Scripts/python.exe scripts/etl.py --projeto 'C:/caminho/Projeto_Empreendedorismo_Feminino' --saida dados --temporarios work
& ./.venv/Scripts/python.exe scripts/verificar_artefatos.py
```

O ETL substitui os artefatos de sua pasta de saída e recria a área SQLite temporária. A memória é limitada por blocos de exportação de 25.000 observações; a leitura não carrega os TXT completos. A verificação independente usa um conjunto de chaves em memória para checar unicidade. Para períodos adicionais, as regras de período e contagens esperadas precisam ser revistas.

## Modelagem e regras

O esquema `ef` contém `fonte`, `observacao` e 10 dimensões: `dim_uf`, `dim_capital`, `dim_v2007`, `dim_v2010`, `dim_vd3004`, `dim_vd4002`, `dim_vd4009`, `dim_v4019`, `dim_v4018` e `dim_vd4010`. Cada dimensão usa `codigo SMALLINT PRIMARY KEY` e `rotulo TEXT NOT NULL`. `fonte` usa SHA-256 como chave primária. A observação usa a chave composta `(ano,trimestre,upa,v1008,v1014,v1016,v2003)` e se relaciona às dimensões por chaves estrangeiras e à fonte por `arquivo_sha256`.

Campos e tipos completos estão no dicionário JSON e no SQL. Os rótulos são extraídos do dicionário XLS, não escritos manualmente. São mantidas todas as UFs e ambos os sexos, com filtro `VD4002=1`. Empreendedor: `VD4009 IN (8,9)`; empreendedora: essa condição e `V2007=2`. Bahia: `UF=29`; Salvador: `UF=29 AND Capital=29`. Formalização significa registro do negócio no CNPJ, aplicada somente aos empreendedores; fora do universo ou sem resposta fica nula.

Brancos opcionais viram NULL. Renda ausente não vira zero; zeros existentes são preservados. Códigos ignorados previstos no dicionário são mantidos. Não há imputação, subamostragem, exclusão geográfica, agregação anterior à carga ou remoção de rendas altas válidas. Campos obrigatórios inválidos, domínios desconhecidos, largura incorreta e inconsistências de identificação são separados em `rejeitados.csv`. Duplicatas com a mesma chave e linha original idêntica são removidas; conteúdos diferentes sob a mesma chave retiram ambas as ocorrências da base válida.

As views calculam somas de V1028 e médias ponderadas usando apenas pesos de observações com renda informada no denominador. O rendimento é habitual do trabalho principal, nominal. Brasil, Bahia e Salvador se sobrepõem e não devem ser somados. Trimestres também não devem ser somados para obter pessoas distintas. Não se estimaram erros padrão ou intervalos de confiança. Pesos replicados ficam fora da base compacta, mas os originais foram preservados; UPA, estrato e peso calibrado permanecem para análises posteriores do desenho amostral.

## Carga local ou em nuvem

A conexão local já está configurada para host `localhost`, porta `5432`, banco `big_data` e usuário `postgres`. O esquema `ef` separa esta entrega das tabelas já existentes em `empreendedorismo`. A carga inicial foi executada. Para recarregar, execute `./scripts/conectar_e_carregar.ps1 -Substituir`: a senha é solicitada e mantida somente durante o processo. Sem essa opção, o carregador recusa alterar tabelas `ef` que já contenham dados. A substituição, quando autorizada pela opção, ocorre dentro de uma única transação. É necessária permissão para criar esquema, tabelas e views. O esquema existente deve ser compatível com esta versão; `CREATE TABLE IF NOT EXISTS` não migra versões anteriores.

Para a conexão local, use `./scripts/conectar_e_carregar.ps1` na primeira carga ou a opção `-Substituir` em uma recarga intencional. O script solicita a senha e utiliza a configuração JSON. Alternativamente, configure `PGCONNECTION` no ambiente sem colocar credenciais no código, README ou Git e use `--local`. Para Aiven, obtenha no painel os parâmetros de conexão e o certificado CA e configure `sslmode=verify-full` e `sslrootcert` com o caminho do CA. O carregador exige essas configurações ao executar sem `--local` e verifica SSL na conexão.

```powershell
# PGCONNECTION deve estar configurada na sessão por um mecanismo seguro.
& ./.venv/Scripts/python.exe scripts/carregar_postgres.py
# No ambiente local, somente:
& ./.venv/Scripts/python.exe scripts/carregar_postgres.py --local
```

Após a carga no Aiven, executar `sql/03_validacao.sql` e guardar resultados ou capturas do painel com host e credenciais ocultados. O script grava `evidencias/carga_nuvem.json` e `resumo_nuvem.csv` somente após o commit. Conferir 464.457 linhas, as duas contagens trimestrais, SSL, tamanho efetivo com `pg_database_size`, armazenamento livre e limites do serviço. Esses valores não podem ser inferidos do tamanho do Parquet.

Para restaurar o backup em banco vazio, configure os parâmetros seguros de conexão do `pg_restore` e execute:

```powershell
pg_restore --no-owner --no-acl --dbname=nome_do_banco dados/empreendedorismo_feminino.dump
```

Use o carregador para uma futura conexão Aiven como caminho preferencial, pois ele aplica a exigência de TLS e gera as evidências. O endereço `localhost:5432/big_data` é um banco local e não comprova hospedagem em nuvem. Não há serviço ou comprovação Aiven nesta entrega.

## Código publicado no repositório da equipe

O repositório contém README, relatório, scripts, requirements, configuração sem senha, SQL, dicionário, auditoria, evidências e Parquet. A configuração `.gitattributes` preserva os bytes e hashes dos arquivos ao clonar. O `.gitignore` exclui o CSV volumoso e o backup; o Parquet de 6,50 MB e os pequenos CSV de referência são versionados. Ao clonar, o carregador reconstrói automaticamente o CSV da base a partir do Parquet, caso o CSV esteja ausente. O backup e o CSV completos acompanham o ZIP. A evidência de publicação encontra-se em `evidencias/repositorio.json`.

## Referências usadas

- Solicitação de Entrega Técnica fase 2, arquivo PDF fornecido pelo usuário.
- Empreendedorismo Feminino no Brasil - Levantamento de parâmetros e tipagem de dados, PDF fornecido pelo usuário.
- Pasta Projeto_Empreendedorismo_Feminino: TXT dos dois trimestres, layout SAS, dicionário e disponibilidade de variáveis XLS.

O Sebrae é citado no levantamento como contexto; nenhuma tabela de estudo anterior ou publicação complementar foi incorporada aos microdados tratados.

## Inventário executado no banco informado

`evidencias/estrutura_postgres.json` contém cada tabela e sua quantidade de registros, todos os campos e tipos, as definições de chaves primárias, estrangeiras e CHECKs e as três views. A carga de `ef` ocupa 182.509.568 bytes somando tabelas e índices. `pg_database_size(big_data)` inclui também os esquemas já existentes e por isso não representa apenas esta entrega.
