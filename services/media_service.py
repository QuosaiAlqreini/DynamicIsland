import asyncio
import datetime
import threading
from PyQt6.QtCore import QObject, pyqtSignal, QTimer

try:
    import winsdk.windows.media.control as wmc
    HAS_WINSDK = True
except ImportError:
    HAS_WINSDK = False

DEMO_TRACKS = [
    {"title": "Starboy (feat. Daft Punk)", "artist": "The Weeknd", "source": "Spotify"},
    {"title": "Midnight City", "artist": "M83", "source": "Apple Music"},
    {"title": "Resonance", "artist": "HOME", "source": "YouTube Music"},
    {"title": "After Dark", "artist": "Mr.Kitty", "source": "SoundCloud"}
]

class MediaService(QObject):
    """Windows media session (Spotify, browsers, ...) with a demo fallback.

    All WinRT calls run on a background thread with one persistent asyncio
    loop, so the UI never waits for Windows. Results come back via a queued
    Qt signal.
    """
    media_updated = pyqtSignal(dict)
    art_changed = pyqtSignal(object)          # QPixmap of the album cover, or None
    _native_done = pyqtSignal(str, object)   # (kind, result)

    def __init__(self, interval_ms=1200):
        super().__init__()
        self.interval_ms = interval_ms
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._poll_media)

        self.is_playing = False
        self.demo_index = 0
        self.current_media = {
            "title": "No Media Playing",
            "artist": "Windows Media System",
            "is_playing": False,
            "has_media": False,
            "source": "Windows",
            "position_sec": 0,
            "duration_sec": 180
        }
        self._manager = None
        self._art_key = None                  # track the current cover belongs to
        self._poll_pending = False
        self._loop = None
        self._native_done.connect(self._on_native_done)
        if HAS_WINSDK:
            self._loop = asyncio.new_event_loop()
            threading.Thread(target=self._loop.run_forever, name="media-winrt", daemon=True).start()

    def start(self):
        self._poll_media()
        self.timer.start(self.interval_ms)

    def stop(self):
        self.timer.stop()

    # ------------------------------------------------------------ plumbing
    def _submit(self, kind, coro):
        """Run a coroutine on the media thread; result arrives in _on_native_done."""
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)

        def done(f):
            try:
                result = f.result()
            except Exception:
                result = None
            self._native_done.emit(kind, result)
        future.add_done_callback(done)

    def _on_native_done(self, kind, result):
        if kind == "poll":
            self._poll_pending = False
            if result:
                art = result.pop("_art", None)
                key = f"{result.get('artist')}|{result.get('title')}"
                if key != self._art_key and art is not None:
                    self._art_key = key
                    self.art_changed.emit(self._pixmap(art))
                self.current_media = result
            elif self._art_key is not None:
                self._art_key = None
                self.art_changed.emit(None)
            self.media_updated.emit(self.current_media)
            return
        # Transport buttons: refresh on success, otherwise use the demo fallback
        if result:
            QTimer.singleShot(250, self._poll_media)
        else:
            {"play_pause": self._demo_play_pause, "next": self._demo_next,
             "prev": self._demo_prev}[kind]()

    async def _session(self):
        if self._manager is None:
            self._manager = await wmc.GlobalSystemMediaTransportControlsSessionManager.request_async()
        return self._manager.get_current_session()

    # ---------------------------------------------------------------- poll
    def _poll_media(self):
        if self._loop is not None:
            if not self._poll_pending:
                self._poll_pending = True
                self._submit("poll", self._get_native_media())
            return
        self.media_updated.emit(self.current_media)

    async def _get_native_media(self):
        try:
            session = await self._session()
            if not session:
                return None

            info = await session.try_get_media_properties_async()
            playback_info = session.get_playback_info()

            status = playback_info.playback_status if playback_info else None
            is_playing = (status == wmc.GlobalSystemMediaTransportControlsSessionPlaybackStatus.PLAYING) if status else False

            timeline = session.get_timeline_properties()
            pos = timeline.position.total_seconds() if timeline and timeline.position else 0
            dur = timeline.end_time.total_seconds() if timeline and timeline.end_time else 180
            # Players report position only now and then: add the time since that report
            try:
                updated = timeline.last_updated_time if timeline else None
                if is_playing and updated is not None and updated.year > 2000:
                    elapsed = (datetime.datetime.now(datetime.timezone.utc) - updated).total_seconds()
                    if 0 <= elapsed < max(dur, 1):
                        pos = min(pos + elapsed, dur)
            except Exception:
                pass

            # Album cover: read once per track (the poll repeats every second)
            art = None
            key = f"{info.artist or 'Unknown Artist'}|{info.title or 'Unknown Track'}"
            if key != self._art_key:
                art = b""
                try:
                    if info.thumbnail is not None:
                        art = await self._read_thumbnail(info.thumbnail)
                except Exception:
                    art = b""

            app_id = session.source_app_user_model_id or "Player"
            app_name = app_id.split("!")[-1] if "!" in app_id else app_id
            if "Spotify" in app_name:
                app_name = "Spotify"
            elif "Chrome" in app_name:
                app_name = "Chrome"
            elif "Edge" in app_name:
                app_name = "Edge"

            return {
                "title": info.title or "Unknown Track",
                "artist": info.artist or "Unknown Artist",
                "album": info.album_title or "",
                "is_playing": is_playing,
                "has_media": True,
                "source": app_name,
                "position_sec": int(pos),
                "position": float(pos),
                "duration_sec": int(dur) if dur > 0 else 180,
                "_art": art,
            }
        except Exception:
            self._manager = None  # re-acquire next time
            return None

    @staticmethod
    async def _read_thumbnail(thumb_ref):
        from winsdk.windows.storage.streams import Buffer, InputStreamOptions, DataReader
        stream = await thumb_ref.open_read_async()
        size = int(stream.size)
        if not size or size > 8_000_000:
            return b""
        buf = Buffer(size)
        await stream.read_async(buf, size, InputStreamOptions.READ_AHEAD)
        try:
            return bytes(memoryview(buf))
        except TypeError:
            reader = DataReader.from_buffer(buf)
            data = bytearray(buf.length)
            reader.read_bytes(data)
            return bytes(data)

    @staticmethod
    def _pixmap(data):
        from PyQt6.QtGui import QPixmap
        if not data:
            return None
        pm = QPixmap()
        return pm if pm.loadFromData(data) else None

    # ----------------------------------------------------------- controls
    async def _transport(self, method):
        try:
            session = await self._session()
            if session:
                await getattr(session, method)()
                return True
        except Exception:
            self._manager = None
        return False

    def toggle_play_pause(self):
        if self._loop is not None:
            self._submit("play_pause", self._transport("try_toggle_play_pause_async"))
        else:
            self._demo_play_pause()

    def next_track(self):
        if self._loop is not None:
            self._submit("next", self._transport("try_skip_next_async"))
        else:
            self._demo_next()

    def previous_track(self):
        if self._loop is not None:
            self._submit("prev", self._transport("try_skip_previous_async"))
        else:
            self._demo_prev()

    # --------------------------------------------------------------- demo
    def _demo_play_pause(self):
        self.current_media["is_playing"] = not self.current_media.get("is_playing", False)
        if not self.current_media.get("has_media"):
            track = DEMO_TRACKS[self.demo_index]
            self.current_media.update({
                "title": track["title"],
                "artist": track["artist"],
                "source": track["source"],
                "has_media": True
            })
        self.media_updated.emit(self.current_media)

    def _demo_step(self, step):
        self.demo_index = (self.demo_index + step) % len(DEMO_TRACKS)
        track = DEMO_TRACKS[self.demo_index]
        self.current_media.update({
            "title": track["title"],
            "artist": track["artist"],
            "source": track["source"],
            "is_playing": True,
            "has_media": True
        })
        self.media_updated.emit(self.current_media)

    def _demo_next(self):
        self._demo_step(1)

    def _demo_prev(self):
        self._demo_step(-1)
