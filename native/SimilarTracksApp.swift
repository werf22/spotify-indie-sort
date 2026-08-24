// Similar Tracks — a real macOS application.
//
// WHY THIS EXISTS: the app used to be a page on localhost, and that cost the one
// thing that matters during a set — a browser is forbidden to hand a filesystem
// path to another application, so dragging a track into Traktor could never
// work. A native window can do it, so the app is now native and the drag is a
// genuine NSDraggingSession carrying file URLs: exactly what Finder does, and
// indistinguishable from it to Traktor.
//
// WHAT IS NATIVE AND WHAT IS NOT: the window, the drag, the process lifecycle
// and the menu are AppKit. The interface inside the window is the same HTML the
// app already had, hosted in a WKWebView — rewriting 77 signal rows, profiles,
// presets and panels into AppKit would take weeks and change nothing the owner
// can see. The parts that a web view genuinely cannot do are taken over here.
//
// HOW TO TWEAK:
//   PORT        the local engine's port
//   DRAG_SLOP   how far the mouse must move before a click becomes a drag (px)
// Rebuild with native/build.sh after any change.

import AppKit
import WebKit

let PORT = 8765
let DRAG_SLOP: CGFloat = 5.0

// MARK: - the window's content view, which is also the drag source

final class HostView: NSView, NSDraggingSource {
    var armedPaths: [String] = []
    var armedFrom = NSPoint.zero
    var armed = false
    var onDrag: ((String) -> Void)?

    func arm(paths: [String], at point: NSPoint) {
        armedPaths = paths
        armedFrom = point
        armed = !paths.isEmpty
    }

    func disarm() { armed = false; armedPaths = [] }

    /// Turns the armed selection into a real file drag. Called from the mouse
    /// monitor once the pointer has actually moved, so a plain click still
    /// clicks and a click-drag over the checkbox column still selects rows.
    func startDrag(with event: NSEvent) {
        guard armed, !armedPaths.isEmpty else { return }
        armed = false
        var items: [NSDraggingItem] = []
        let origin = convert(event.locationInWindow, from: nil)
        for (i, path) in armedPaths.enumerated() {
            guard FileManager.default.fileExists(atPath: path) else { continue }
            let item = NSDraggingItem(pasteboardWriter: URL(fileURLWithPath: path) as NSURL)
            let icon = NSWorkspace.shared.icon(forFile: path)
            icon.size = NSSize(width: 32, height: 32)
            let step = CGFloat(min(i, 5)) * 4
            item.setDraggingFrame(NSRect(x: origin.x - 16 + step, y: origin.y - 16 - step,
                                         width: 32, height: 32), contents: icon)
            items.append(item)
        }
        guard !items.isEmpty else { onDrag?("startDrag: NIČ — žiadny zo súborov neexistuje"); return }
        onDrag?("startDrag: \(items.count) file(s) — natívna session spustená")
        beginDraggingSession(with: items, event: event, source: self)
    }

    func draggingSession(_ session: NSDraggingSession,
                         sourceOperationMaskFor context: NSDraggingContext) -> NSDragOperation {
        return .copy            // never move the owner's music, only reference it
    }
}

// MARK: - application

