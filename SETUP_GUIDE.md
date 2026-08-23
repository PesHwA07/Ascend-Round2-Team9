# 🚀 AuraBrief 95 — Complete Setup & Run Guide

> **For all 5 team members.** Follow every step in exact order. Estimated time: ~10 minutes.

---

## 📋 Prerequisites (Install These First)

Before anything, make sure you have these installed on your laptop:

| Tool | Why We Need It | Install Link |
|------|---------------|--------------|
| **Git** | Clone the repo | https://git-scm.com/downloads |
| **Docker Desktop** | Runs all 3 services in containers | https://www.docker.com/products/docker-desktop/ |
| **Ollama** | Runs the local LLM for AI explanations | https://ollama.com/download |

### ⚠️ Docker Desktop Setup
After installing Docker Desktop:
1. **Open Docker Desktop** and let it start completely (whale icon in system tray should be stable)
2. On Windows: Go to **Settings → Resources → WSL Integration** → Enable for your default distro
3. Make sure Docker is **running** before proceeding (you should see "Docker Desktop is running" in the app)

---

## Step 1: Clone the Repository

Open **PowerShell** (Windows) or **Terminal** (Mac/Linux) and run:

```bash
git clone https://github.com/PesHwA07/Ascend-Round2-Team9.git
cd Ascend-Round2-Team9
git checkout main
git pull origin main
```

> You should now see these folders: `backend/`, `frontend/`, `simulator/`

---

## Step 2: Set Up Ollama (The AI Brain)

### 2a. Start Ollama

**Windows/Mac:** Just open the Ollama app. It runs in the background.

**Linux:**
```bash
ollama serve
```

### 2b. Pull the LLM Model

```bash
ollama pull llama3.2:3b
```

> ⏳ This downloads ~2GB. Wait for it to finish completely.

### 2c. Verify Ollama is Running

```bash
ollama list
```

You should see `llama3.2:3b` in the list. Also verify the API is up:

```bash
curl http://localhost:11434/api/tags
```

You should get a JSON response listing the model. If you see `connection refused`, Ollama is not running — go back to Step 2a.

---

## Step 3: Create the Environment File

In the project root folder (`Ascend-Round2-Team9/`), create a file called `.env`:

**Windows (PowerShell):**
```powershell
Copy-Item .env.example .env
```

**Mac/Linux:**
```bash
cp .env.example .env
```

### ⚠️ Important: Edit .env ONLY if needed

The defaults work for most setups. But check these:

| Setting | Default | Change If... |
|---------|---------|-------------|
| `OLLAMA_HOST` | `http://host.docker.internal:11434` | You're on **Linux** → change to `http://172.17.0.1:11434` |
| `OLLAMA_MODEL` | `llama3.2:3b` | You pulled a different model name |
| `STREAM_INTERVAL` | `5` | You want faster events (use `2`) or slower (use `10`) |

> **Linux Users Only:** `host.docker.internal` doesn't work on Linux. Edit `.env`:
> ```
> OLLAMA_HOST=http://172.17.0.1:11434
> ```

---

## Step 4: Build & Start Everything with Docker

This single command builds and starts all 3 services:

```bash
docker-compose up --build
```

> ⏳ **First run takes 3-5 minutes** (downloading Python/Node images, installing dependencies).
> Subsequent runs take ~10 seconds.

### What You Should See in the Terminal

Wait for these logs to appear (in order):

```
backend-1    | INFO:     Uvicorn running on http://0.0.0.0:8000
backend-1    | INFO:     Application startup complete
frontend-1   | VITE v5.x.x ready in xxx ms
frontend-1   | ➜  Local: http://localhost:5173/
simulator-1  | [SIMULATOR] Starting event generation...
simulator-1  | [SIMULATOR] Sent batch of X events
```

> ✅ When you see the simulator sending events, everything is working!

---

## Step 5: Open the Dashboard

Open your browser and go to:

### 👉 **http://localhost:5173**

