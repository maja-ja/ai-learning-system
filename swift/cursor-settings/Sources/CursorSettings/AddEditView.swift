import SwiftUI

// MARK: - AddEditView

struct AddEditView: View {
    enum Mode {
        case add
        case edit(SettingEntry)
    }

    let mode: Mode
    let onSave: (SettingEntry) -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var key: String
    @State private var value: String
    @State private var showValidationError = false

    private var title: String {
        switch mode {
        case .add:  return "New Setting"
        case .edit: return "Edit Setting"
        }
    }

    init(mode: Mode, onSave: @escaping (SettingEntry) -> Void) {
        self.mode = mode
        self.onSave = onSave
        switch mode {
        case .add:
            _key   = State(initialValue: "")
            _value = State(initialValue: "")
        case .edit(let entry):
            _key   = State(initialValue: entry.key)
            _value = State(initialValue: entry.rawValue)
        }
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("Key") {
                    TextField("e.g. editor.fontSize", text: $key)
                        .autocorrectionDisabled()
                        .textInputAutocapitalization(.never)
                        .font(.system(.body, design: .monospaced))
                }

                Section {
                    TextField("e.g. 16  /  true  /  \"Default Dark Modern\"", text: $value)
                        .autocorrectionDisabled()
                        .textInputAutocapitalization(.never)
                        .font(.system(.body, design: .monospaced))
                } header: {
                    Text("Value")
                } footer: {
                    Text("Numbers, booleans (true/false), and strings are auto-detected.")
                        .font(.caption)
                }

                if showValidationError {
                    Section {
                        Label("Key cannot be empty.", systemImage: "exclamationmark.circle")
                            .foregroundStyle(.red)
                    }
                }
            }
            .navigationTitle(title)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") { submit() }
                        .fontWeight(.semibold)
                }
            }
        }
        .presentationDetents([.medium])
    }

    private func submit() {
        guard !key.trimmingCharacters(in: .whitespaces).isEmpty else {
            showValidationError = true
            return
        }
        let trimmedKey = key.trimmingCharacters(in: .whitespaces)
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

// MARK: - PresetsView

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
                    HStack(spacing: 14) {
                        Image(systemName: preset.icon)
                            .frame(width: 28)
                            .foregroundStyle(.blue)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(preset.rawValue)
                                .foregroundStyle(.primary)
                            Text("\(key) = \(value)")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                                .fontDesign(.monospaced)
                        }
                    }
                    .padding(.vertical, 2)
                }
            }
            .navigationTitle("Quick Presets")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Done") { dismiss() }
                }
            }
        }
        .presentationDetents([.large])
    }
}
