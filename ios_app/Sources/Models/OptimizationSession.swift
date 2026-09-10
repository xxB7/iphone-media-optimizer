import Foundation

public struct OptimizationSession: Codable, Identifiable {
    public var id: UUID
    public var date: Date
    public var totalProcessed: Int
    public var totalSavedBytes: Int64
    public var photosOptimized: Int
    public var videosOptimized: Int
    public var livePhotosOptimized: Int
    public var skippedCount: Int
    public var failedCount: Int
    
    public var formattedSavedSpace: String {
        let formatter = ByteCountFormatter()
        formatter.allowedUnits = [.useGB, .useMB]
        formatter.countStyle = .file
        return formatter.string(fromByteCount: totalSavedBytes)
    }
    
    public init(
        id: UUID = UUID(),
        date: Date = Date(),
        totalProcessed: Int = 0,
        totalSavedBytes: Int64 = 0,
        photosOptimized: Int = 0,
        videosOptimized: Int = 0,
        livePhotosOptimized: Int = 0,
        skippedCount: Int = 0,
        failedCount: Int = 0
    ) {
        self.id = id
        self.date = date
        self.totalProcessed = totalProcessed
        self.totalSavedBytes = totalSavedBytes
        self.photosOptimized = photosOptimized
        self.videosOptimized = videosOptimized
        self.livePhotosOptimized = livePhotosOptimized
        self.skippedCount = skippedCount
        self.failedCount = failedCount
    }
}
