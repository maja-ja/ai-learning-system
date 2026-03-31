import Foundation
import Combine

// Mac Catalyst 不支援 `FileManager.homeDirectoryForCurrentUser`。
private enum CursorSettingsHome {
    static var url: URL {
        #if targetEnvironment(macCatalyst)
        URL(fileURLWithPath: NSHomeDirectory(), isDirectory: true)
        #else
        FileManager.default.homeDirectoryForCurrentUser
        #endif
    }
}

// MARK: - Setting Entry

struct SettingEntry: Identifiable, Codable, Equatable {
    var id = UUID()
    var key: String
    var rawValue: String          // always stored as String, coerced on save
}

// MARK: - SettingsStore (iOS ObservableObject)

@MainActor
final class SettingsStore: ObservableObject {

    @Published private(set) var entries: [SettingEntry] = []
    @Published private(set) var saveStatus: SaveStatus = .idle

    enum SaveStatus: Equatable {
        case idle
        case saved
        case error(String)
    }

    // On iOS the app shows its own JSON file in Documents.
    // On macOS it reads the real Cursor settings.json.
    private var fileURL: URL {
        #if os(iOS)
        return FileManager.default
            .urls(for: .documentDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("cursor_settings.json")
        #else
        CursorSettingsHome.url
            .appendingPathComponent("Library/Application Support/Cursor/User/settings.json")
        #endif
    }

    // MARK: Load

    func load() {
        guard FileManager.default.fileExists(atPath: fileURL.path) else {
            entries = defaultEntries()
            return
        }
        do {
            let raw = try String(contentsOf: fileURL, encoding: .utf8)
            let cleaned = JsonCleaner.stripComments(from: raw)
            guard let data = cleaned.data(using: .utf8),
                  let dict = try JSONSerialization.jsonObject(with: data) as? [String: Any]
            else { return }

            entries = dict.sorted(by: { $0.key < $1.key }).map { key, value in
                SettingEntry(key: key, rawValue: stringify(value))
            }
        } catch {
            saveStatus = .error(error.localizedDescription)
        }
    }

    // MARK: Save

    func save() {
        var dict: [String: Any] = [:]
        for entry in entries {
            dict[entry.key] = parseValue(entry.rawValue)
        }
        do {
            let data = try JSONSerialization.data(
                withJSONObject: dict,
                options: [.prettyPrinted, .sortedKeys]
            )
            try data.write(to: fileURL, options: .atomic)
            saveStatus = .saved
            Task { try? await Task.sleep(for: .seconds(2)); saveStatus = .idle }
        } catch {
            saveStatus = .error(error.localizedDescription)
        }
    }

    // MARK: Mutations

    func add(_ entry: SettingEntry) {
        entries.append(entry)
        entries.sort { $0.key < $1.key }
        save()
    }

    func update(_ entry: SettingEntry) {
        if let i = entries.firstIndex(where: { $0.id == entry.id }) {
            entries[i] = entry
            save()
        }
    }

    func delete(at offsets: IndexSet) {
        entries.remove(atOffsets: offsets)
        save()
    }

    // MARK: Presets

    func applyPreset(_ preset: SettingPreset) {
        let (key, value) = preset.keyValue
        if let i = entries.firstIndex(where: { $0.key == key }) {
            entries[i].rawValue = value
        } else {
            entries.append(SettingEntry(key: key, rawValue: value))
            entries.sort { $0.key < $1.key }
        }
        save()
    }

    // MARK: Helpers

    private func stringify(_ value: Any) -> String {
        switch value {
        case let b as Bool:   return b ? "true" : "false"
        case let n as Int:    return "\(n)"
        case let d as Double: return "\(d)"
        case let s as String: return s
        default:
            if let data = try? JSONSerialization.data(withJSONObject: value, options: [.prettyPrinted]),
               let s = String(data: data, encoding: .utf8) { return s }
            return "\(value)"
        }
    }

    private func parseValue(_ raw: String) -> Any {
        if raw == "true"  { return true }
        if raw == "false" { return false }
        if raw == "null"  { return NSNull() }
        if let n = Int(raw)    { return n }
        if let d = Double(raw) { return d }
        if let data = raw.data(using: .utf8),
           let obj = try? JSONSerialization.jsonObject(with: data) { return obj }
        return raw
    }

    private func defaultEntries() -> [SettingEntry] {
        [
            SettingEntry(key: "editor.fontSize",       rawValue: "14"),
            SettingEntry(key: "editor.tabSize",        rawValue: "2"),
            SettingEntry(key: "editor.formatOnSave",   rawValue: "true"),
            SettingEntry(key: "editor.wordWrap",       rawValue: "on"),
            SettingEntry(key: "workbench.colorTheme",  rawValue: "Default Dark Modern"),
        ]
    }
}

// MARK: - JSON Comment Stripper (shared)

enum JsonCleaner {
    static func stripComments(from source: String) -> String {
        var result = ""
        var i = source.startIndex
        while i < source.endIndex {
            let c = source[i]
            let next = source.index(after: i)
            if c == "/" && next < source.endIndex && source[next] == "*" {
                var j = source.index(next, offsetBy: 1)
                while j < source.endIndex {
                    let jNext = source.index(after: j)
                    if source[j] == "*" && jNext < source.endIndex && source[jNext] == "/" {
                        i = source.index(jNext, offsetBy: 1); break
                    }
                    j = source.index(after: j)
                }
                continue
            }
            if c == "/" && next < source.endIndex && source[next] == "/" {
                while i < source.endIndex && source[i] != "\n" { i = source.index(after: i) }
                continue
            }
            result.append(c)
            i = source.index(after: i)
        }
        return result
    }
}

// MARK: - Preset enum

enum SettingPreset: String, CaseIterable, Identifiable {
    case fontSizeSmall  = "Font Size 13"
    case fontSizeMedium = "Font Size 15"
    case fontSizeLarge  = "Font Size 18"
    case formatOnSave   = "Format on Save"
    case noFormatOnSave = "No Format on Save"
    case darkTheme      = "Dark Theme"
    case lightTheme     = "Light Theme"
    case wordWrapOn     = "Word Wrap On"
    case wordWrapOff    = "Word Wrap Off"
    case hideMinimap    = "Hide Minimap"
    case showMinimap    = "Show Minimap"

    var id: String { rawValue }

    var keyValue: (key: String, value: String) {
        switch self {
        case .fontSizeSmall:  return ("editor.fontSize", "13")
        case .fontSizeMedium: return ("editor.fontSize", "15")
        case .fontSizeLarge:  return ("editor.fontSize", "18")
        case .formatOnSave:   return ("editor.formatOnSave", "true")
        case .noFormatOnSave: return ("editor.formatOnSave", "false")
        case .darkTheme:      return ("workbench.colorTheme", "Default Dark Modern")
        case .lightTheme:     return ("workbench.colorTheme", "Default Light Modern")
        case .wordWrapOn:     return ("editor.wordWrap", "on")
        case .wordWrapOff:    return ("editor.wordWrap", "off")
        case .hideMinimap:    return ("editor.minimap.enabled", "false")
        case .showMinimap:    return ("editor.minimap.enabled", "true")
        }
    }

    var icon: String {
        switch self {
        case .fontSizeSmall, .fontSizeMedium, .fontSizeLarge: return "textformat.size"
        case .formatOnSave, .noFormatOnSave: return "wand.and.stars"
        case .darkTheme, .lightTheme: return "paintpalette"
        case .wordWrapOn, .wordWrapOff: return "arrow.turn.down.left"
        case .hideMinimap, .showMinimap: return "map"
        }
    }
}
