import Foundation
import Photos

/// Preserves album associations so optimized media returns to its exact original albums.
public class AlbumPreserver {
    
    public init() {}
    
    /// Finds all user albums an asset belongs to.
    public func getContainingAlbums(for asset: PHAsset) -> [PHAssetCollection] {
        var collections: [PHAssetCollection] = []
        let albums = PHAssetCollection.fetchAssetCollectionsContaining(asset, with: .album, options: nil)
        albums.enumerateObjects { collection, _, _ in
            collections.append(collection)
        }
        return collections
    }
    
    /// Inserts an asset into multiple target albums.
    public func addAsset(_ asset: PHAsset, to collections: [PHAssetCollection], completion: @escaping (Bool) -> Void) {
        guard !collections.isEmpty else {
            completion(true)
            return
        }
        
        PHPhotoLibrary.shared().performChanges({
            for collection in collections {
                if let albumChangeRequest = PHAssetCollectionChangeRequest(for: collection) {
                    albumChangeRequest.addAssets([asset] as NSArray)
                }
            }
        }) { success, _ in
            completion(success)
        }
    }
}
