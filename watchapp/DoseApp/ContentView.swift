import SwiftUI

struct ContentView: View {
    @EnvironmentObject var vm: DoseViewModel

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()

            switch vm.viewState {
            case .noDose:
                NoDoseView()
            case .doseNeeded:
                DoseNeededView()
            case .doseConfirm:
                DoseConfirmView()
            }
        }
        .environmentObject(vm)
    }
}

// MARK: - STATE 1: No dose needed

struct NoDoseView: View {
    @EnvironmentObject var vm: DoseViewModel

    var body: some View {
        VStack(spacing: 4) {
            Text(vm.bgDisplayText)
                .font(.system(size: 52, weight: .bold, design: .rounded))
                .foregroundColor(.white)
            Text(vm.trendArrow)
                .font(.system(size: 22, weight: .medium))
                .foregroundColor(.white.opacity(0.75))
        }
    }
}

// MARK: - STATE 2: Dose needed (glanceable)

struct DoseNeededView: View {
    @EnvironmentObject var vm: DoseViewModel

    var body: some View {
        Button(action: { vm.openConfirm() }) {
            VStack(spacing: 6) {
                Text(vm.doseDisplayText)
                    .font(.system(size: 44, weight: .bold, design: .rounded))
                    .foregroundColor(.white)
                HStack(spacing: 4) {
                    Text(vm.bgDisplayText)
                        .font(.system(size: 18, weight: .medium))
                        .foregroundColor(.white.opacity(0.8))
                    Text(vm.trendArrow)
                        .font(.system(size: 16))
                        .foregroundColor(.white.opacity(0.7))
                }
            }
        }
        .buttonStyle(.plain)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

// MARK: - STATE 3: Dose confirm

struct DoseConfirmView: View {
    @EnvironmentObject var vm: DoseViewModel

    var body: some View {
        VStack(spacing: 12) {
            Button("Back") {
                vm.dismissConfirm()
            }
            .font(.system(size: 13))
            .foregroundColor(.white.opacity(0.6))
            .buttonStyle(.plain)

            Spacer()

            Text(vm.confirmDisplayText)
                .font(.system(size: 22, weight: .semibold, design: .rounded))
                .foregroundColor(.white)
                .multilineTextAlignment(.center)

            Spacer()

            Button(action: { vm.acknowledge() }) {
                Label("Done", systemImage: "checkmark.circle.fill")
                    .font(.system(size: 18, weight: .bold))
                    .foregroundColor(.white)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 10)
                    .background(Color.green.opacity(0.85))
                    .cornerRadius(12)
            }
            .buttonStyle(.plain)
            .disabled(vm.isAcknowledging)
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 6)
    }
}
