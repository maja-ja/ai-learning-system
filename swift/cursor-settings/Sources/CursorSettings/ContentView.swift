import SwiftUI

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
                    SettingRow(entry: entry)
                        .contentShape(Rectangle())
                        .onTapGesture { editingEntry = entry }
                }
                .onDelete(perform: store.delete)
            }
            .listStyle(.insetGrouped)
            .searchable(text: $searchText, prompt: "Search settings")
            .navigationTitle("Cursor Settings")
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button { showPresets = true } label: {
                        Label("Presets", systemImage: "sparkles")
                    }
                }
                ToolbarItemGroup(placement: .topBarTrailing) {
                    saveStatusView
                    Button { showAdd = true } label: {
                        Image(systemName: "plus")
                    }
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

    @ViewBuilder
    private var saveStatusView: some View {
        switch store.saveStatus {
        case .saved:
            Label("Saved", systemImage: "checkmark.circle.fill")
                .foregroundStyle(.green)
                .font(.caption)
        case .error(let msg):
            Label(msg, systemImage: "exclamationmark.triangle.fill")
                .foregroundStyle(.red)
                .font(.caption)
        case .idle:
            EmptyView()
        }
    }
}

// MARK: - SettingRow

struct SettingRow: View {
    let entry: SettingEntry

    private var valueColor: Color {
        switch entry.rawValue.lowercased() {
        case "true":  return .green
        case "false": return .red
        default:
            if Int(entry.rawValue) != nil || Double(entry.rawValue) != nil {
                return .orange
            }
            return .secondary
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(entry.key)
                .font(.system(.subheadline, design: .monospaced))
                .foregroundStyle(.primary)
            Text(entry.rawValue)
                .font(.system(.caption, design: .monospaced))
                .foregroundStyle(valueColor)
                .lineLimit(2)
        }
        .padding(.vertical, 2)
    }
}
