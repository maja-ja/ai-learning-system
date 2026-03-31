import SwiftUI

struct SettingEntry: Identifiable, Codable, Equatable {
    var id = UUID()
    var key: String
    var rawValue: String
}

@MainActor
final class SettingsStore: ObservableObject {
    @Published private(set) var entries: [SettingEntry] = []
    @Published private(set) var saveStatus: SaveStatus = .idle

    enum SaveStatus: Equatable {
        case idle
        case saved
        case error(String)
    }

    private var fileURL: URL {
        FileManager.default
            .urls(for: .documentDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("cursor_settings.json")
    }

    func load() {
        guard FileManager.default.fileExists(atPath: fileURL.path) else {
            entries = [
                SettingEntry(key: "editor.fontSize", rawValue: "14"),
                SettingEntry(key: "editor.tabSize", rawValue: "2"),
                SettingEntry(key: "editor.formatOnSave", rawValue: "true"),
                SettingEntry(key: "editor.wordWrap", rawValue: "on"),
                SettingEntry(key: "workbench.colorTheme", rawValue: "Default Dark Modern")
            ]
            return
        }
        do {
            let raw = try String(contentsOf: fileURL, encoding: .utf8)
            let cleaned = JsonCleaner.stripComments(from: raw)
            guard let data = cleaned.data(using: .utf8),
                  let dict = try JSONSerialization.jsonObject(with: data) as? [String: Any]
            else { return }
            entries = dict.sorted(by: { $0.key < $1.key }).map {
                SettingEntry(key: $0.key, rawValue: stringify($0.value))
            }
        } catch {
            saveStatus = .error(error.localizedDescription)
        }
    }

    func save() {
        var dict: [String: Any] = [:]
        for entry in entries { dict[entry.key] = parseValue(entry.rawValue) }
        do {
            let data = try JSONSerialization.data(withJSONObject: dict, options: [.prettyPrinted, .sortedKeys])
            try data.write(to: fileURL, options: .atomic)
            saveStatus = .saved
            Task {
                try? await Task.sleep(for: .seconds(2))
                saveStatus = .idle
            }
        } catch {
            saveStatus = .error(error.localizedDescription)
        }
    }

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

    private func stringify(_ value: Any) -> String {
        switch value {
        case let b as Bool: return b ? "true" : "false"
        case let n as Int: return "\(n)"
        case let d as Double: return "\(d)"
        case let s as String: return s
        default:
            if let data = try? JSONSerialization.data(withJSONObject: value, options: [.prettyPrinted]),
               let s = String(data: data, encoding: .utf8) {
                return s
            }
            return "\(value)"
        }
    }

    private func parseValue(_ raw: String) -> Any {
        if raw == "true" { return true }
        if raw == "false" { return false }
        if raw == "null" { return NSNull() }
        if let n = Int(raw) { return n }
        if let d = Double(raw) { return d }
        if let data = raw.data(using: .utf8),
           let obj = try? JSONSerialization.jsonObject(with: data) {
            return obj
        }
        return raw
    }
}

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
                        i = source.index(jNext, offsetBy: 1)
                        break
                    }
                    j = source.index(after: j)
                }
                continue
            }
            if c == "/" && next < source.endIndex && source[next] == "/" {
                while i < source.endIndex && source[i] != "\n" {
                    i = source.index(after: i)
                }
                continue
            }
            result.append(c)
            i = source.index(after: i)
        }
        return result
    }
}

enum SettingPreset: String, CaseIterable, Identifiable {
    case fontSizeSmall = "Font Size 13"
    case fontSizeMedium = "Font Size 15"
    case fontSizeLarge = "Font Size 18"
    case formatOnSave = "Format on Save"
    case noFormatOnSave = "No Format on Save"
    case darkTheme = "Dark Theme"
    case lightTheme = "Light Theme"
    case wordWrapOn = "Word Wrap On"
    case wordWrapOff = "Word Wrap Off"
    case hideMinimap = "Hide Minimap"
    case showMinimap = "Show Minimap"

    var id: String { rawValue }

