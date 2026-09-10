import Foundation
import Photos

public enum MediaType: String, Codable {
    case photo = "صورة"
    case video = "فيديو"
    case livePhoto = "صورة حية"
    case unknown = "غير معروف"
}

public enum ItemOptimizationStatus: String, Codable {
    case pending = "قيد الانتظار"
    case processing = "جاري المعالجة"
    case completed = "تم بنجاح"
    case skipped = "تم التخطي (مضغوط بالفعل)"
    case failed = "فشل"
}

public struct MediaItem: Identifiable, Equatable {
    public let id: String
    public let asset: PHAsset
    public let mediaType: MediaType
    public let creationDate: Date?
    public var originalSizeBytes: Int64
    public var compressedSizeBytes: Int64
    public var status: ItemOptimizationStatus
    public var associatedAlbumIds: [String]
    public var errorMessage: String?
    
    public var savedBytes: Int64 {
        if status == .completed && compressedSizeBytes > 0 && originalSizeBytes > compressedSizeBytes {
            return originalSizeBytes - compressedSizeBytes
        }
        return 0
    }
    
    public init(
        id: String,
        asset: PHAsset,
        mediaType: MediaType,
        creationDate: Date? = nil,
        originalSizeBytes: Int64 = 0,
        compressedSizeBytes: Int64 = 0,
        status: ItemOptimizationStatus = .pending,
        associatedAlbumIds: [String] = []
    ) {
        self.id = id
        self.asset = asset
        self.mediaType = mediaType
        self.creationDate = creationDate
        self.originalSizeBytes = originalSizeBytes
        self.compressedSizeBytes = compressedSizeBytes
        self.status = status
        self.associatedAlbumIds = associatedAlbumIds
    }
    
    public static func == (lhs: MediaItem, rhs: MediaItem) -> Bool {
        return lhs.id == rhs.id && lhs.status == rhs.status && lhs.compressedSizeBytes == rhs.compressedSizeBytes
    }
}
