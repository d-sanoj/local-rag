import SwiftUI

/// Shown in the detail area when the local-rag service cannot be
/// reached. Tells the user exactly how to start it.
struct ConnectionView: View {
    @EnvironmentObject private var settings: SettingsStore
    @EnvironmentObject private var appController: AppController
    @State private var isRetrying = false

    var body: some View {
        VStack(spacing: 20) {
            Spacer()
            Image(systemName: "wifi.exclamationmark")
                .font(.system(size: 44))
                .foregroundStyle(.secondary)
            Text("Service not reachable")
                .font(.title2.bold())
            VStack(alignment: .leading, spacing: 8) {
                Text("The local-rag service is not answering at:")
                    .foregroundStyle(.secondary)
                Text(settings.baseURL.absoluteString)
                    .font(.body.monospaced())
                    .textSelection(.enabled)
                if let error = appController.lastError {
                    Text(error)
                        .font(.callout)
                        .foregroundStyle(.red)
                }
            }
            VStack(alignment: .leading, spacing: 6) {
                Text("To start it:")
                    .font(.headline)
                Text("1.  Open a terminal in the local-rag repo")
                Text("2.  Run  ./run.sh")
                Text("3.  Wait for “local-rag listening on …:8000”, then press Retry")
            }
            .frame(maxWidth: 480, alignment: .leading)
            HStack(spacing: 12) {
                TextField("Service address", text: $settings.baseURLString)
                    .textFieldStyle(.roundedBorder)
                    .frame(width: 260)
                Button("Retry") {
                    isRetrying = true
                    Task {
                        await appController.checkHealth()
                        isRetrying = false
                    }
                }
                .buttonStyle(.borderedProminent)
                .disabled(isRetrying)
            }
            Spacer()
        }
        .padding()
        .navigationTitle("Not connected")
    }
}