final class App: NSObject, NSApplicationDelegate, WKScriptMessageHandler,
                 WKNavigationDelegate, WKUIDelegate {
    var window: NSWindow!
    var host: HostView!
    var web: WKWebView!
    var server: Process?
    var monitor: Any?
    let status = NSTextField(labelWithString: "spúšťam engine…")

    // The .app sits in the project folder, so the project is one level up.
    var root: URL { Bundle.main.bundleURL.deletingLastPathComponent() }

    func applicationDidFinishLaunching(_ note: Notification) {
        buildMenu()

        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1440, height: 900),
                          styleMask: [.titled, .closable, .miniaturizable, .resizable],
                          backing: .buffered, defer: false)
        window.title = "Similar Tracks"
        window.setFrameAutosaveName("SimilarTracksWindow")
        window.minSize = NSSize(width: 900, height: 560)

        host = HostView(frame: window.contentLayoutRect)
        host.autoresizingMask = [.width, .height]
        host.onDrag = { [weak self] in self?.note($0) }
        host.wantsLayer = true
        host.layer?.backgroundColor = NSColor(calibratedRed: 0.063, green: 0.067, blue: 0.098, alpha: 1).cgColor

        status.frame = NSRect(x: 0, y: host.bounds.midY, width: host.bounds.width, height: 22)
        status.alignment = .center
        status.autoresizingMask = [.width, .minYMargin, .maxYMargin]
        status.textColor = NSColor(calibratedRed: 0.55, green: 0.58, blue: 0.70, alpha: 1)
        host.addSubview(status)

        let cfg = WKWebViewConfiguration()
        cfg.mediaTypesRequiringUserActionForPlayback = []       // play() without a click
        let ctl = WKUserContentController()
        ctl.add(self, name: "native")
        // Tell the page it is inside the native app, so it can hand drags over
        // to us instead of trying (and failing) to do them itself.
        ctl.addUserScript(WKUserScript(source: "window.NATIVE_HOST = true;",
                                       injectionTime: .atDocumentStart, forMainFrameOnly: true))
        cfg.userContentController = ctl
        cfg.preferences.setValue(true, forKey: "developerExtrasEnabled")

        web = WKWebView(frame: host.bounds, configuration: cfg)
        web.autoresizingMask = [.width, .height]
        web.navigationDelegate = self
        web.uiDelegate = self
        web.isHidden = true
        web.setValue(false, forKey: "drawsBackground")
        host.addSubview(web)

        window.contentView = host
        window.center()
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)

        // A drag is a mouse-down followed by movement. The page tells us what is
        // under the pointer; this is what notices the movement.
        monitor = NSEvent.addLocalMonitorForEvents(matching: [.leftMouseDragged]) { [weak self] ev in
            guard let self = self, self.host.armed else { return ev }
            let p = ev.locationInWindow
            if abs(p.x - self.host.armedFrom.x) > DRAG_SLOP || abs(p.y - self.host.armedFrom.y) > DRAG_SLOP {
                self.host.startDrag(with: ev)
                return nil                       // the drag owns the gesture now
            }
            return ev
        }

        startServer()
    }

    // MARK: engine process

    func startServer() {
        probe(attempt: 0, launched: false)
    }

    /// Wait for the engine, starting it if nothing answers. Reusing a running
    /// one matters: warming the audio index takes over two minutes and a second
    /// copy would just fight for the database.
    func probe(attempt: Int, launched: Bool) {
        var req = URLRequest(url: URL(string: "http://127.0.0.1:\(PORT)/api/similar/status")!)
        req.timeoutInterval = 2
        URLSession.shared.dataTask(with: req) { [weak self] data, _, _ in
            guard let self = self else { return }
            if let data = data,
               let j = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                let ready = (j["ready"] as? Bool) ?? false
                DispatchQueue.main.async {
                    if ready { self.load() }
                    else {
                        self.status.stringValue = "nahrávam audio odtlačky… (prvé spustenie trvá ~2 minúty)"
                        DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
                            self.probe(attempt: attempt + 1, launched: true)
                        }
                    }
                }
                return
            }
            DispatchQueue.main.async {
                if !launched { self.launchServer() }
                if attempt > 200 {
                    self.status.stringValue = "engine sa nespustil — pozri native/engine.log"
                    return
                }
                DispatchQueue.main.asyncAfter(deadline: .now() + 1) {
                    self.probe(attempt: attempt + 1, launched: true)
                }
            }
        }.resume()
    }

    func launchServer() {
        let python = root.appendingPathComponent(".venv/bin/python")
        let script = root.appendingPathComponent("music_app/server.py")
        guard FileManager.default.fileExists(atPath: python.path) else {
            status.stringValue = "chýba .venv — spusti najprv native/build.sh"
            return
        }
        let p = Process()
        p.executableURL = python
        p.arguments = [script.path]
        p.currentDirectoryURL = root
        let log = root.appendingPathComponent("native/engine.log")
        FileManager.default.createFile(atPath: log.path, contents: nil)
        if let h = try? FileHandle(forWritingTo: log) { p.standardOutput = h; p.standardError = h }
        do { try p.run(); server = p } catch {
            status.stringValue = "engine sa nepodarilo spustiť: \(error.localizedDescription)"
        }
    }

    func note(_ line: String) {
        let file = root.appendingPathComponent("native/app.log")
        let stamp = ISO8601DateFormatter().string(from: Date())
        guard let data = "\(stamp)  \(line)\n".data(using: .utf8) else { return }
        if let h = try? FileHandle(forWritingTo: file) {
            h.seekToEndOfFile(); h.write(data); try? h.close()
        } else { try? data.write(to: file) }
    }

    func load() {
        status.isHidden = true
        web.isHidden = false
        web.load(URLRequest(url: URL(string: "http://127.0.0.1:\(PORT)/similar")!))
    }

    func applicationWillTerminate(_ note: Notification) {
        // Leave nothing running behind the app; the engine holds the database.
        server?.terminate()
        if let m = monitor { NSEvent.removeMonitor(m) }
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ s: NSApplication) -> Bool { true }

    // MARK: the page talking to us

    func userContentController(_ c: WKUserContentController, didReceive msg: WKScriptMessage) {
        guard let body = msg.body as? [String: Any],
              let cmd = body["cmd"] as? String else { return }
        switch cmd {
        case "armDrag":
            let paths = (body["paths"] as? [String]) ?? []
            // Window coordinates, the same frame the drag monitor reports in.
            host.arm(paths: paths, at: window.mouseLocationOutsideOfEventStream)
            note("armDrag: \(paths.count) file(s), first=\(paths.first ?? "-")")
        case "disarmDrag":
            host.disarm()
        case "log":
            // The page reporting something from inside the web view. Without
            // this there is no way to see what the UI actually does in the app,
            // because its console is not the app's console.
            note((body["text"] as? String) ?? "")
        case "reveal":
            let paths = (body["paths"] as? [String]) ?? []
            NSWorkspace.shared.activateFileViewerSelecting(paths.map { URL(fileURLWithPath: $0) })
        default: break
        }
    }

    // Let the page use the microphone permission that device labels need.
    func webView(_ w: WKWebView, requestMediaCapturePermissionFor origin: WKSecurityOrigin,
                 initiatedByFrame frame: WKFrameInfo, type: WKMediaCaptureType,
                 decisionHandler: @escaping (WKPermissionDecision) -> Void) {
        decisionHandler(.grant)
    }

    func webView(_ w: WKWebView, didFail nav: WKNavigation!, withError error: Error) {
        status.isHidden = false
        status.stringValue = "stránka sa nenačítala: \(error.localizedDescription)"
    }

    // MARK: menu — without one, ⌘Q and ⌘R do nothing

    func buildMenu() {
        let main = NSMenu()
        let appItem = NSMenuItem()
        let appMenu = NSMenu()
        appMenu.addItem(withTitle: "O aplikácii Similar Tracks", action: #selector(NSApplication.orderFrontStandardAboutPanel(_:)), keyEquivalent: "")
        appMenu.addItem(.separator())
        appMenu.addItem(withTitle: "Znova načítať", action: #selector(reload), keyEquivalent: "r").target = self
        appMenu.addItem(.separator())
        appMenu.addItem(withTitle: "Skryť", action: #selector(NSApplication.hide(_:)), keyEquivalent: "h")
        appMenu.addItem(withTitle: "Ukončiť", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        appItem.submenu = appMenu
        main.addItem(appItem)

        let editItem = NSMenuItem()
        let edit = NSMenu(title: "Upraviť")
        edit.addItem(withTitle: "Vystrihnúť", action: #selector(NSText.cut(_:)), keyEquivalent: "x")
        edit.addItem(withTitle: "Kopírovať", action: #selector(NSText.copy(_:)), keyEquivalent: "c")
        edit.addItem(withTitle: "Prilepiť", action: #selector(NSText.paste(_:)), keyEquivalent: "v")
        edit.addItem(withTitle: "Označiť všetko", action: #selector(NSText.selectAll(_:)), keyEquivalent: "a")
        editItem.submenu = edit
        main.addItem(editItem)

        NSApp.mainMenu = main
    }

    @objc func reload() { web.reload() }
}

let app = NSApplication.shared
let delegate = App()
app.delegate = delegate
app.setActivationPolicy(.regular)
app.run()
