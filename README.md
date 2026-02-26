# Spyfall-Simulation
# Spyfall – Multiplayer Web Edition

A web-based multiplayer Spyfall game where each player uses their own device.

## How to Play

1. One player **creates a room** and shares the 6-character room code
2. Other players **join** using the code on their own phones/tablets/laptops
3. The host **starts the game** — each player privately sees their role on their own screen
4. One random player is the **Spy** (they don't know the location)
5. Players take turns asking each other questions to find the spy
6. The spy tries to figure out the location without being caught
7. When ready, the host calls a **vote** — everyone picks who they think is the spy
8. If the spy is caught, they get **2 guesses** to name the location and still win

## Features

- **Individual devices**: No more passing a phone around
- **Location list**: All players can see the location list; the spy can mark/unmark locations to track eliminations
- **Per-player notes**: Every player gets a private notepad with a section for each other player
- **Timer**: Host can start/pause a configurable round timer
- **Reconnection**: If a player disconnects, they can rejoin with the same name
- **CSV locations**: Locations and roles are loaded from `locations.csv` — easy to edit without touching code
- **Docker ready**: One command to build and run

## Quick Start

### Option A: Docker (recommended for hosting)

```bash
docker compose up --build
```

Then open `http://<your-ip>:5000` on each player's device.

### Option B: Run directly with Python

```bash
pip install -r requirements.txt
python app.py
```

Server starts on `http://localhost:5000`.

### Hosting on your local network

Players on the same Wi-Fi can connect using your machine's local IP (e.g. `http://192.168.1.42:5000`). Find your IP with:

- **macOS**: `ipconfig getifaddr en0`
- **Linux**: `hostname -I`
- **Windows**: `ipconfig` → look for IPv4 Address

### Hosting publicly

For internet access, you can:

1. **Reverse proxy** (nginx/Caddy) + port forwarding on your router
2. **Cloud VM** (DigitalOcean, AWS, etc.) — just run the Docker container
3. **Tunneling** — `ngrok http 5000` or `cloudflared tunnel` for quick sharing

## Editing Locations

Open `locations.csv` and add/remove rows. Format:

```
location,roles
My New Place,"Role1,Role2,Role3,Role4,Role5,Role6"
```

The roles column is comma-separated inside quotes. The server loads this file on startup (and Docker mounts it as a volume, so edits don't need a rebuild, just restart the container).

## Project Structure

```
spyfall/
├── app.py                 # Flask + SocketIO server
├── locations.csv          # Location and role data
├── templates/
│   └── index.html         # Single-page frontend
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```
