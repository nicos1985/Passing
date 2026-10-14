$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)

try {
    $inputData = [Console]::In.ReadToEnd() | ConvertFrom-Json
    $body = @{
        model = $inputData.model
        messages = @(
            @{ role = 'system'; content = $inputData.system }
            @{ role = 'user'; content = $inputData.message }
        )
        temperature = $inputData.temperature
        max_tokens = $inputData.max_tokens
        response_format = @{ type = 'json_object' }
    } | ConvertTo-Json -Depth 8 -Compress
    $headers = @{ Authorization = "Bearer $($inputData.key)" }
    $httpResponse = Invoke-WebRequest -Uri 'https://api.openai.com/v1/chat/completions' -Method Post -UseBasicParsing `
        -Headers $headers -ContentType 'application/json; charset=utf-8' `
        -Body ([System.Text.Encoding]::UTF8.GetBytes($body)) -TimeoutSec 35
    $response = [System.Text.Encoding]::UTF8.GetString($httpResponse.RawContentStream.ToArray()) | ConvertFrom-Json
    $content = $response.choices[0].message.content
    if (-not $content) { exit 1 }
    [Console]::Out.Write($content)
} catch {
    # El proceso padre registra solo una categoría de error, nunca la respuesta ni la clave.
    exit 1
}