    var keyValue: (key: String, value: String) {
        switch self {
        case .fontSizeSmall: return ("editor.fontSize", "13")
        case .fontSizeMedium: return ("editor.fontSize", "15")
        case .fontSizeLarge: return ("editor.fontSize", "18")
        case .formatOnSave: return ("editor.formatOnSave", "true")
        case .noFormatOnSave: return ("editor.formatOnSave", "false")
        case .darkTheme: return ("workbench.colorTheme", "Default Dark Modern")
        case .lightTheme: return ("workbench.colorTheme", "Default Light Modern")
        case .wordWrapOn: return ("editor.wordWrap", "on")
        case .wordWrapOff: return ("editor.wordWrap", "off")
        case .hideMinimap: return ("editor.minimap.enabled", "false")
        case .showMinimap: return ("editor.minimap.enabled", "true")
        }
    }
}

struct ContentView: View {
    @EnvironmentObject var store: SettingsStore
    @State private var showAdd = false
    @State private var showPresets = false
    @State private var searchText = ""
    @State private var editingEntry: SettingEntry?

    private var filtered: [SettingEntry] {
        guard !searchText.isEmpty else { return store.entries }
        return store.entries.filter {
            $0.key.localizedCaseInsensitiveContains(searchText) ||
            $0.rawValue.localizedCaseInsensitiveContains(searchText)
        }
    }

    var body: some View {
        NavigationStack {
            List {
                ForEach(filtered) { entry in
                    VStack(alignment: .leading, spacing: 4) {
                        Text(entry.key).font(.system(.subheadline, design: .monospaced))
                        Text(entry.rawValue)
                            .font(.system(.caption, design: .monospaced))
                            .foregroundStyle(.secondary)
                    }
                    .contentShape(Rectangle())
                    .onTapGesture { editingEntry = entry }
                }
                .onDelete(perform: store.delete)
            }
            .searchable(text: $searchText, prompt: "Search settings")
            .navigationTitle("Cursor Settings")
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("Presets") { showPresets = true }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button { showAdd = true } label: { Image(systemName: "plus") }
                }
            }
        }
        .sheet(isPresented: $showAdd) {
            AddEditView(mode: .add) { store.add($0) }
        }
        .sheet(item: $editingEntry) { entry in
            AddEditView(mode: .edit(entry)) { store.update($0) }
        }
        .sheet(isPresented: $showPresets) {
            PresetsView()
        }
    }
}

struct AddEditView: View {
    enum Mode { case add, edit(SettingEntry) }

    let mode: Mode
    let onSave: (SettingEntry) -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var key: String
    @State private var value: String

    init(mode: Mode, onSave: @escaping (SettingEntry) -> Void) {
        self.mode = mode
        self.onSave = onSave
        switch mode {
        case .add:
            _key = State(initialValue: "")
            _value = State(initialValue: "")
        case .edit(let entry):
            _key = State(initialValue: entry.key)
            _value = State(initialValue: entry.rawValue)
        }
    }

    var body: some View {
        NavigationStack {
            Form {
                TextField("Key", text: $key)
                    .font(.system(.body, design: .monospaced))
                TextField("Value", text: $value)
                    .font(.system(.body, design: .monospaced))
            }
            .navigationTitle("Edit Setting")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        let trimmedKey = key.trimmingCharacters(in: .whitespaces)
                        guard !trimmedKey.isEmpty else { return }
                        let trimmedVal = value.trimmingCharacters(in: .whitespaces)
                        switch mode {
                        case .add:
                            onSave(SettingEntry(key: trimmedKey, rawValue: trimmedVal))
                        case .edit(var entry):
                            entry.key = trimmedKey
                            entry.rawValue = trimmedVal
                            onSave(entry)
                        }
                        dismiss()
                    }
                }
            }
        }
    }
}

struct PresetsView: View {
    @EnvironmentObject var store: SettingsStore
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            List(SettingPreset.allCases) { preset in
                let (key, value) = preset.keyValue
                Button {
                    store.applyPreset(preset)
                    dismiss()
                } label: {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(preset.rawValue)
                        Text("\(key) = \(value)")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                            .fontDesign(.monospaced)
                    }
                }
            }
            .navigationTitle("Quick Presets")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Done") { dismiss() }
                }
            }
        }
    }
}

@main
struct CursorSettingsPlaygroundApp: App {
    @StateObject private var store = SettingsStore()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(store)
                .onAppear { store.load() }
        }
    }
}
