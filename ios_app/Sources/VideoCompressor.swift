import Foundation
import AVFoundation

/// Native hardware-accelerated video compressor using AVFoundation & VideoToolbox.
/// Encodes in HEVC (H.265), preserves original audio tracks and QuickTime metadata.
public class VideoCompressor {
    
    public init() {}
    
    public enum VideoQuality {
        case high1080p
        case medium720p
        case highestHEVC
        
        var exportPreset: String {
            switch self {
            case .high1080p:
                return AVAssetExportPresetHEVC1920x1080
            case .medium720p:
                return AVAssetExportPresetHEVC1280x720
            case .highestHEVC:
                return AVAssetExportPresetHEVCHighestQuality
            }
        }
    }
    
    /// Compresses a video file at sourceURL to destURL using hardware HEVC encoder.
    public func compressVideo(
        sourceURL: URL,
        destURL: URL,
        quality: VideoQuality = .high1080p,
        progressHandler: ((Double) -> Void)? = nil,
        completion: @escaping (Result<URL, Error>) -> Void
    ) {
        let asset = AVAsset(url: sourceURL)
        
        guard let exportSession = AVAssetExportSession(
            asset: asset,
            presetName: quality.exportPreset
        ) else {
            completion(.failure(NSError(domain: "VideoCompressor", code: -1, userInfo: [NSLocalizedDescriptionKey: "Failed to create export session"])))
            return
        }
        
        // Remove destination file if already exists
        if FileManager.default.fileExists(atPath: destURL.path) {
            try? FileManager.default.removeItem(at: destURL)
        }
        
        exportSession.outputURL = destURL
        exportSession.outputFileType = .mov
        exportSession.shouldOptimizeForNetworkUse = true
        
        // Preserve original metadata items (dates, camera, GPS)
        exportSession.metadata = asset.metadata
        
        exportSession.exportAsynchronously {
            switch exportSession.status {
            case .completed:
                completion(.success(destURL))
            case .failed:
                let error = exportSession.error ?? NSError(domain: "VideoCompressor", code: -2, userInfo: [NSLocalizedDescriptionKey: "Video export failed"])
                completion(.failure(error))
            case .cancelled:
                completion(.failure(NSError(domain: "VideoCompressor", code: -3, userInfo: [NSLocalizedDescriptionKey: "Video export cancelled"])))
            default:
                break
            }
        }
    }
}
