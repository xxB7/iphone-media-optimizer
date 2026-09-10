import Foundation
import Photos
import UIKit

/// Manages interaction with Apple PhotoKit (PHPhotoLibrary).
/// Handles permissions, album discovery, asset fetching, and in-place replacement.
public class PhotoKitManager: ObservableObject {
    
    @Published public var authorizationStatus: PHAuthorizationStatus = .notDetermined
    @Published public var totalPhotoCount: Int = 0
    @Published public var totalVideoCount: Int = 0
    @Published public var totalLivePhotoCount: Int = 0
    @Published public var estimatedTotalBytes: Int64 = 0
    
    public init() {
        checkPermission()
    }
    
    public func checkPermission() {
        self.authorizationStatus = PHPhotoLibrary.authorizationStatus(for: .readWrite)
    }
    
    public func requestPermission(completion: @escaping (Bool) -> Void) {
        PHPhotoLibrary.requestAuthorization(for: .readWrite) { status in
            DispatchQueue.main.async {
                self.authorizationStatus = status
                completion(status == .authorized || status == .limited)
            }
        }
    }
    
    /// Scans the user's library and categorizes assets by media type.
    public func scanLibrary(completion: @escaping () -> Void) {
        guard authorizationStatus == .authorized || authorizationStatus == .limited else {
            completion()
            return
        }
        
        DispatchQueue.global(qos: .userInitiated).async {
            let fetchOptions = PHFetchOptions()
            fetchOptions.includeAssetSourceTypes = [.typeUserLibrary, .typeCloudShared, .typeiTunesSynced]
            
            let allAssets = PHAsset.fetchAssets(with: fetchOptions)
            var photos = 0
            var videos = 0
            var livePhotos = 0
            
            allAssets.enumerateObjects { asset, _, _ in
                if asset.mediaSubtypes.contains(.photoLive) {
                    livePhotos += 1
                } else if asset.mediaType == .image {
                    photos += 1
                } else if asset.mediaType == .video {
                    videos += 1
                }
            }
            
            DispatchQueue.main.async {
                self.totalPhotoCount = photos
                self.totalVideoCount = videos
                self.totalLivePhotoCount = livePhotos
                completion()
            }
        }
    }
    
    /// Safely deletes original heavy assets after verified compression.
    /// iOS will present the native system confirmation dialog.
    public func deleteOriginalAssets(_ assets: [PHAsset], completion: @escaping (Bool, Error?) -> Void) {
        PHPhotoLibrary.shared().performChanges({
            PHAssetChangeRequest.deleteAssets(assets as NSArray)
        }) { success, error in
            DispatchQueue.main.async {
                completion(success, error)
            }
        }
    }
}
