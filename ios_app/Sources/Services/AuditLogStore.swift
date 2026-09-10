import Foundation

/// Persists session history, audit logs, and lifetime space savings.
public class AuditLogStore: ObservableObject {
    
    private let userDefaultsKey = "khafeef_optimization_sessions"
    
    @Published public var sessions: [OptimizationSession] = []
    
    public var lifetimeSavedBytes: Int64 {
        sessions.reduce(0) { $0 + $1.totalSavedBytes }
    }
    
    public var formattedLifetimeSavedSpace: String {
        let formatter = ByteCountFormatter()
        formatter.allowedUnits = [.useGB, .useMB]
        formatter.countStyle = .file
        return formatter.string(fromByteCount: lifetimeSavedBytes)
    }
    
    public init() {
        loadSessions()
    }
    
    public func saveSession(_ session: OptimizationSession) {
        sessions.insert(session, at: 0)
        persist()
    }
    
    public func clearHistory() {
        sessions.removeAll()
        UserDefaults.standard.removeObject(forKey: userDefaultsKey)
    }
    
    private func persist() {
        if let encoded = try? JSONEncoder().encode(sessions) {
            UserDefaults.standard.set(encoded, forKey: userDefaultsKey)
        }
    }
    
    private func loadSessions() {
        if let data = UserDefaults.standard.data(forKey: userDefaultsKey),
           let decoded = try? JSONDecoder().decode([OptimizationSession].self, from: data) {
            self.sessions = decoded
        }
    }
}
