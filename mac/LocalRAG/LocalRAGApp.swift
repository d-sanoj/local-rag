import SwiftUI

@main
struct LocalRAGApp: App {
    @StateObject private var settings = SettingsStore()
    @StateObject private var appController: AppController
    @StateObject private var chatController = ChatController()
    @StateObject private var searchController = SearchController()
    @StateObject private var documentsController = DocumentsController()

    init() {
        let settingsStore = SettingsStore()
        _settings = StateObject(wrappedValue: settingsStore)
        _appController = StateObject(wrappedValue: AppController(settings: settingsStore))
    }

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(settings)
                .environmentObject(appController)
                .environmentObject(chatController)
                .environmentObject(searchController)
                .environmentObject(documentsController)
                .frame(minWidth: 920, minHeight: 620)
        }
        .commands {
            SidebarCommands()
        }
    }
}
