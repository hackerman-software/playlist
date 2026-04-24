
# pip install rumps audioplayer pyobjc-framework-Quartz

from pathlib import Path

import objc
import Quartz
import rumps
from audioplayer import AudioPlayer

from AppKit import (
    NSApp,
    # NSImage,
    NSScreen,
    NSAlert,
    NSAlertStyleInformational,
    NSSystemDefined,
    # NSEvent,
    # NSEventMaskSystemDefined,
    NSWorkspace,
    NSWindow,
    NSView,
    NSTextField,
    NSColor,
    NSBackingStoreBuffered,
    NSWindowStyleMaskBorderless,
    NSDragOperationCopy,
    NSPasteboardTypeFileURL,
    NSBezierPath,
    NSFont,
    NSFontWeightSemibold,
    NSVisualEffectView,
    NSVisualEffectMaterialHUDWindow,
    NSVisualEffectBlendingModeBehindWindow,
    NSVisualEffectStateActive,
)
from Foundation import NSURL

from MediaPlayer import (
    MPRemoteCommandCenter,
    MPRemoteCommandHandlerStatusSuccess,
    MPRemoteCommandHandlerStatusCommandFailed,
    MPNowPlayingInfoCenter,
    MPMediaItemPropertyTitle,
    MPMediaItemPropertyArtist,
    MPNowPlayingInfoPropertyPlaybackRate,
)

AUDIO_EXTENSIONS = {
    ".mp3",
    ".wav",
    ".ogg",
    ".flac",
    ".m4a",
    ".aac",
}

# macOS media key constants
NX_KEYTYPE_PLAY = 16
NX_KEYTYPE_NEXT = 17
NX_KEYTYPE_PREVIOUS = 18
NX_KEYTYPE_FAST = 19
NX_KEYTYPE_REWIND = 20
NX_KEYDOWN = 0xA
NX_KEYUP = 0xB


class DropWindow(NSWindow):
    def canBecomeKeyWindow(self):
        return True

    def canBecomeMainWindow(self):
        return True

def nscolor_from_hex(hex_color: str, alpha: float = 1.0):
    hex_color = hex_color.lstrip("#")

    r = int(hex_color[0:2], 16) / 255.0
    g = int(hex_color[2:4], 16) / 255.0
    b = int(hex_color[4:6], 16) / 255.0

    return NSColor.colorWithCalibratedRed_green_blue_alpha_(r, g, b, alpha)


# FolderDropView
class FolderDropView(NSView):
    
    # FolderDropView : initWithCallback_closeCallback_
    def initWithCallback_closeCallback_(self, callback, close_callback):
        self = self.init()
        if self is None:
            return None
    
        self.callback = callback
        self.close_callback = close_callback
        self.hovering = False
        self.registerForDraggedTypes_([NSPasteboardTypeFileURL])
        return self

    # FolderDropView : isFlipped
    def isFlipped(self):
        return True
    
    # FolderDropView : acceptsFirstResponder
    def acceptsFirstResponder(self):
        return True
    
    # FolderDropView : acceptsFirstMouse_
    def acceptsFirstMouse_(self, event):
        return True
    
    # FolderDropView : mouseDown_
    def mouseDown_(self, event):
        self.window().performWindowDragWithEvent_(event)
    
    # FolderDropView : draggingEntered_
    def draggingEntered_(self, sender):
        if self._folder_from_drag(sender) is not None:
            self.hovering = True
            self.setNeedsDisplay_(True)
            return NSDragOperationCopy
        return 0
    
    # FolderDropView : draggingExited_
    def draggingExited_(self, sender):
        self.hovering = False
        self.setNeedsDisplay_(True)
    
    # FolderDropView : performDragOperation_
    def performDragOperation_(self, sender):
        self.hovering = False
        self.setNeedsDisplay_(True)

        folder = self._folder_from_drag(sender)
        if folder is None:
            return False

        self.callback(folder)
        return True
    
    # FolderDropView : drawRect_
    def drawRect_(self, rect):
        bounds = self.bounds()
        inset = 24
        drop_rect = (
            (inset, inset),
            (bounds.size.width - inset * 2, bounds.size.height - inset * 2),
        )
        drop_path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            drop_rect,
            12,
            12,
        )
        
        fill = nscolor_from_hex("#f174f2", 0.05)
        stroke = nscolor_from_hex("#f174f2", 0.5)

        fill.setFill()
        drop_path.fill()

        stroke.setStroke()
        drop_path.setLineWidth_(2.0)
        drop_path.setLineDash_count_phase_([8.0, 5.0], 2, 0.0)
        drop_path.stroke()
    
    # FolderDropView : _folder_from_drag
    def _folder_from_drag(self, sender):
        pasteboard = sender.draggingPasteboard()
        urls = pasteboard.readObjectsForClasses_options_([NSURL], None)

        if not urls:
            return None

        url = urls[0]

        if not url.isFileURL():
            return None

        path = Path(str(url.path())).expanduser()

        if path.exists() and path.is_dir():
            return path

        return None
    
    # FolderDropView : keyDown_
    def keyDown_(self, event):
        if event.keyCode() == 53: # Escape
            if hasattr(self, "close_callback") and self.close_callback is not None:
                self.close_callback()
            else:
                self.window().close()
            return
    
        objc.super(FolderDropView, self).keyDown_(event)


