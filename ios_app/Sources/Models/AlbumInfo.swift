import Foundation
import Photos

public struct AlbumInfo: Identifiable, Equatable {
    public let id: String
    public let title: String
    public let count: Int
    public let collection: PHAssetCollection
    public var isSelected: Bool
    
    public init(id: String, title: String, count: Int, collection: PHAssetCollection, isSelected: Bool = true) {
        self.id = id
        self.title = title
        self.count = count
        self.collection = collection
        self.isSelected = isSelected
    }
    
    public static func == (lhs: AlbumInfo, rhs: AlbumInfo) -> Bool {
        return lhs.id == rhs.id && lhs.isSelected == rhs.isSelected && lhs.count == rhs.count
    }
}
