import Foundation
import Photos
import AVFoundation

/// Handles Apple Live Photos dual-stream compression while preserving pairing.
public class LivePhotoEngine {
    
    private let imageOptimizer: ImageOptimizer
    private let videoOptimizer: VideoOptimizer
    
    public init(imageOptimizer: ImageOptimizer = ImageOptimizer(), videoOptimizer: VideoOptimizer = VideoOptimizer()) {
        self.imageOptimizer = imageOptimizer
        self.videoOptimizer = videoOptimizer
    }
    
    /// Checks if companion video is under 3.5s duration.
    public func isAuthenticLivePhotoVideo(url: URL) -> Bool {
        let asset = AVAsset(url: url)
        let duration = CMTimeGetSeconds(asset.duration)
        return duration <= 3.5
    }
    
    /// Extracts photo and paired video resources from a Live Photo asset.
    public func extractLivePhotoResources(
        asset: PHAsset,
        completion: @escaping (Result<(photoData: Data, videoURL: URL), Error>) -> Void
    ) {
        let resources = PHAssetResource.assetResources(for: asset)
        guard let photoResource = resources.first(where: { $0.type == .photo }),
              let videoResource = resources.first(where: { $0.type == .pairedVideo }) else {
            completion(.failure(NSError(domain: "LivePhotoEngine", code: -1, userInfo: [NSLocalizedDescriptionKey: "لم يتم العثور على أزواج الصورة الحية كاملة"])))
            return
        }
        
        let tempDir = FileManager.default.temporaryDirectory
        let tempVideoURL = tempDir.appendingPathComponent(UUID().uuidString + "_orig.mov")
        let photoData = NSMutableData()
        
        let manager = PHAssetResourceManager.default()
        let group = DispatchGroup()
        var extractError: Error?
        
        // 1. Extract photo data
        group.enter()
        let photoOptions = PHAssetResourceRequestOptions()
        photoOptions.isNetworkAccessAllowed = true
        manager.requestData(for: photoResource, options: photoOptions, dataReceivedHandler: { chunk in
            photoData.append(chunk)
        }, completionHandler: { error in
            if let error = error { extractError = error }
            group.leave()
        })
        
        // 2. Extract paired video
        group.enter()
        let videoOptions = PHAssetResourceRequestOptions()
        videoOptions.isNetworkAccessAllowed = true
        manager.writeData(for: videoResource, toFile: tempVideoURL, options: videoOptions) { error in
            if let error = error { extractError = error }
            group.leave()
        }
        
        group.notify(queue: .global(qos: .userInitiated)) {
            if let error = extractError {
                try? FileManager.default.removeItem(at: tempVideoURL)
                completion(.failure(error))
            } else {
                completion(.success((photoData: photoData as Data, videoURL: tempVideoURL)))
            }
        }
    }
    
    /// Recreates the compressed Live Photo in the photo library.
    public func createCompressedLivePhoto(
        imageData: Data,
        videoURL: URL,
        targetCollections: [PHAssetCollection] = [],
        completion: @escaping (Result<PHObjectPlaceholder, Error>) -> Void
    ) {
        var placeholder: PHObjectPlaceholder?
        
        PHPhotoLibrary.shared().performChanges({
            let request = PHAssetCreationRequest.forAsset()
            
            let photoOptions = PHAssetResourceCreationOptions()
            request.addResource(with: .photo, data: imageData, options: photoOptions)
            
            let videoOptions = PHAssetResourceCreationOptions()
            request.addResource(with: .pairedVideo, fileURL: videoURL, options: videoOptions)
            
            placeholder = request.placeholderForCreatedAsset
            
            // Add to original albums
            for collection in targetCollections {
                if let albumChangeRequest = PHAssetCollectionChangeRequest(for: collection),
                   let assetPlaceholder = placeholder {
                    albumChangeRequest.addAssets([assetPlaceholder] as NSArray)
                }
            }
        }) { success, error in
            if success, let placeholder = placeholder {
                completion(.success(placeholder))
            } else {
                let err = error ?? NSError(domain: "LivePhotoEngine", code: -2, userInfo: [NSLocalizedDescriptionKey: "فشل حفظ الصورة الحية في الاستديو"])
                completion(.failure(err))
            }
        }
    }
}
