import SwiftUI

@main
struct CursorSettingsApp: App {
    @StateObject private var store = SettingsStore()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(store)
                .onAppear { store.load() }
        }
    }
}
