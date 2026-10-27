# Pipeline completo do modelo 3D do site (rodar na raiz do repositório, PowerShell).
#   1. Blender: separa/nomeia as peças e põe os pivôs -> site/assets/models/drone-rigged.glb
#   2. gltf-transform: WebP (normal map quase sem perdas) + Meshopt -> site/assets/models/drone.glb
#   3. Confere a hierarquia e os extras do resultado
# O arquivo original (site/assets/models/source/...) nunca é alterado.
$ErrorActionPreference = "Stop"
$root = (Get-Location).Path
$blender = "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
$src = Join-Path $root "site\assets\models\source\dji-air-2s\source\66371f2fbf595bfe531d2c38ab1b50d6.glb"
$models = Join-Path $root "site\assets\models"
$rigged = Join-Path $models "drone-rigged.glb"
$final = Join-Path $models "drone.glb"
$tmp = Join-Path $env:TEMP "spottingai-model"
New-Item -ItemType Directory -Force $tmp | Out-Null
$gt = "@gltf-transform/cli@4.5.1"

# source/ não é versionado (site/.gitignore): extrai o zip do autor se faltar.
if (-not (Test-Path $src)) {
    Expand-Archive -Path (Join-Path $models "dji-air-2s.zip") -DestinationPath (Join-Path $models "source\dji-air-2s") -Force
}

$retouched = Join-Path $models "textures\basecolor_retouched.png"
$python = Join-Path $root "venv\Scripts\python.exe"

# Logotipos e textos da textura com bordas limpas (comparações em docs/site/tools/renders/logo/)
& $python -I (Join-Path $root "docs\site\tools\retouch_logo.py") $src $retouched (Join-Path $root "docs\site\tools\renders\logo")
if ($LASTEXITCODE -ne 0) { throw "retoque falhou" }

& $blender --background --python (Join-Path $root "docs\site\tools\rig_drone.py") -- $src $rigged $retouched
if ($LASTEXITCODE -ne 0) { throw "Blender falhou" }

# Base color: WebP sem perdas (com perdas borra os logotipos; a textura é quase toda chapada e fica pequena).
# ORM: WebP q90. Normal map: near-lossless (com perdas gera bandas no relevo).
npx -y $gt webp $rigged "$tmp\a0.glb" --slots "baseColorTexture" --lossless true
npx -y $gt webp "$tmp\a0.glb" "$tmp\a.glb" --slots "{occlusionTexture,metallicRoughnessTexture}" --quality 90
npx -y $gt webp "$tmp\a.glb" "$tmp\b.glb" --slots "normalTexture" --near-lossless true
# Meshopt sem achatar/juntar a cena (as peças precisam continuar separadas) e sem simplificar.
npx -y $gt optimize "$tmp\b.glb" $final --compress meshopt --texture-compress false `
    --flatten false --join false --palette false --instance false --simplify false

& $python -I (Join-Path $root "docs\site\tools\glb_nodes.py") $final
Get-Item $rigged, $final | Select-Object Name, @{n = "MB"; e = { [math]::Round($_.Length / 1MB, 2) } }
