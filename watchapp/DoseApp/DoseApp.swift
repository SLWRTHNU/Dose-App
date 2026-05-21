import SwiftUI

@main
struct DoseApp: App {
    @StateObject private var viewModel = DoseViewModel()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(viewModel)
        }
    }
}