# PlaylistPlayerApp
class PlaylistPlayerApp(rumps.App):
    def __init__(self):
        super().__init__("▶", quit_button=None)

        self.folder: Path | None = None
        self.track_list: list[Path] = []

        self.current_index: int | None = None
        self.player: AudioPlayer | None = None
        self.paused = False
        
        self.playlist_menu = rumps.MenuItem("Playlist")
        
        self.about_item = rumps.MenuItem("About Playlist", callback=self.show_about)
        self.set_folder_item = rumps.MenuItem("Open playlist...", callback=self.set_playlist_folder)
        self.play_pause_item = rumps.MenuItem("Play / Pause", callback=self.play_pause)
        self.stop_item = rumps.MenuItem("Stop", callback=self.stop)
        self.previous_item = rumps.MenuItem("Previous", callback=lambda _: self.play_previous())
        self.next_item = rumps.MenuItem("Next", callback=lambda _: self.play_next())
        self.quit_item = rumps.MenuItem("Quit", callback=self.quit_app)
        
        self.menu = [
            self.set_folder_item,
            None,
            self.playlist_menu,
            None,
            self.play_pause_item,
            self.stop_item,
            self.previous_item,
            self.next_item,
            None,
            self.about_item,
            None,
            self.quit_item,
        ]
        
        self.playlist_menu.add(rumps.MenuItem("No tracks loaded", callback=None))
        
        self.media_event_tap = None
        self.media_run_loop_source = None
        self.setup_media_key_tap()
    
    # PlaylistPlayerApp : setup_media_key_tap
    def setup_media_key_tap(self):
        mask = Quartz.CGEventMaskBit(Quartz.NSSystemDefined)
    
        self.media_event_tap = Quartz.CGEventTapCreate(
            Quartz.kCGSessionEventTap,
            Quartz.kCGHeadInsertEventTap,
            Quartz.kCGEventTapOptionDefault,
            mask,
            self.handle_media_key_event_tap,
            None,
        )
    
        if self.media_event_tap is None:
            print("Could not create media key event tap. Grant Accessibility permission.")
            return
    
        self.media_run_loop_source = Quartz.CFMachPortCreateRunLoopSource(
            None,
            self.media_event_tap,
            0,
        )
    
        Quartz.CFRunLoopAddSource(
            Quartz.CFRunLoopGetCurrent(),
            self.media_run_loop_source,
            Quartz.kCFRunLoopCommonModes,
        )
    
        Quartz.CGEventTapEnable(self.media_event_tap, True)
    
    # PlaylistPlayerApp : handle_media_key_event_tap
    def handle_media_key_event_tap(self, proxy, event_type, event, refcon):
        if event_type != Quartz.NSSystemDefined:
            return event
    
        ns_event = Quartz.NSEvent.eventWithCGEvent_(event)
    
        if ns_event is None:
            return event
    
        # subtype 8 = media/special system keys
        if ns_event.subtype() != 8:
            return event
    
        data = ns_event.data1()
    
        key_code = (data >> 16) & 0xFFFF
        key_state = (data >> 8) & 0xFF
        
        # print("media key:", key_code, "state:", key_state)
    
        if key_state != NX_KEYDOWN:
            return None
    
        if key_code == NX_KEYTYPE_PLAY:
            self.play_pause(None)
            return None
        
        if key_code in (NX_KEYTYPE_NEXT, NX_KEYTYPE_FAST):
            self.play_next()
            return None
        
        if key_code in (NX_KEYTYPE_PREVIOUS, NX_KEYTYPE_REWIND):
            self.play_previous()
            return None
    
        return event
    
    # PlaylistPlayerApp : handle_media_key_event
    def handle_media_key_event(self, event):
        # subtype 8 = media keys / special system keys
        if event.subtype() != 8:
            return
    
        data = event.data1()
    
        key_code = (data & 0xFFFF0000) >> 16
        key_state = (data & 0x0000FF00) >> 8
    
        # 0xA = key down, 0xB = key up.
        # Only handle key down to avoid double-trigger.
        if key_state != 0xA:
            return
    
        if key_code == NX_KEYTYPE_PLAY:
            self.play_pause(None)
    
        elif key_code == NX_KEYTYPE_NEXT:
            self.play_next()
    
        elif key_code == NX_KEYTYPE_PREVIOUS:
            self.play_previous()        
    
    # PlaylistPlayerApp : show_about
    def show_about(self, _):
        alert = NSAlert.alloc().init()
        alert.setAlertStyle_(NSAlertStyleInformational)
        alert.setMessageText_("Playlist")
        alert.setInformativeText_("Version 0.1.0\n© 2026 Michael Sjoeberg")
    
        alert.addButtonWithTitle_("Website")
        alert.addButtonWithTitle_("Close")
    
        NSApp.activateIgnoringOtherApps_(True)
    
        window = alert.window()
        window.setLevel_(3)
    
        # Force layout so the alert has its final size before centering.
        window.layoutIfNeeded()
    
        self.center_window_on_main_screen(window)
    
        window.makeKeyAndOrderFront_(None)
    
        response = alert.runModal()
    
        if response == 1000:
            url = NSURL.URLWithString_("https://hackerman.ai")
            NSWorkspace.sharedWorkspace().openURL_(url)
            return True
    
        return True
    
    # PlaylistPlayerApp : center_window_on_main_screen
    def center_window_on_main_screen(self, window):
        screen = NSScreen.mainScreen()
        if screen is None:
            return
    
        screen_frame = screen.visibleFrame()
        window_frame = window.frame()
    
        x = screen_frame.origin.x + (screen_frame.size.width - window_frame.size.width) / 2
        y = screen_frame.origin.y + (screen_frame.size.height - window_frame.size.height) / 2
    
        window.setFrameOrigin_((x, y))
    
    # PlaylistPlayerApp : close_drop_folder_window
    def close_drop_folder_window(self):
        if getattr(self, "drop_window", None) is not None:
            try:
                self.drop_window.orderOut_(None)
            except:
                pass
    
    # PlaylistPlayerApp : destroy_drop_folder_window
    def destroy_drop_folder_window(self):
        if getattr(self, "drop_window", None) is not None:
            try:
                self.drop_window.orderOut_(None)
                self.drop_window.setContentView_(None)
                self.drop_window.close()
            except:
                pass
    
        self.drop_window = None
        self.drop_root = None
        self.drop_panel = None
        self.drop_view = None
        self.drop_labels = []
    
    # PlaylistPlayerApp : show_drop_folder_window
    def show_drop_folder_window(self):
        width = 460
        height = 460
        
        if getattr(self, "drop_window", None) is not None:
            NSApp.activateIgnoringOtherApps_(True)
            self.drop_window.center()
            self.drop_window.makeKeyAndOrderFront_(None)
            self.drop_window.makeFirstResponder_(self.drop_view)
            return
    
        self.drop_window = DropWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            ((0, 0), (width, height)),
            NSWindowStyleMaskBorderless,
            NSBackingStoreBuffered,
            False,
        )
    
        self.drop_window.setTitle_("Set Playlist Folder")
        self.drop_window.center()
        self.drop_window.setOpaque_(False)
        self.drop_window.setBackgroundColor_(NSColor.clearColor())
        self.drop_window.setHasShadow_(True)
        self.drop_window.setMovableByWindowBackground_(True)
    
        # Keeps it above normal windows, but not obnoxiously global.
        self.drop_window.setLevel_(3)
        
        self.drop_root = NSView.alloc().initWithFrame_(((0, 0), (width, height)))
        self.drop_root.setWantsLayer_(True)
        self.drop_root.layer().setBackgroundColor_(NSColor.clearColor().CGColor())
        
        panel_inset = 12
        panel_width = width - panel_inset * 2
        panel_height = height - panel_inset * 2
        
        self.drop_panel = NSVisualEffectView.alloc().initWithFrame_(
            (
                (panel_inset, panel_inset),
                (width - panel_inset * 2, height - panel_inset * 2),
            )
        )
        self.drop_panel.setMaterial_(NSVisualEffectMaterialHUDWindow)
        self.drop_panel.setBlendingMode_(NSVisualEffectBlendingModeBehindWindow)
        self.drop_panel.setState_(NSVisualEffectStateActive)
        self.drop_panel.setWantsLayer_(True)
        
        panel_layer = self.drop_panel.layer()
        panel_layer.setCornerRadius_(24)
        panel_layer.setMasksToBounds_(True)
        panel_layer.setBorderWidth_(1.0)
        panel_layer.setBorderColor_(
            NSColor.whiteColor().colorWithAlphaComponent_(0.14).CGColor()
        )
    
        self.drop_view = FolderDropView.alloc().initWithCallback_closeCallback_(
            self.load_playlist_folder,
            self.close_drop_folder_window,
        )
        self.drop_view.setFrame_(((0, 0), (panel_width, panel_height)))
        self.drop_view.setWantsLayer_(True)
        self.drop_view.layer().setBackgroundColor_(NSColor.clearColor().CGColor())
    
        title = NSTextField.alloc().initWithFrame_(((0, 96), (panel_width, 34)))
        title.setStringValue_("Drop folder here")
        title.setAlignment_(1)
        title.setEditable_(False)
        title.setSelectable_(False)
        title.setBezeled_(False)
        title.setDrawsBackground_(False)
        title.setFont_(NSFont.systemFontOfSize_weight_(22, NSFontWeightSemibold))
        title.setTextColor_(NSColor.labelColor())
    
        hint = NSTextField.alloc().initWithFrame_(((0, 198), (panel_width, 24)))
        hint.setStringValue_("MP3, WAV, OGG, FLAC, M4A, AAC")
        hint.setAlignment_(1)
        hint.setEditable_(False)
        hint.setSelectable_(False)
        hint.setBezeled_(False)
        hint.setDrawsBackground_(False)
        hint.setFont_(NSFont.systemFontOfSize_(11))
        # hint.setTextColor_(NSColor.tertiaryLabelColor())
        hint.setTextColor_(nscolor_from_hex("#f174f2", 0.5))
        
        self.drop_labels = [title, hint]
    
        self.drop_panel.addSubview_(self.drop_view)
        self.drop_root.addSubview_(self.drop_panel)
        
        self.drop_view.addSubview_(title)
        self.drop_view.addSubview_(hint)
    
        self.drop_window.setContentView_(self.drop_root)
        self.drop_window.contentView().setWantsLayer_(True)
        self.drop_window.contentView().layer().setBackgroundColor_(NSColor.clearColor().CGColor())
        NSApp.activateIgnoringOtherApps_(True)
        self.drop_window.makeKeyAndOrderFront_(None)
        self.drop_window.makeFirstResponder_(self.drop_view)
    
    # PlaylistPlayerApp : load_playlist_folder
    def load_playlist_folder(self, path: Path):
        if not path.exists() or not path.is_dir():
            rumps.alert("Invalid folder", f"Not a folder:\n{path}")
            return
    
        self.folder = path
        self.track_list = self.load_tracks(path)
    
        self.stop(None)
        self.current_index = None
        self.paused = False
    
        self.rebuild_playlist_menu()
        self.close_drop_folder_window()
    
        if not self.track_list:
            self.stop(None)
            self.rebuild_playlist_menu()
            rumps.alert("No tracks found", "No supported audio files found in that folder.")
            return
        
        self.play_track(0)
    
    # PlaylistPlayerApp : set_playlist_folder
    def set_playlist_folder(self, _):
        self.show_drop_folder_window()
    
    # PlaylistPlayerApp : load_tracks
    def load_tracks(self, folder: Path) -> list[Path]:
        tracks = []

        for path in folder.iterdir():
            if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS:
                tracks.append(path)

        tracks.sort(key=lambda p: p.name.lower())
        return tracks
    
    # PlaylistPlayerApp : rebuild_playlist_menu
    def rebuild_playlist_menu(self):
        if not self.track_list:
            self.playlist_menu.clear()
            self.playlist_menu.add(rumps.MenuItem("No tracks loaded", callback=None))
            return
    
        self.playlist_menu.clear()
    
        for index, track in enumerate(self.track_list):
            item = rumps.MenuItem(
                self.track_title(index),
                callback=self.make_track_callback(index),
            )
            self.playlist_menu.add(item)
    
    # PlaylistPlayerApp : track_title
    def track_title(self, index: int) -> str:
        track = self.track_list[index]

        if index == self.current_index:
            prefix = "⏸ " if self.paused else "▶ "
        else:
            prefix = ""

        return f"{prefix}{track.name}"
    
    # PlaylistPlayerApp : make_track_callback
    def make_track_callback(self, index: int):
        def callback(_):
            if index == self.current_index:
                self.play_pause(None)
            else:
                self.play_track(index)

        return callback
    
    # PlaylistPlayerApp : play_track
    def play_track(self, index: int):
        if index < 0 or index >= len(self.track_list):
            return

        self.stop(None)

        self.current_index = index
        self.paused = False

        track = self.track_list[index]

        try:
            self.player = AudioPlayer(str(track))
            self.player.play(block=False)
        except Exception as error:
            self.player = None
            rumps.alert("Playback error", str(error))
            return

        self.title = "⏸"
        self.rebuild_playlist_menu()
        self.update_now_playing()
        
    def update_now_playing(self):
        if self.current_index is None or not self.track_list:
            MPNowPlayingInfoCenter.defaultCenter().setNowPlayingInfo_(None)
            return
    
        track = self.track_list[self.current_index]
        info = {
            MPMediaItemPropertyTitle: track.stem,
            MPMediaItemPropertyArtist: self.folder.name if self.folder else "Playlist",
            MPNowPlayingInfoPropertyPlaybackRate: 0.0 if self.paused else 1.0,
        }
    
        MPNowPlayingInfoCenter.defaultCenter().setNowPlayingInfo_(info)
    
    # PlaylistPlayerApp : play_next
    def play_next(self):
        if not self.track_list:
            return
    
        if self.current_index is None:
            self.play_track(0)
            return
    
        next_index = (self.current_index + 1) % len(self.track_list)
        self.play_track(next_index)
    
    # PlaylistPlayerApp : play_previous
    def play_previous(self):
        if not self.track_list:
            return
    
        if self.current_index is None:
            self.play_track(0)
            return
    
        previous_index = (self.current_index - 1) % len(self.track_list)
        self.play_track(previous_index)

    # PlaylistPlayerApp : play_pause
    def play_pause(self, _):
        if not self.track_list:
            return

        if self.current_index is None:
            self.play_track(0)
            return

        if self.player is None:
            self.play_track(self.current_index)
            return

        try:
            if self.paused:
                self.player.resume()
                self.paused = False
                self.title = "⏸"
            else:
                self.player.pause()
                self.paused = True
                self.title = "▶"
        except Exception as error:
            rumps.alert("Playback error", str(error))

        self.rebuild_playlist_menu()
        self.update_now_playing()
    
    # PlaylistPlayerApp : stop
    def stop(self, _):
        if self.player is not None:
            try:
                self.player.stop()
            except:
                pass

        self.player = None
        self.paused = False
        self.title = "▶"

        self.rebuild_playlist_menu()
        self.update_now_playing()
    
    # PlaylistPlayerApp : quit_app
    def quit_app(self, _):
        self.stop(None)
        self.destroy_drop_folder_window()
        
        # center = MPRemoteCommandCenter.sharedCommandCenter()

        # for token in self.remote_command_tokens:
        #     try:
        #         center.playCommand().removeTarget_(token)
        #         center.pauseCommand().removeTarget_(token)
        #         center.togglePlayPauseCommand().removeTarget_(token)
        #         center.nextTrackCommand().removeTarget_(token)
        #         center.previousTrackCommand().removeTarget_(token)
        #     except Exception:
        #         pass
        
        # self.remote_command_tokens = []
        # MPNowPlayingInfoCenter.defaultCenter().setNowPlayingInfo_(None)
        
        if self.media_event_tap is not None:
            Quartz.CGEventTapEnable(self.media_event_tap, False)
            self.media_event_tap = None
            self.media_run_loop_source = None
        
        rumps.quit_application()


if __name__ == "__main__":
    PlaylistPlayerApp().run()

