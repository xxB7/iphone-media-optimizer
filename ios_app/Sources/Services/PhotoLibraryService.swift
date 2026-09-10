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
    
    @Published public var deviceTotalBytes: Int64 = 0
    @Published public var deviceUsedBytes: Int64 = 0
    
    /// Scans the entire library, categorizes media, and measures realistic on-device storage.
    /// Uses physical disk capacity as an absolute ceiling to prevent impossible values.
    public func scanLibrary(completion: @escaping () -> Void) {
        guard authorizationStatus == .authorized || authorizationStatus == .limited else {
            completion()
            return
        }
        
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            guard let self = self else { return }
            
            // ─── Step 1: Measure physical device storage ────────────────────────
            // Use volumeAvailableCapacityKey (NOT ForImportantUsage) — the "important" variant
            // can return a value LARGER than totalDisk (it includes purgeable future space),
            // which causes usedDisk = max(0, total - free) = 0, defeating the clamp entirely.
            let homeURL = URL(fileURLWithPath: NSHomeDirectory())
            var totalDisk: Int64 = 256 * 1024 * 1024 * 1024 // safe default: 256 GB
            var freeDisk: Int64 = 0
            
            if let vals = try? homeURL.resourceValues(forKeys: [
                .volumeTotalCapacityKey,
                .volumeAvailableCapacityKey      // standard free space (no purgeable inflation)
            ]) {
                if let total = vals.volumeTotalCapacity, total > 0 {
                    totalDisk = Int64(total)
                }
                if let free = vals.volumeAvailableCapacity, free > 0 {
                    freeDisk = Int64(free)
                }
            }
            let usedDisk = max(0, totalDisk - freeDisk)
            
            // ─── Step 2: Scan and categorize all assets ─────────────────────────
            let fetchOptions = PHFetchOptions()
            fetchOptions.includeAssetSourceTypes = [.typeUserLibrary, .typeCloudShared, .typeiTunesSynced]
            let allAssets = PHAsset.fetchAssets(with: fetchOptions)
            
            var photos = 0
            var videos = 0
            var livePhotos = 0
            
            var sampledPhotoBytes: Int64 = 0
            var sampledPhotoCount = 0
            var sampledVideoBytes: Int64 = 0
            var sampledVideoCount = 0
            var sampledLiveBytes: Int64 = 0
            var sampledLiveCount = 0
            
            allAssets.enumerateObjects { asset, _, _ in
                if asset.mediaSubtypes.contains(.photoLive) {
                    livePhotos += 1
                    if sampledLiveCount < 30 {
                        let res = PHAssetResource.assetResources(for: asset)
                        let size = res.compactMap { $0.value(forKey: "fileSize") as? Int64 }.reduce(0, +)
                        if size > 0 { sampledLiveBytes += size; sampledLiveCount += 1 }
                    }
                } else if asset.mediaType == .image {
                    photos += 1
                    if sampledPhotoCount < 40 {
                        let res = PHAssetResource.assetResources(for: asset)
                        if let size = res.first?.value(forKey: "fileSize") as? Int64, size > 0 {
                            sampledPhotoBytes += size; sampledPhotoCount += 1
                        }
                    }
                } else if asset.mediaType == .video {
                    videos += 1
                    if sampledVideoCount < 30 {
                        let res = PHAssetResource.assetResources(for: asset)
                        if let size = res.first?.value(forKey: "fileSize") as? Int64, size > 0 {
                            sampledVideoBytes += size; sampledVideoCount += 1
                        }
                    }
                }
            }
            
            // ─── Step 3: Compute per-type averages ──────────────────────────────
            let avgPhoto = sampledPhotoCount > 0 ? (sampledPhotoBytes / Int64(sampledPhotoCount)) : 1_100_000
            let avgLive  = sampledLiveCount  > 0 ? (sampledLiveBytes  / Int64(sampledLiveCount))  : 3_200_000
            let avgVideo = sampledVideoCount > 0 ? (sampledVideoBytes / Int64(sampledVideoCount)) : 10_000_000
            
            var estimatedBytes = (Int64(photos) * avgPhoto) +
                                 (Int64(livePhotos) * avgLive) +
                                 (Int64(videos) * avgVideo)
            
            // ─── Step 4: Apply hard physical ceilings (order matters) ────────────
            // CEILING 1 — Absolute: cannot exceed total device capacity (physical law)
            estimatedBytes = min(estimatedBytes, totalDisk)
            
            // CEILING 2 — Soft: cap at 80% of actually used storage if available
            if usedDisk > 0 && estimatedBytes > usedDisk {
                estimatedBytes = Int64(Double(usedDisk) * 0.80)
            }
            
            // ─── Step 5: Discover user albums ────────────────────────────────────
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
                self.deviceTotalBytes = totalDisk
                self.deviceUsedBytes = usedDisk
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
