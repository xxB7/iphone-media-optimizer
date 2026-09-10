import Foundation
import Photos
import UIKit

/// High-level service for interacting with Apple PhotoKit (PHPhotoLibrary).
/// Handles permissions, scanning, album discovery, and asset insertion/deletion.
public class PhotoLibraryService: ObservableObject {
    
    @Published public var authorizationStatus: PHAuthorizationStatus = .notDetermined
    @Published public var totalPhotoCount: Int = 0
    @Published public var totalVideoCount: Int = 0
    @Published public var totalLivePhotoCount: Int = 0
    @Published public var estimatedTotalBytes: Int64 = 0
    @Published public var availableAlbums: [AlbumInfo] = []
    
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
                let isAuthorized = (status == .authorized || status == .limited)
                completion(isAuthorized)
            }
        }
    }
    
    /// Scans the entire library, categorizes media, and discovers user albums.
    public func scanLibrary(completion: @escaping () -> Void) {
        guard authorizationStatus == .authorized || authorizationStatus == .limited else {
            completion()
            return
        }
        
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            guard let self = self else { return }
            
            // 1. Scan all assets
            let fetchOptions = PHFetchOptions()
            fetchOptions.includeAssetSourceTypes = [.typeUserLibrary, .typeCloudShared, .typeiTunesSynced]
            let allAssets = PHAsset.fetchAssets(with: fetchOptions)
            
            var photos = 0
            var videos = 0
            var livePhotos = 0
            var estimatedBytes: Int64 = 0
            
            allAssets.enumerateObjects { asset, _, _ in
                if asset.mediaSubtypes.contains(.photoLive) {
                    livePhotos += 1
                    estimatedBytes += 12 * 1024 * 1024 // ~12MB estimated per Live Photo
                } else if asset.mediaType == .image {
                    photos += 1
                    estimatedBytes += 3 * 1024 * 1024  // ~3MB estimated per Photo
                } else if asset.mediaType == .video {
                    videos += 1
                    let durationSec = asset.duration
                    let estimatedVideoMB = max(5.0, durationSec * 2.5) // ~2.5 MB/s
                    estimatedBytes += Int64(estimatedVideoMB * 1024 * 1024)
                }
            }
            
            // 2. Discover user albums
            var discoveredAlbums: [AlbumInfo] = []
            let userAlbums = PHAssetCollection.fetchAssetCollections(with: .album, subtype: .any, options: nil)
            userAlbums.enumerateObjects { collection, _, _ in
                let assetsInAlbum = PHAsset.fetchAssets(in: collection, options: nil)
                if assetsInAlbum.count > 0 {
                    let album = AlbumInfo(
                        id: collection.localIdentifier,
                        title: collection.localizedTitle ?? "ألبوم بدون اسم",
                        count: assetsInAlbum.count,
                        collection: collection,
                        isSelected: true
                    )
                    discoveredAlbums.append(album)
                }
            }
            
            DispatchQueue.main.async {
                self.totalPhotoCount = photos
                self.totalVideoCount = videos
                self.totalLivePhotoCount = livePhotos
                self.estimatedTotalBytes = estimatedBytes
                self.availableAlbums = discoveredAlbums
                completion()
            }
        }
    }
    
    /// Finds all albums containing a given asset.
    public func fetchAlbumCollections(for asset: PHAsset) -> [PHAssetCollection] {
        var collections: [PHAssetCollection] = []
        let albums = PHAssetCollection.fetchAssetCollectionsContaining(asset, with: .album, options: nil)
        albums.enumerateObjects { collection, _, _ in
            collections.append(collection)
        }
        return collections
    }
    
    /// Safely finds or creates a dedicated album for keeping original backups if safety mode is active.
    public func getOrCreateBackupAlbum(completion: @escaping (PHAssetCollection?) -> Void) {
        let albumTitle = "خفيف - النسخ الأصلية"
        let fetchOptions = PHFetchOptions()
        fetchOptions.predicate = NSPredicate(format: "localizedTitle = %@", albumTitle)
        let collections = PHAssetCollection.fetchAssetCollections(with: .album, subtype: .any, options: fetchOptions)
        
        if let existingAlbum = collections.firstObject {
            completion(existingAlbum)
            return
        }
        
        var placeholder: PHObjectPlaceholder?
        PHPhotoLibrary.shared().performChanges({
            let createAlbumRequest = PHAssetCollectionChangeRequest.creationRequestForAssetCollection(withTitle: albumTitle)
            placeholder = createAlbumRequest.placeholderForCreatedAssetCollection
        }) { success, error in
            DispatchQueue.main.async {
                if success, let id = placeholder?.localIdentifier {
                    let result = PHAssetCollection.fetchAssetCollections(withLocalIdentifiers: [id], options: nil)
                    completion(result.firstObject)
                } else {
                    completion(nil)
                }
            }
        }
    }
    
    /// Deletes original assets via the official Apple system confirmation prompt.
    public func deleteOriginalAssets(_ assets: [PHAsset], completion: @escaping (Bool, Error?) -> Void) {
        guard !assets.isEmpty else {
            completion(true, nil)
            return
        }
        
        PHPhotoLibrary.shared().performChanges({
            PHAssetChangeRequest.deleteAssets(assets as NSArray)
        }) { success, error in
            DispatchQueue.main.async {
                completion(success, error)
            }
        }
    }
}
