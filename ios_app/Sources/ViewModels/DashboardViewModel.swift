import Foundation
import SwiftUI
import Photos
import UIKit

@MainActor
public class DashboardViewModel: ObservableObject {
    
    @Published public var totalPhotos: Int = 0
    @Published public var totalVideos: Int = 0
    @Published public var totalLivePhotos: Int = 0
    @Published public var formattedEstimatedStorage: String = "0 GB"
    @Published public var formattedPotentialSavings: String = "0 GB"
    @Published public var isScanning: Bool = false
    @Published public var hasPermission: Bool = false
    @Published public var isPermissionDenied: Bool = false
    
    public let photoService: PhotoLibraryService
    public let auditStore: AuditLogStore
    
    public init(photoService: PhotoLibraryService, auditStore: AuditLogStore) {
        self.photoService = photoService
        self.auditStore = auditStore
        checkAndRequestPermission()
    }
    
    public func checkAndRequestPermission() {
        let status = photoService.authorizationStatus
        if status == .authorized || status == .limited {
            self.hasPermission = true
            self.isPermissionDenied = false
            refreshLibrary()
        } else if status == .notDetermined {
            requestAccess { _ in }
        } else {
            self.hasPermission = false
            self.isPermissionDenied = true
        }
    }
    
    public func requestAccess(completion: @escaping (Bool) -> Void) {
        photoService.requestPermission { [weak self] granted in
            guard let self = self else { return }
            self.hasPermission = granted
            self.isPermissionDenied = !granted
            if granted {
                self.refreshLibrary()
            }
            completion(granted)
        }
    }
    
    public func openSettings() {
        if let url = URL(string: UIApplication.openSettingsURLString), UIApplication.shared.canOpenURL(url) {
            UIApplication.shared.open(url)
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
