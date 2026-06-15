Write-Host "Starting Immigration RAG..." -ForegroundColor Cyan

# AI Service
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd 'C:\graph_knowledge\apps\ai-service'; python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload" -WindowStyle Normal

# Web
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd 'C:\graph_knowledge\apps\web'; npm run dev" -WindowStyle Normal

Start-Sleep -Seconds 3
Write-Host ""
Write-Host "Web:        http://localhost:5173" -ForegroundColor Green
Write-Host "API Docs:   http://localhost:8000/docs" -ForegroundColor Green
Write-Host ""
Start-Process "http://localhost:5173"
