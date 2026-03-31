// Mac /「在 Mac 上設計的 iPad App」（Mac Catalyst）用單檔。
//
// Swift Playgrounds 請務必二選一，否則會重複定義與兩個 @main：
// A) 刪除或清空內建 MyApp.swift（含 @main 與 struct ContentView），只保留本檔；或
// B) 保留 MyApp：刪掉本檔最後的 @main struct，在 MyApp 的 WindowGroup 裡放
//    CursorSettingsRootView().environmentObject(你的 SettingsStore)。
//
// 讀寫：~/Library/Application Support/Cursor/User/settings.json
// 儲存會寫成標準 JSON，原有 // 註解會消失，建議先備份 settings.json。

import SwiftUI

struct SettingEntry: Identifiable, Codable, Equatable {
    var id = UUID()
    var key: String
    var rawValue: String
}

/// Mac Catalyst 不可用 `FileManager.homeDirectoryForCurrentUser`，改用最外層使用者目錄。
private enum CursorSettingsHome {
    static var url: URL {
        #if targetEnvironment(macCatalyst)
        URL(fileURLWithPath: NSHomeDirectory(), isDirectory: true)
        #else
        FileManager.default.homeDirectoryForCurrentUser
        #endif
    }
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
        CursorSettingsHome.url
            .appendingPathComponent("Library/Application Support/Cursor/User/settings.json")
    }

    var settingsPathDisplay: String { fileURL.path }

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

    func applyPreset(_ preset: CursorSettingsPreset) {
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

enum CursorSettingsPreset: String, CaseIterable, Identifiable {
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

/// 名稱刻意不用 `ContentView`，避免與 Playgrounds 範本衝突。
struct CursorSettingsRootView: View {
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
                Section {
                    Text(store.settingsPathDisplay)
                        .font(.system(.caption2, design: .monospaced))
                        .foregroundStyle(.secondary)
                        .textSelection(.enabled)
                } header: {
                    Text("Cursor settings.json")
                }

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
                ToolbarItem(placement: .navigation) {
                    Button("Presets") { showPresets = true }
                }
                ToolbarItem(placement: .primaryAction) {
                    Button { showAdd = true } label: { Image(systemName: "plus") }
                }
            }
        }
        .frame(minWidth: 480, minHeight: 360)
        .sheet(isPresented: $showAdd) {
            CursorSettingsAddEditView(mode: .add) { store.add($0) }
        }
        .sheet(item: $editingEntry) { entry in
            CursorSettingsAddEditView(mode: .edit(entry)) { store.update($0) }
        }
        .sheet(isPresented: $showPresets) {
            CursorSettingsPresetsView()
        }
    }
}

struct CursorSettingsAddEditView: View {
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
        .frame(minWidth: 400, minHeight: 220)
    }
}

struct CursorSettingsPresetsView: View {
    @EnvironmentObject var store: SettingsStore
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            List(CursorSettingsPreset.allCases) { preset in
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
        .frame(minWidth: 360, minHeight: 400)
    }
}

/// 若專案裡還有帶 @main 的 MyApp，請刪除其中一個 @main（見檔案頂端說明）。
@main
struct CursorSettingsMacPlaygroundApp: App {
    @StateObject private var store = SettingsStore()

    var body: some Scene {
        WindowGroup {
            CursorSettingsRootView()
                .environmentObject(store)
                .onAppear { store.load() }
        }
        #if os(macOS) && !targetEnvironment(macCatalyst)
        .defaultSize(width: 900, height: 640)
        #endif
    }
}
