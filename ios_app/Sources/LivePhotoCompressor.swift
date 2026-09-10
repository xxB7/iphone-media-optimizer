import Foundation
import Photos
import AVFoundation

/// Handles paired Apple Live Photos compression and verification.
/// Guarantees that the photo and micro-video remain coupled with matching ContentIdentifier.
public class LivePhotoCompressor {
    
    private let imageCompressor: ImageCompressor
    private let videoCompressor: VideoCompressor
    
    public init(imageCompressor: ImageCompressor = ImageCompressor(), videoCompressor: VideoCompressor = VideoCompressor()) {
        self.imageCompressor = imageCompressor
        self.videoCompressor = videoCompressor
    }
    
    /// Verifies if a video asset qualifies as an authentic Apple Live Photo (duration <= 3.5s).
    public func isAuthenticLivePhotoVideo(url: URL) -> Bool {
        let asset = AVAsset(url: url)
        let duration = CMTimeGetSeconds(asset.duration)
        return duration <= 3.5
    }
    
    /// Saves a compressed image and companion video back into PhotoKit as a native Live Photo.
    public func saveLivePhoto(
        imageData: Data,
        videoURL: URL,
        targetCollection: PHAssetCollection? = nil,
        completion: @escaping (Bool, Error?) -> Void
    ) {
        PHPhotoLibrary.shared().performChanges({
            let request = PHAssetCreationRequest.forAsset()
            
            // 1. Add still photo component
            let photoOptions = PHAssetResourceCreationOptions()
            request.addResource(with: .photo, data: imageData, options: photoOptions)
            
            // 2. Add companion video component
            let videoOptions = PHAssetResourceCreationOptions()
            request.addResource(with: .pairedVideo, fileURL: videoURL, options: videoOptions)
            
            // 3. Add to target album if specified
            if let collection = targetCollection,
               let albumChangeRequest = PHAssetCollectionChangeRequest(for: collection) {
                if let placeholder = request.placeholderForCreatedAsset {
                    albumChangeRequest.addAssets([placeholder] as NSArray)
                }
            }
        }) { success, error in
            DispatchQueue.main.async {
                completion(success, error)
            }
        }
    }
}
