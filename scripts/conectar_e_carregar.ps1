param([switch]$Substituir)
$ErrorActionPreference='Stop'
$raiz=Split-Path -Parent $PSScriptRoot
$python=Join-Path $raiz '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Crie a .venv e instale requirements.txt conforme o README.' }
$senha=Read-Host 'Senha do usuario postgres no banco big_data' -AsSecureString
$anterior=$env:PGPASSWORD
try {
 $env:PGPASSWORD=[System.Net.NetworkCredential]::new('', $senha).Password
 $argumentos=@((Join-Path $PSScriptRoot 'carregar_postgres.py'),'--local')
 if ($Substituir) { $argumentos+='--substituir' }
 & $python @argumentos
 if ($LASTEXITCODE -ne 0) { throw 'A carga nao foi concluida. Confira a mensagem acima.' }
} finally { $env:PGPASSWORD=$anterior; $senha.Dispose() }
