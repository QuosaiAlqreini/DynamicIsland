import asyncio
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
    media_updated = pyqtSignal(dict)

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

    def start(self):
        self._poll_media()
        self.timer.start(self.interval_ms)

    def stop(self):
        self.timer.stop()

    def _poll_media(self):
        if HAS_WINSDK:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                media_info = loop.run_until_complete(self._get_native_media())
                loop.close()
                if media_info:
                    self.current_media = media_info
                    self.media_updated.emit(self.current_media)
                    return
            except Exception:
                pass

        # If native media is idle or not present, emit current or demo state
        self.media_updated.emit(self.current_media)

    async def _get_native_media(self):
        try:
            manager = await wmc.GlobalSystemMediaTransportControlsSessionManager.request_async()
            session = manager.get_current_session()
            if not session:
                return None

            info = await session.try_get_media_properties_async()
            playback_info = session.get_playback_info()
            
            status = playback_info.playback_status if playback_info else None
            # 4 is Playing, 5 is Paused in Windows Media Control
            is_playing = (status == wmc.GlobalSystemMediaTransportControlsSessionPlaybackStatus.PLAYING) if status else False

            timeline = session.get_timeline_properties()
            pos = timeline.position.total_seconds() if timeline and timeline.position else 0
            dur = timeline.end_time.total_seconds() if timeline and timeline.end_time else 180

            app_id = session.source_app_user_model_id or "Player"
            # Clean up app id
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
                "duration_sec": int(dur) if dur > 0 else 180
            }
        except Exception:
            return None

    def toggle_play_pause(self):
        if HAS_WINSDK:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                success = loop.run_until_complete(self._native_play_pause())
                loop.close()
                if success:
                    self._poll_media()
                    return
            except Exception:
                pass

        # Demo toggle fallback
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

    async def _native_play_pause(self):
        try:
            manager = await wmc.GlobalSystemMediaTransportControlsSessionManager.request_async()
            session = manager.get_current_session()
            if session:
                await session.try_toggle_play_pause_async()
                return True
        except Exception:
            pass
        return False

    def next_track(self):
        if HAS_WINSDK:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                success = loop.run_until_complete(self._native_next())
                loop.close()
                if success:
                    self._poll_media()
                    return
            except Exception:
                pass

        # Demo next
        self.demo_index = (self.demo_index + 1) % len(DEMO_TRACKS)
        track = DEMO_TRACKS[self.demo_index]
        self.current_media.update({
            "title": track["title"],
            "artist": track["artist"],
            "source": track["source"],
            "is_playing": True,
            "has_media": True
        })
        self.media_updated.emit(self.current_media)

    async def _native_next(self):
        try:
            manager = await wmc.GlobalSystemMediaTransportControlsSessionManager.request_async()
            session = manager.get_current_session()
            if session:
                await session.try_skip_next_async()
                return True
        except Exception:
            pass
        return False

    def previous_track(self):
        if HAS_WINSDK:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                success = loop.run_until_complete(self._native_prev())
                loop.close()
                if success:
                    self._poll_media()
                    return
            except Exception:
                pass

        # Demo prev
        self.demo_index = (self.demo_index - 1) % len(DEMO_TRACKS)
        track = DEMO_TRACKS[self.demo_index]
        self.current_media.update({
            "title": track["title"],
            "artist": track["artist"],
            "source": track["source"],
            "is_playing": True,
            "has_media": True
        })
        self.media_updated.emit(self.current_media)

    async def _native_prev(self):
        try:
            manager = await wmc.GlobalSystemMediaTransportControlsSessionManager.request_async()
            session = manager.get_current_session()
            if session:
                await session.try_skip_previous_async()
                return True
        except Exception:
            pass
        return False
