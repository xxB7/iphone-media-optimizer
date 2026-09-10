import Foundation
import SwiftUI

@MainActor
public class SettingsViewModel: ObservableObject {
    
    private let configKey = "khafeef_compression_config"
    
    @Published public var config: CompressionConfig = CompressionConfig() {
        didSet {
            saveConfig()
        }
    }
    
    public init() {
        loadConfig()
    }
    
    private func saveConfig() {
        if let encoded = try? JSONEncoder().encode(config) {
            UserDefaults.standard.set(encoded, forKey: configKey)
        }
    }
    
    private func loadConfig() {
        if let data = UserDefaults.standard.data(forKey: configKey),
           let decoded = try? JSONDecoder().decode(CompressionConfig.self, from: data) {
            self.config = decoded
        }
    }
    
    public func resetToDefaults() {
        self.config = CompressionConfig()
    }
}
