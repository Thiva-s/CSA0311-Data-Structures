# Emergency Routing Control Center

Web-based conversion of the original `emergency_routing.c` assignment.

## Run

```bash
cd emergency_routing_web
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open <http://127.0.0.1:5000> in a browser.

## Features

- Generates a connected, weighted road network.
- Finds shortest routes with Dijkstra's algorithm and a binary min-heap.
- Caches repeated `(source, destination)` queries.
- Updates road travel times and invalidates cached routes.
- Provides JSON endpoints at `/api/stats`, `/api/generate`, `/api/route`, and `/api/traffic`.
