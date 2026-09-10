import Foundation
import SwiftUI
import Photos

@MainActor
public class AlbumsViewModel: ObservableObject {
    
    @Published public var albums: [AlbumInfo] = []
    @Published public var isSelectAll: Bool = true
    
    public let photoService: PhotoLibraryService
    
    public init(photoService: PhotoLibraryService) {
        self.photoService = photoService
        self.albums = photoService.availableAlbums
    }
    
    public func refresh() {
        photoService.scanLibrary { [weak self] in
            guard let self = self else { return }
            self.albums = self.photoService.availableAlbums
        }
    }
    
    public func toggleSelectAll() {
        isSelectAll.toggle()
        for i in 0..<albums.count {
            albums[i].isSelected = isSelectAll
        }
    }
    
    public func toggleAlbum(_ albumId: String) {
        if let index = albums.firstIndex(where: { $0.id == albumId }) {
            albums[index].isSelected.toggle()
        }
    }
    
    /// Fetches all assets belonging to selected albums.
    public func fetchSelectedAssets() -> [PHAsset] {
        var assets: [PHAsset] = []
        let selected = albums.filter { $0.isSelected }
        
        for album in selected {
            let result = PHAsset.fetchAssets(in: album.collection, options: nil)
            result.enumerateObjects { asset, _, _ in
                if !assets.contains(where: { $0.localIdentifier == asset.localIdentifier }) {
                    assets.append(asset)
                }
            }
        }
        return assets
    }
}
