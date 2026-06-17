$root = $PSScriptRoot
$uvicorn = "C:\Users\ADMIN\AppData\Local\Programs\Python\Python311\Scripts\uvicorn.exe"

8001..8005 | ForEach-Object {
    $port = $_
    Write-Host "Starting worker on port $port..."
    Start-Process -FilePath $uvicorn `
        -ArgumentList "main:app --port $port --workers 1" `
        -WorkingDirectory "$root\apps\ai-service" `
        -NoNewWindow
}

Write-Host "All 5 workers started (8001-8005)"
Write-Host "Now start nginx: C:\nginx\nginx.exe -c C:\graph_knowledge\nginx.conf"
