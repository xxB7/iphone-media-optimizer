import Foundation
import SwiftUI
import Photos

@MainActor
public class OptimizerViewModel: ObservableObject {
    
    @Published public var selectedFilterTitle: String = "كامل الاستديو"
    @Published public var customAssetsToProcess: [PHAsset]? = nil
    @Published public var lastSession: OptimizationSession? = nil
    @Published public var showCompletionAlert: Bool = false
    
    public let batchOptimizer: BatchOptimizer
    public let photoService: PhotoLibraryService
    public let auditStore: AuditLogStore
    
    public init(batchOptimizer: BatchOptimizer, photoService: PhotoLibraryService, auditStore: AuditLogStore) {
        self.batchOptimizer = batchOptimizer
        self.photoService = photoService
        self.auditStore = auditStore
    }
    
    public var formattedSavedSpace: String {
        let formatter = ByteCountFormatter()
        formatter.allowedUnits = [.useGB, .useMB]
        formatter.countStyle = .file
        return formatter.string(fromByteCount: batchOptimizer.totalSavedBytes)
    }
    
    public var formattedRemainingTime: String {
        let seconds = Int(batchOptimizer.estimatedRemainingSeconds)
        if seconds <= 0 { return "جاري الحساب..." }
        let minutes = seconds / 60
        let remSec = seconds % 60
        if minutes > 0 {
            return "\(minutes) دقيقة و \(remSec) ثانية"
        }
        return "\(remSec) ثانية"
    }
    
    public func start(config: CompressionConfig) {
        let fetchOptions = PHFetchOptions()
        fetchOptions.includeAssetSourceTypes = [.typeUserLibrary, .typeCloudShared, .typeiTunesSynced]
        
        let targetAssets: [PHAsset]
        if let custom = customAssetsToProcess, !custom.isEmpty {
            targetAssets = custom
        } else {
            let all = PHAsset.fetchAssets(with: fetchOptions)
            var list: [PHAsset] = []
            all.enumerateObjects { asset, _, _ in
                list.append(asset)
            }
            targetAssets = list
        }
        
        batchOptimizer.startOptimization(assets: targetAssets, config: config) { [weak self] session in
            self?.auditStore.saveSession(session)
            self?.lastSession = session
            self?.showCompletionAlert = true
            self?.photoService.scanLibrary {}
        }
    }
    
    public func pause() {
        batchOptimizer.pause()
    }
    
    public func resume() {
        batchOptimizer.resume()
    }
    
    public func cancel() {
        batchOptimizer.cancel()
    }
}
