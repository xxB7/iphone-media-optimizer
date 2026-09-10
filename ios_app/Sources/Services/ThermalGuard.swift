import Foundation

/// Monitors device thermal state to prevent overheating during bulk media processing.
public class ThermalGuard: ObservableObject {
    
    @Published public var currentThermalState: ProcessInfo.ThermalState = .nominal
    @Published public var shouldThrottle: Bool = false
    
    public init() {
        self.currentThermalState = ProcessInfo.processInfo.thermalState
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(thermalStateChanged),
            name: ProcessInfo.thermalStateDidChangeNotification,
            object: nil
        )
    }
    
    deinit {
        NotificationCenter.default.removeObserver(self)
    }
    
    @objc private func thermalStateChanged() {
        DispatchQueue.main.async {
            self.currentThermalState = ProcessInfo.processInfo.thermalState
            switch self.currentThermalState {
            case .nominal, .fair:
                self.shouldThrottle = false
            case .serious, .critical:
                self.shouldThrottle = true
            @unknown default:
                self.shouldThrottle = false
            }
        }
    }
}
