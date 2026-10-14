param([switch]$Substituir)
$ErrorActionPreference='Stop'
$raiz=Split-Path -Parent $PSScriptRoot
$python=Join-Path $raiz '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Crie a .venv e instale requirements.txt conforme o README.' }
$senha=Read-Host 'Senha do usuario avnadmin no Aiven' -AsSecureString
$anterior=$env:PGPASSWORD
try {
 $env:PGPASSWORD=[System.Net.NetworkCredential]::new('', $senha).Password
 $argumentos=@((Join-Path $PSScriptRoot 'carregar_postgres.py'),'--config',(Join-Path $raiz 'config/postgres.aiven.json'))
 if ($Substituir) { $argumentos+='--substituir' }
 & $python @argumentos
 if ($LASTEXITCODE -ne 0) { throw 'A carga no Aiven nao foi concluida. Confira a mensagem acima.' }
 & $python (Join-Path $PSScriptRoot 'verificar_postgres.py') --config (Join-Path $raiz 'config/postgres.aiven.json') --nuvem
 if ($LASTEXITCODE -ne 0) { throw 'Falha na verificacao do banco em nuvem.' }
} finally { $env:PGPASSWORD=$anterior; $senha.Dispose() }
