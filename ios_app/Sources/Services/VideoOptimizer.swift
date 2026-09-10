import Foundation
import AVFoundation

/// Native hardware-accelerated video optimizer using AVFoundation and VideoToolbox.
/// Encodes in HEVC (H.265), preserves original audio tracks and QuickTime metadata.
public class VideoOptimizer {
    
    public init() {}
    
    /// Compresses a video file at sourceURL to a temporary output file using the requested preset.
    public func compressVideo(
        sourceURL: URL,
        preset: CompressionConfig.VideoPreset = .hevc1080p,
        completion: @escaping (Result<(URL, Int64), Error>) -> Void
    ) {
        let asset = AVAsset(url: sourceURL)
        
        let tempDir = FileManager.default.temporaryDirectory
        let destURL = tempDir.appendingPathComponent(UUID().uuidString + ".mov")
        
        // Check if preset is compatible with the asset
        AVAssetExportSession.determineCompatibility(ofExportPreset: preset.avPreset, with: asset, outputFileType: .mov) { isCompatible in
            guard isCompatible, let exportSession = AVAssetExportSession(asset: asset, presetName: preset.avPreset) else {
                // Fallback to 1080p if highest is not compatible
                guard let fallbackSession = AVAssetExportSession(asset: asset, presetName: AVAssetExportPresetHEVC1920x1080) else {
                    completion(.failure(NSError(domain: "VideoOptimizer", code: -1, userInfo: [NSLocalizedDescriptionKey: "لا يمكن إنشاء جلسة تصدير متوافقة مع هذا الفيديو"])))
                    return
                }
                self.executeExport(exportSession: fallbackSession, destURL: destURL, asset: asset, completion: completion)
                return
            }
            
            self.executeExport(exportSession: exportSession, destURL: destURL, asset: asset, completion: completion)
        }
    }
    
    private func executeExport(
        exportSession: AVAssetExportSession,
        destURL: URL,
        asset: AVAsset,
        completion: @escaping (Result<(URL, Int64), Error>) -> Void
    ) {
        if FileManager.default.fileExists(atPath: destURL.path) {
            try? FileManager.default.removeItem(at: destURL)
        }
        
        exportSession.outputURL = destURL
        exportSession.outputFileType = .mov
        exportSession.shouldOptimizeForNetworkUse = true
        exportSession.metadata = asset.metadata
        
        exportSession.exportAsynchronously {
            switch exportSession.status {
            case .completed:
                do {
                    let attributes = try FileManager.default.attributesOfItem(atPath: destURL.path)
                    let fileSize = (attributes[.size] as? NSNumber)?.int64Value ?? 0
                    completion(.success((destURL, fileSize)))
                } catch {
                    completion(.failure(error))
                }
            case .failed:
                let error = exportSession.error ?? NSError(domain: "VideoOptimizer", code: -2, userInfo: [NSLocalizedDescriptionKey: "فشل تصدير الفيديو المضغوط"])
                try? FileManager.default.removeItem(at: destURL)
                completion(.failure(error))
            case .cancelled:
                try? FileManager.default.removeItem(at: destURL)
                completion(.failure(NSError(domain: "VideoOptimizer", code: -3, userInfo: [NSLocalizedDescriptionKey: "تم إلغاء تصدير الفيديو"])))
            default:
                break
            }
        }
    }
}
