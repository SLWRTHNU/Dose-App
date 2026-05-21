import SwiftUI
import WatchKit

// Change this constant to point at your backend server.
private let backendURL = "http://192.168.1.100:5000"

enum ViewState {
    case noDose
    case doseNeeded
    case doseConfirm
}

@MainActor
final class DoseViewModel: ObservableObject {
    @Published var currentAction: String? = nil
    @Published var bg: Double? = nil
    @Published var trend: String? = nil
    @Published var viewState: ViewState = .noDose
    @Published var isAcknowledging: Bool = false

    private var pollTimer: Timer?
    private var previousAction: String? = nil

    init() {
        startPolling()
    }

    // MARK: - Polling

    func startPolling() {
        poll()
        pollTimer = Timer.scheduledTimer(withTimeInterval: 60, repeats: true) { [weak self] _ in
            Task { await self?.poll() }
        }
    }

    func poll() {
        Task { await fetchStatus() }
    }

    private func fetchStatus() async {
        guard let url = URL(string: "\(backendURL)/status") else {
            print("DoseViewModel: invalid backend URL")
            return
        }

        do {
            let (data, response) = try await URLSession.shared.data(from: url)
            guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
                print("DoseViewModel: non-200 status response")
                return
            }
            let decoded = try JSONDecoder().decode(StatusResponse.self, from: data)
            applyStatus(decoded)
        } catch {
            // Keep last known state on network error - do not crash.
            print("DoseViewModel: poll error: \(error)")
        }
    }

    private func applyStatus(_ status: StatusResponse) {
        let newAction = status.action
        bg = status.bg
        trend = status.trend

        let wasNil = previousAction == nil
        let isNonNil = newAction != nil
        previousAction = currentAction
        currentAction = newAction

        if wasNil && isNonNil {
            // Transition from no dose to dose needed - trigger haptic.
            WKInterfaceDevice.current().play(.notification)
            if viewState == .noDose {
                viewState = .doseNeeded
            }
        } else if newAction == nil {
            viewState = .noDose
        } else if viewState == .noDose && newAction != nil {
            viewState = .doseNeeded
        }
    }

    // MARK: - User actions

    func openConfirm() {
        viewState = .doseConfirm
    }

    func dismissConfirm() {
        viewState = .doseNeeded
    }

    func acknowledge() {
        guard !isAcknowledging else { return }
        isAcknowledging = true

        // Clear local state immediately for responsiveness.
        let actionBeforeAck = currentAction
        currentAction = nil
        viewState = .noDose

        Task {
            await postAcknowledge()
            isAcknowledging = false
            if currentAction == nil && actionBeforeAck != nil {
                // Refresh to confirm server state.
                await fetchStatus()
            }
        }
    }

    private func postAcknowledge() async {
        guard let url = URL(string: "\(backendURL)/acknowledge") else { return }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try? JSONEncoder().encode(["acknowledged_by": "watch"])

        do {
            let (_, response) = try await URLSession.shared.data(for: request)
            if let http = response as? HTTPURLResponse, http.statusCode != 200 {
                print("DoseViewModel: acknowledge returned status \(http.statusCode)")
            }
        } catch {
            print("DoseViewModel: acknowledge POST failed: \(error)")
        }
    }

    // MARK: - Display helpers

    var doseDisplayText: String {
        guard let action = currentAction else { return "" }
        if action.hasPrefix("jb:"), let n = action.split(separator: ":").last {
            return "\(n)x \u{1F36C}"  // 🍬
        }
        if action == "water" { return "\u{1F4A7}" }   // 💧
        if action == "juicebox" { return "\u{1F9C3}" } // 🧃
        return action
    }

    var confirmDisplayText: String {
        guard let action = currentAction else { return "" }
        if action.hasPrefix("jb:"), let n = action.split(separator: ":").last {
            return "Give \(n)g"
        }
        if action == "water" { return "Give water" }
        if action == "juicebox" { return "Give juice box" }
        return action
    }

    var bgDisplayText: String {
        guard let b = bg else { return "--" }
        return String(format: "%.1f", b)
    }

    var trendArrow: String {
        let arrows: [String: String] = [
            "DoubleUp": "\u{2191}\u{2191}",
            "SingleUp": "\u{2191}",
            "FortyFiveUp": "\u{2197}",
            "Flat": "\u{2192}",
            "FortyFiveDown": "\u{2198}",
            "SingleDown": "\u{2193}",
            "DoubleDown": "\u{2193}\u{2193}",
        ]
        return arrows[trend ?? ""] ?? "?"
    }
}

// MARK: - Codable response type

private struct StatusResponse: Decodable {
    let action: String?
    let bg: Double?
    let trend: String?
}
