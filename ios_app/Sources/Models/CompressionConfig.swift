import Foundation
import AVFoundation

/// Configuration options for library media optimization.
public struct CompressionConfig: Codable, Equatable {
    
    public enum VideoPreset: String, Codable, CaseIterable, Identifiable {
        case hevc1080p = "HEVC 1080p (متوازن)"
        case hevc720p = "HEVC 720p (أقصى توفير)"
        case hevcHighest = "HEVC الأصلية (أعلى جودة)"
        
        public var id: String { rawValue }
        
        public var avPreset: String {
            switch self {
            case .hevc1080p:
                return AVAssetExportPresetHEVC1920x1080
            case .hevc720p:
                return AVAssetExportPresetHEVC1280x720
            case .hevcHighest:
                return AVAssetExportPresetHEVCHighestQuality
            }
        }
    }
    
    public enum SafetyMode: String, Codable, CaseIterable, Identifiable {
        case backupFirst = "الوضع الآمن (نقل الأصل إلى ألبوم النسخ الاحتياطية)"
        case directReplace = "استبدال مباشر (حذف الأصل بعد التأكيد الرسمي)"
        
        public var id: String { rawValue }
    }
    
    /// Image compression quality between 0.5 (low) and 1.0 (lossless), default 0.75
    public var imageQuality: Float = 0.75
    
    /// Target video export preset
    public var videoPreset: VideoPreset = .hevc1080p
    
    /// Safety mode for handling originals
    public var safetyMode: SafetyMode = .backupFirst
    
    /// Whether to preserve Live Photos as paired animations
    public var preserveLivePhotos: Bool = true
    
    /// Whether to auto-throttle when device temperature rises
    public var enableThermalGuard: Bool = true
    
    /// Threshold in megabytes below which files are skipped (already small)
    public var skipFilesUnderMB: Double = 0.5
    
    public init() {}
}
