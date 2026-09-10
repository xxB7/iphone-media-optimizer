import Foundation
import SwiftUI
import Photos

@MainActor
public class DashboardViewModel: ObservableObject {
    
    @Published public var totalPhotos: Int = 0
    @Published public var totalVideos: Int = 0
    @Published public var totalLivePhotos: Int = 0
    @Published public var formattedEstimatedStorage: String = "0 GB"
    @Published public var formattedPotentialSavings: String = "0 GB"
    @Published public var isScanning: Bool = false
    @Published public var hasPermission: Bool = false
    
    public let photoService: PhotoLibraryService
    public let auditStore: AuditLogStore
    
    public init(photoService: PhotoLibraryService, auditStore: AuditLogStore) {
        self.photoService = photoService
        self.auditStore = auditStore
        checkInitialPermission()
    }
    
    public func checkInitialPermission() {
        let status = photoService.authorizationStatus
        self.hasPermission = (status == .authorized || status == .limited)
        if hasPermission {
            refreshLibrary()
        }
    }
    
    public func requestAccess(completion: @escaping (Bool) -> Void) {
        photoService.requestPermission { [weak self] granted in
            self?.hasPermission = granted
            if granted {
                self?.refreshLibrary()
            }
            completion(granted)
        }
    }
    
    public func refreshLibrary() {
        self.isScanning = true
        photoService.scanLibrary { [weak self] in
            guard let self = self else { return }
            self.totalPhotos = self.photoService.totalPhotoCount
            self.totalVideos = self.photoService.totalVideoCount
            self.totalLivePhotos = self.photoService.totalLivePhotoCount
            
            let formatter = ByteCountFormatter()
            formatter.allowedUnits = [.useGB, .useMB]
            formatter.countStyle = .file
            self.formattedEstimatedStorage = formatter.string(fromByteCount: self.photoService.estimatedTotalBytes)
            
            // Expected average saving is ~65% of total library footprint
            let potentialBytes = Int64(Double(self.photoService.estimatedTotalBytes) * 0.65)
            self.formattedPotentialSavings = formatter.string(fromByteCount: potentialBytes)
            
            self.isScanning = false
        }
    }
}