You should see the **AuraBrief 95** dashboard with:
- ✅ Incident cards appearing with severity colors
- ✅ AI-generated summaries on each card (from Ollama)
- ✅ Score breakdowns (severity, frequency, recency, anomaly, business impact)
- ✅ Navigation tabs: Dashboard, History, Audit Log

---

## Step 6: Verify Everything Works

### Check the Backend API directly:
```bash
curl http://localhost:8000/api/health
```
Expected: `{"status": "healthy", ...}`

### Check Triage Results:
```bash
curl http://localhost:8000/api/triage/current
```
Expected: JSON with `ranked_events` array containing scored incidents.

---

## 🛑 How to Stop Everything

Press `Ctrl + C` in the terminal where Docker is running, then:

```bash
docker-compose down
```

To also clear the database and start fresh:
```bash
docker-compose down -v
rm -f data/aurabrief.db
```

---

## 🔄 How to Restart After Stopping

```bash
docker-compose up
```

> No `--build` needed unless code changed. If you pulled new code from GitHub:
> ```bash
> git pull origin main
> docker-compose up --build
> ```

---

## 🔧 Troubleshooting

### Problem: "Cannot connect to the Docker daemon"
**Fix:** Open Docker Desktop and wait for it to fully start.

### Problem: Frontend shows "Backend Offline" or "Connection Error"
**Fix:** The backend takes ~15 seconds to start. Refresh the page after waiting.

### Problem: AI summaries show "Template Fallback" instead of real AI text
**Fix:** Ollama is not reachable. Check:
```bash
# Is Ollama running?
ollama list

# Can Docker reach it?
docker exec -it ascend-round2-team9-backend-1 curl http://host.docker.internal:11434/api/tags
```
If the second command fails, check your `.env` file's `OLLAMA_HOST` value.

### Problem: "Port 8000 already in use" or "Port 5173 already in use"
**Fix:** Something else is using that port. Kill it:
```bash
# Windows
netstat -ano | findstr :8000
taskkill /PID <PID_NUMBER> /F

# Mac/Linux
lsof -i :8000
kill -9 <PID>
```

### Problem: Simulator not sending events
**Fix:** The simulator waits for the backend health check to pass first (~15 seconds). Check:
```bash
docker-compose logs simulator
```

### Problem: "OCI runtime create failed" or Docker build errors
**Fix:** Rebuild from scratch:
```bash
docker-compose down -v
docker system prune -f
docker-compose up --build
```

---

## 📊 Architecture Overview

```
┌──────────────────┐     ┌───────────────────┐     ┌──────────────┐
│   Simulator      │────▶│   Backend (API)    │◀────│   Ollama     │
│   Port: internal │     │   Port: 8000       │     │   Port: 11434│
│   Sends events   │     │   FastAPI + SQLite  │     │   LLM Engine │
└──────────────────┘     └────────┬────────────┘     └──────────────┘
                                  │
                         ┌────────▼────────────┐
                         │   Frontend (UI)     │
                         │   Port: 5173        │
                         │   React + Vite      │
                         └─────────────────────┘
```

**Data Flow:**
1. **Simulator** generates fake cloud events every 5 seconds → POSTs to Backend
2. **Backend** scores events using 5-factor ranking → asks Ollama for AI explanations
3. **Frontend** fetches ranked events from Backend → displays dashboard to operator
4. **Operator** adjusts weights via sliders → Backend re-ranks in real-time

---

## 📱 Quick Reference Commands

| Action | Command |
|--------|---------|
| Start everything | `docker-compose up --build` |
| Start (no rebuild) | `docker-compose up` |
| Stop everything | `Ctrl+C` then `docker-compose down` |
| View backend logs | `docker-compose logs backend` |
| View frontend logs | `docker-compose logs frontend` |
| View simulator logs | `docker-compose logs simulator` |
| Reset database | `docker-compose down -v && rm -f data/aurabrief.db` |
| Pull latest code | `git pull origin main` |
| Check backend health | `curl http://localhost:8000/api/health` |
| Open dashboard | Browser → `http://localhost:5173` |
