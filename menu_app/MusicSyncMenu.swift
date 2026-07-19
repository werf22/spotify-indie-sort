import AppKit
import SwiftUI

private let projectRoot = "/Users/jakub/Appky Claude/spotify-indie-sort"
private let pythonPath = projectRoot + "/.venv/bin/python"

struct SyncSnapshot: Codable {
    let tracksTotal: Int
    let localTracksMatched: Int
    let localTracksDeepVerified: Int
    let localTracksQuickVerified: Int
    let queue: [String: Int]
    let rhythm: Int
    let maest: Int
    let clap: Int
    let freqblogSuccess: Int
    let blindspotExported: Int
    let freeGib: Double
    let minFreeGib: Double
    let estimatedRemainingAudioGib: Double
    let outputRoot: String
    let acquisitionPaused: Bool
    let pauseReason: String?
    let daemonRunning: Bool
}

@MainActor
final class StatusModel: ObservableObject {
    @Published var status: SyncSnapshot?
    @Published var error: String?
    private var timer: Timer?

    init() {
        refresh()
        timer = Timer.scheduledTimer(withTimeInterval: 8, repeats: true) { [weak self] _ in
            Task { @MainActor in self?.refresh() }
        }
    }

    private func process(_ script: String, _ arguments: [String]) throws -> Data {
        let task = Process()
        let pipe = Pipe()
        task.executableURL = URL(fileURLWithPath: pythonPath)
        task.arguments = [projectRoot + "/" + script] + arguments
        task.currentDirectoryURL = URL(fileURLWithPath: projectRoot)
        task.standardOutput = pipe
        task.standardError = pipe
        try task.run()
        task.waitUntilExit()
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        guard task.terminationStatus == 0 else {
            throw NSError(domain: "MusicSync", code: Int(task.terminationStatus),
                          userInfo: [NSLocalizedDescriptionKey: String(data: data, encoding: .utf8) ?? "Command failed"])
        }
        return data
    }

    func refresh() {
        do {
            let data = try process("sync_status.py", ["--json"])
            let decoder = JSONDecoder()
            decoder.keyDecodingStrategy = .convertFromSnakeCase
            status = try decoder.decode(SyncSnapshot.self, from: data)
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
    }

    func control(_ command: String) {
        do {
            _ = try process("sync_control.py", [command])
            refresh()
        } catch {
            self.error = error.localizedDescription
        }
    }

    func runInventory() {
        let task = Process()
        task.executableURL = URL(fileURLWithPath: pythonPath)
        task.arguments = [projectRoot + "/sync_library_inventory.py"]
        task.currentDirectoryURL = URL(fileURLWithPath: projectRoot)
        try? task.run()
    }
}

struct MenuContent: View {
    @ObservedObject var model: StatusModel

    var body: some View {
        if let s = model.status {
            VStack(alignment: .leading, spacing: 7) {
                Text("Music Library Sync").font(.headline)
                Text(s.daemonRunning ? "● Beží" : "● Zastavené")
                    .foregroundStyle(s.daemonRunning ? .green : .red)
                ProgressView(value: Double(s.localTracksDeepVerified), total: Double(max(s.tracksTotal, 1)))
                    .frame(width: 250)
                Text("Lokálne spárované: \(s.localTracksMatched.formatted()) / \(s.tracksTotal.formatted())")
                Text("Overené celé súbory: \(s.localTracksDeepVerified.formatted())")
                Text("Treba zdroj: \((s.queue["needs_source"] ?? 0).formatted())")
                Text("Treba nájsť existujúce: \((s.queue["locate_existing"] ?? 0).formatted())")
                Divider()
                Text("Beat / MAEST / CLAP: \(s.rhythm.formatted()) / \(s.maest.formatted()) / \(s.clap.formatted())")
                Text("FreqBlog: \(s.freqblogSuccess.formatted())")
                Text("Blindspot playlisty: \(s.blindspotExported.formatted())")
                Divider()
                Text("Disk: \(s.freeGib, specifier: "%.1f") GiB voľných")
                    .foregroundStyle(s.freeGib <= s.minFreeGib ? .red : .primary)
                Text("Poistka: \(s.minFreeGib, specifier: "%.0f") GiB")
                Text("Odhad chýbajúceho 320 kbps audia: \(s.estimatedRemainingAudioGib, specifier: "%.0f") GiB")
                    .font(.caption)
                if s.acquisitionPaused {
                    Text("Acquisition pozastavený: \(s.pauseReason ?? "manual")").foregroundStyle(.orange)
                }
                Divider()
                HStack {
                    Button("Pause all") { model.control("pause-all") }
                    Button("Resume") { model.control("resume-all") }
                    Button("Refresh") { model.refresh() }
                }
                Button("Prepočítať Spotify ↔ Traktor ↔ lokálne") { model.runInventory() }
                Button("Otvoriť projekt") {
                    NSWorkspace.shared.open(URL(fileURLWithPath: projectRoot))
                }
                Button("Otvoriť log") {
                    NSWorkspace.shared.open(URL(fileURLWithPath: projectRoot + "/data/enrichment_supervisor.log"))
                }
                Divider()
                Button("Ukončiť menu app") { NSApplication.shared.terminate(nil) }
            }
            .padding(8)
        } else {
            Text(model.error ?? "Načítavam stav…").padding(8)
            Button("Refresh") { model.refresh() }
            Button("Ukončiť") { NSApplication.shared.terminate(nil) }
        }
    }
}

@main
struct MusicSyncMenuApp: App {
    @StateObject private var model = StatusModel()

    var body: some Scene {
        MenuBarExtra("Music Library Sync", systemImage: model.status?.daemonRunning == true ? "waveform.circle.fill" : "pause.circle") {
            MenuContent(model: model)
        }
        .menuBarExtraStyle(.window)
    }
}
