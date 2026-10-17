# HarvestLink

HarvestLink is a food donation and surplus redistribution network. Donors publish food with a quantity and pickup deadline; community groups can reserve it, mark it collected, and browse the live board. The app uses a Python HTTP backend and a SQLite database, so listings survive server restarts when deployed with the included Render persistent disk.

## Run locally (Windows / VS Code)

Requires Python 3.10 or newer. No third-party packages are needed.

1. Extract the ZIP to a normal folder, for example `D:\HarvestLink`.
2. Open that folder in VS Code.
3. Open **Terminal → New Terminal** and run:

   ```powershell
   python --version
   python server.py
   ```

4. Wait for the message that HarvestLink is running, then open <http://localhost:8000> in your browser.
5. Keep the terminal open while using the website. Press `Ctrl+C` in that terminal to stop the server.

The backend creates `data/harvestlink.sqlite3` on first run and adds demo listings to an empty database. Listings you create are stored locally and remain after server restarts. Set `PORT` and `DATA_DIR` to change the server port and database location.

On Windows, double-click `Start-HarvestLink.bat` to start the server in the background and open the site in your default browser. The launcher waits for the API to respond before opening the page.

## Features

- Live donation listings with category, status and text filters
- Create donations with server-side validation and pickup deadlines
- Reserve a listing for a community group, mark it collected, or relist it
- Server-side validation and protection against two groups reserving the same listing
- SQLite persistence and live dashboard counts
- Responsive layout for desktop and mobile
- Health endpoint at `/api/health`

## Deploy

The included `render.yaml` describes a Render web service with a persistent SQLite disk. Push this folder to a public GitHub or GitLab repository, then create a Render Blueprint from that repository. Render supplies the public URL after the service is deployed. Other hosts can run `python server.py`; make sure `DATA_DIR` points to durable storage before using the service for real donations.

## API

- `GET /api/donations` returns donation records and aggregate counts
- `POST /api/donations` validates and creates a listing
- `PATCH /api/donations/{id}/claim` reserves an available listing for a named group
- `PATCH /api/donations/{id}/status` updates status to `available`, `reserved`, or `collected`
- `GET /api/health` returns server health

This buildathon prototype has no user accounts. Anyone with access to the site can post donations and use the workflow buttons. Demo listings and contact details are illustrative. Do not publish real personal contact information or rely on this prototype for live food-safety operations without adding authentication, authorization, privacy controls, and appropriate food-handling procedures. A public deployment requires your own hosting account and Git repository.
