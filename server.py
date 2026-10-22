"""
Author: Claude Opus 5.5 Medium
Date: 22-October-2026
PURPOSE: The studio's local web server (only reachable from this Mac). It serves the studio window
(web/index.html) and a small set of actions: list songs, render, save the window's volume mix into
the song file, receive a recorded take, drop a take, and import a song to split. A watcher thread
re-renders any song whose file changed, so when Claude edits a song in plain-word rounds, the open
window picks up the new version by itself. Python standard library only.
Run: python3 server.py, then open http://localhost:8765
SRP/DRY check: Pass - HTTP plumbing only; reading, rendering, editing, takes and importing all live
in the band package.
"""

import json
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from band import edit, importer, voice
from band.render import OUT, render
from band.song import SongError, load_song

STUDIO = Path(__file__).resolve().parent
SONGS = STUDIO / "songs"
WEB = STUDIO / "web"
PORT = 8765
TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css",
         ".wav": "audio/wav", ".mp3": "audio/mpeg", ".json": "application/json"}

locks = {}            # song name -> lock, so one song never renders twice at once
errors = {}           # song name -> last render problem, shown in the window
jobs = {}             # song name -> what's happening right now ("rendering", "importing")


def lock_for(name):
    return locks.setdefault(name, threading.Lock())


def song_path(name: str) -> Path:
    path = (SONGS / f"{name}.toml").resolve()
    if path.parent != SONGS.resolve() or not path.exists():
        raise FileNotFoundError(f"no song called {name}")
    return path


def info_for(name: str):
    f = OUT / name / "info.json"
    return json.loads(f.read_text()) if f.exists() else None


def do_render(name: str):
    with lock_for(name):
        jobs[name] = "rendering"
        try:
            render(load_song(song_path(name)), name)
            errors.pop(name, None)
        except (SongError, RuntimeError, FileNotFoundError) as e:
            errors[name] = str(e)
        except Exception as e:   # a crash still shouldn't take the server down
            errors[name] = f"render crashed: {e}"
            traceback.print_exc()
        finally:
            jobs.pop(name, None)


def watcher():
    """Re-render songs whose files changed (Claude's edits, or the Boss's)."""
    while True:
        for f in sorted(SONGS.glob("*.toml")):
            name = f.stem
            if name in jobs:
                continue
            mtime = f.stat().st_mtime
            info = info_for(name)
            if (info is None or info.get("song_mtime") != mtime) and errors.get(name + ":mtime") != mtime:
                do_render(name)
                if name in errors:
                    errors[name + ":mtime"] = mtime   # don't retry a broken file until it changes
        time.sleep(1.5)


def song_state(name: str) -> dict:
    path = song_path(name)
    info = info_for(name) or {}
    state = {"name": name, "text": path.read_text(), "info": info, "job": jobs.get(name),
             "error": errors.get(name), "volumes": {}}
    try:
        song = load_song(path)
        state["volumes"] = {**{t.name: t.volume for t in song.tracks.values()},
                            **{v.name: v.volume for v in song.voices.values()}}
        state["voices"] = list(song.voices)
    except SongError as e:
        state["error"] = str(e)
    return state


def save_mix(name: str, gains: dict):
    """Fold the window's slider positions into the song file's volumes."""
    path = song_path(name)
    song = load_song(path)
    for stem, gain in gains.items():
        gain = float(gain)
        if stem in song.tracks:
            edit.set_value(path, f"tracks.{stem}", "volume", round(min(1.0, song.tracks[stem].volume * gain), 3))
        elif stem in song.voices:
            base = song.voices[stem].volume or 1.0   # a muted voice's stem plays at full level
            edit.set_value(path, f"voices.{stem}", "volume", round(min(2.0, base * gain), 3))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, code, body, kind="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def fail(self, e, code=400):
        self.send(code, {"error": str(e)})

    def body(self) -> bytes:
        return self.rfile.read(int(self.headers.get("Content-Length", 0)))

    def do_GET(self):
        url = urlparse(self.path)
        parts = [unquote(p) for p in url.path.strip("/").split("/") if p]
        try:
            if not parts:
                return self.static(WEB / "index.html")
            if parts[0] == "api" and parts[1:2] == ["songs"]:
                return self.send(200, [{"name": f.stem, "title": (info_for(f.stem) or {}).get("title", f.stem),
                                        "job": jobs.get(f.stem), "error": errors.get(f.stem)}
                                       for f in sorted(SONGS.glob("*.toml"))])
            if parts[0] == "api" and parts[1:2] == ["song"] and len(parts) == 3:
                return self.send(200, song_state(parts[2]))
            if parts[0] == "audio" and len(parts) >= 3:
                base = (OUT / parts[1]).resolve()
                target = (base / "/".join(parts[2:])).resolve()
                if base not in target.parents:
                    return self.fail("not allowed", 403)
                return self.static(target)
            return self.static(WEB / "/".join(parts))
        except FileNotFoundError as e:
            self.fail(e, 404)

    def static(self, path: Path):
        path = path.resolve()
        if not path.is_file():
            return self.fail("not found", 404)
        self.send(200, path.read_bytes(), TYPES.get(path.suffix, "application/octet-stream"))

    def do_POST(self):
        url = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        parts = [unquote(p) for p in url.path.strip("/").split("/") if p]
        try:
            action = parts[1] if len(parts) > 1 and parts[0] == "api" else None
            if action == "render":
                do_render(parts[2])
                return self.send(200, song_state(parts[2]))
            if action == "save-mix":
                name = parts[2]
                with lock_for(name):
                    save_mix(name, json.loads(self.body())["gains"])
                do_render(name)
                return self.send(200, song_state(name))
            if action == "take":
                name = parts[2]
                with lock_for(name):
                    song = load_song(song_path(name))
                    take = voice.save_take(song, name, self.body(), int(q["rate"]), float(q["start"]))
                do_render(name)
                return self.send(200, {**song_state(name), "take": take})
            if action == "drop-voice":
                name, which = parts[2], parts[3]
                with lock_for(name):
                    edit.remove_table(song_path(name), f"voices.{which}")
                do_render(name)
                return self.send(200, song_state(name))
            if action == "import":
                upload_dir = OUT / "_uploads"
                upload_dir.mkdir(parents=True, exist_ok=True)
                filename = Path(unquote(self.headers.get("X-Filename", "song.mp3"))).name
                src = upload_dir / filename
                src.write_bytes(self.body())
                jobs["_import"] = f"importing {filename}"
                try:
                    song_file = importer.import_song(src, q.get("title") or None)
                finally:
                    jobs.pop("_import", None)
                do_render(song_file.stem)
                return self.send(200, song_state(song_file.stem))
            self.fail("unknown action", 404)
        except (SongError, RuntimeError, FileExistsError, FileNotFoundError, KeyError, ValueError) as e:
            self.fail(e)
        except Exception as e:
            traceback.print_exc()
            self.fail(f"something broke: {e}", 500)


def main():
    threading.Thread(target=watcher, daemon=True).start()
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"studio running at http://localhost:{PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
