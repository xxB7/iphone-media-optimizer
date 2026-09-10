import Foundation
import Photos
import UIKit
import AVFoundation

/// Production batch processor orchestrating the end-to-end media optimization pipeline.
/// Implements Zero-OOM memory chunking, background task protection, thermal throttling,
/// and live UI progress callbacks.
public class BatchOptimizer: ObservableObject {
    
    public enum State {
        case idle
        case running
        case paused
        case completed
        case cancelled
    }
    
    @Published public var state: State = .idle
    @Published public var progress: Double = 0.0
    @Published public var processedCount: Int = 0
    @Published public var totalCount: Int = 0
    @Published public var totalSavedBytes: Int64 = 0
    @Published public var currentItemTitle: String = ""
    @Published public var currentThumbnail: UIImage? = nil
    @Published public var itemsPerMinute: Double = 0.0
    @Published public var estimatedRemainingSeconds: TimeInterval = 0.0
    @Published public var errorMessage: String? = nil
    
    private let photoService: PhotoLibraryService
    private let imageOptimizer: ImageOptimizer
    private let videoOptimizer: VideoOptimizer
    private let livePhotoEngine: LivePhotoEngine
    private let albumPreserver: AlbumPreserver
    private let thermalGuard: ThermalGuard
    
    private var isCancelled: Bool = false
    private var isPausedInternal: Bool = false
    private var backgroundTaskId: UIBackgroundTaskIdentifier = .invalid
    private var startTime: Date?
    
    public init(
        photoService: PhotoLibraryService = PhotoLibraryService(),
        thermalGuard: ThermalGuard = ThermalGuard()
    ) {
        self.photoService = photoService
        self.imageOptimizer = ImageOptimizer()
        self.videoOptimizer = VideoOptimizer()
        self.livePhotoEngine = LivePhotoEngine()
        self.albumPreserver = AlbumPreserver()
        self.thermalGuard = thermalGuard
    }
    
    /// Starts batch optimization for a list of assets or specific selected albums.
    public func startOptimization(
        assets: [PHAsset],
        config: CompressionConfig,
        onSessionComplete: @escaping (OptimizationSession) -> Void
    ) {
        guard state == .idle || state == .completed || state == .cancelled else { return }
        guard !assets.isEmpty else { return }
        
        self.state = .running
        self.isCancelled = false
        self.isPausedInternal = false
        self.processedCount = 0
        self.totalCount = assets.count
        self.totalSavedBytes = 0
        self.progress = 0.0
        self.startTime = Date()
        
        beginBackgroundTask()
        
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            guard let self = self else { return }
            
            var session = OptimizationSession()
            var originalsToCleanup: [PHAsset] = []
            
            // Process in chunks of 10 to ensure zero memory accumulation
            let chunkSize = 10
            var currentIndex = 0
            
            while currentIndex < assets.count && !self.isCancelled {
                // Handle pause loop
                while self.isPausedInternal && !self.isCancelled {
                    Thread.sleep(forTimeInterval: 0.5)
                }
                if self.isCancelled { break }
                
                // Thermal safety throttle
                if config.enableThermalGuard && self.thermalGuard.shouldThrottle {
                    Thread.sleep(forTimeInterval: 1.5)
                }
                
                let chunkEnd = min(currentIndex + chunkSize, assets.count)
                let currentChunk = Array(assets[currentIndex..<chunkEnd])
                
                for asset in currentChunk {
                    if self.isCancelled { break }
                    
                    while self.isPausedInternal && !self.isCancelled {
                        Thread.sleep(forTimeInterval: 0.5)
                    }
                    
                    // Enforce Zero-OOM via autoreleasepool
                    autoreleasepool {
                        let semaphore = DispatchSemaphore(value: 0)
                        
                        self.processSingleAsset(asset: asset, config: config) { result in
                            switch result {
                            case .success(let savedBytes):
                                self.totalSavedBytes += savedBytes
                                session.totalSavedBytes += savedBytes
                                if asset.mediaSubtypes.contains(.photoLive) {
                                    session.livePhotosOptimized += 1
                                } else if asset.mediaType == .image {
                                    session.photosOptimized += 1
                                } else if asset.mediaType == .video {
                                    session.videosOptimized += 1
                                }
                                originalsToCleanup.append(asset)
                            case .failure(let error):
                                session.failedCount += 1
                                print("Skipped/Failed asset: \(error.localizedDescription)")
                            }
                            semaphore.signal()
                        }
                        
                        _ = semaphore.wait(timeout: .now() + 120.0) // 2 min max per asset
                    }
                    
                    self.processedCount += 1
                    session.totalProcessed = self.processedCount
                    
                    // Update UI telemetry
                    self.updateTelemetry()
                }
                
                // If direct replace mode, trigger batch delete for completed chunk
                if config.safetyMode == .directReplace && !originalsToCleanup.isEmpty {
                    let cleanupBatch = originalsToCleanup
                    originalsToCleanup.removeAll()
                    self.photoService.deleteOriginalAssets(cleanupBatch) { _, _ in }
                }
                
                currentIndex = chunkEnd
            }
            
            // Finalize session
            DispatchQueue.main.async {
                self.state = self.isCancelled ? .cancelled : .completed
                self.endBackgroundTask()
                onSessionComplete(session)
            }
        }
    }
    
    public func pause() {
        guard state == .running else { return }
        isPausedInternal = true
        state = .paused
    }
    
    public func resume() {
        guard state == .paused else { return }
        isPausedInternal = false
        state = .running
    }
    
    public func cancel() {
        isCancelled = true
        isPausedInternal = false
        state = .cancelled
    }
    
    private func processSingleAsset(
        asset: PHAsset,
        config: CompressionConfig,
        completion: @escaping (Result<Int64, Error>) -> Void
    ) {
        // Fetch original containing albums to preserve categorization
        let containingAlbums = albumPreserver.getContainingAlbums(for: asset)
        
        // Update thumbnail for UI
        fetchThumbnail(for: asset)
        
        if asset.mediaSubtypes.contains(.photoLive) && config.preserveLivePhotos {
            processLivePhoto(asset: asset, containingAlbums: containingAlbums, config: config, completion: completion)
        } else if asset.mediaType == .image {
            processImage(asset: asset, containingAlbums: containingAlbums, config: config, completion: completion)
        } else if asset.mediaType == .video {
            processVideo(asset: asset, containingAlbums: containingAlbums, config: config, completion: completion)
        } else {
            completion(.failure(NSError(domain: "BatchOptimizer", code: -1, userInfo: [NSLocalizedDescriptionKey: "نوع وسائط غير مدعوم"])))
        }
    }
    
    private func processImage(
        asset: PHAsset,
        containingAlbums: [PHAssetCollection],
        config: CompressionConfig,
        completion: @escaping (Result<Int64, Error>) -> Void
    ) {
        let options = PHImageRequestOptions()
        options.isNetworkAccessAllowed = true
        options.version = .original
        options.isSynchronous = false
        
        PHImageManager.default().requestImageDataAndOrientation(for: asset, options: options) { [weak self] data, _, _, info in
            guard let self = self, let originalData = data else {
                completion(.failure(NSError(domain: "BatchOptimizer", code: -2, userInfo: [NSLocalizedDescriptionKey: "تعذر تحميل بيانات الصورة"])))
                return
            }
            
            let originalBytes = Int64(originalData.count)
            let minSkipBytes = Int64(config.skipFilesUnderMB * 1024 * 1024)
            if originalBytes < minSkipBytes {
                completion(.failure(NSError(domain: "BatchOptimizer", code: -3, userInfo: [NSLocalizedDescriptionKey: "الحجم أصغر من حد التخطي"])))
                return
            }
            
            guard let compressedData = self.imageOptimizer.compressImageData(originalData, quality: config.imageQuality) else {
                completion(.failure(NSError(domain: "BatchOptimizer", code: -4, userInfo: [NSLocalizedDescriptionKey: "فشل ضغط الصورة"])))
                return
            }
            
            let compressedBytes = Int64(compressedData.count)
            guard compressedBytes < originalBytes else {
                completion(.failure(NSError(domain: "BatchOptimizer", code: -5, userInfo: [NSLocalizedDescriptionKey: "النسخة المضغوطة ليست أصغر من الأصل"])))
                return
            }
            
            // Save compressed photo to library with albums
            PHPhotoLibrary.shared().performChanges({
                let request = PHAssetCreationRequest.forAsset()
                request.addResource(with: .photo, data: compressedData, options: nil)
                request.creationDate = asset.creationDate
                request.location = asset.location
                request.isFavorite = asset.isFavorite
                
                for album in containingAlbums {
                    if let albumReq = PHAssetCollectionChangeRequest(for: album),
                       let placeholder = request.placeholderForCreatedAsset {
                        albumReq.addAssets([placeholder] as NSArray)
                    }
                }
            }) { success, error in
                if success {
                    let saved = originalBytes - compressedBytes
                    completion(.success(saved))
                } else {
                    completion(.failure(error ?? NSError(domain: "BatchOptimizer", code: -6, userInfo: [NSLocalizedDescriptionKey: "فشل كتابة الصورة الجديدة في الاستديو"])))
                }
            }
        }
    }
    
    private func processVideo(
        asset: PHAsset,
        containingAlbums: [PHAssetCollection],
        config: CompressionConfig,
        completion: @escaping (Result<Int64, Error>) -> Void
    ) {
        let options = PHVideoRequestOptions()
        options.isNetworkAccessAllowed = true
        options.version = .original
        
        PHImageManager.default().requestAVAsset(forVideo: asset, options: options) { [weak self] avAsset, _, _ in
            guard let self = self, let urlAsset = avAsset as? AVURLAsset else {
                completion(.failure(NSError(domain: "BatchOptimizer", code: -7, userInfo: [NSLocalizedDescriptionKey: "تعذر قراءة ملف الفيديو الأصلي"])))
                return
            }
            
            let sourceURL = urlAsset.url
            let originalBytes = (try? FileManager.default.attributesOfItem(atPath: sourceURL.path)[.size] as? NSNumber)?.int64Value ?? 0
            
            self.videoOptimizer.compressVideo(sourceURL: sourceURL, preset: config.videoPreset) { result in
                switch result {
                case .success(let (destURL, compressedBytes)):
                    guard compressedBytes < originalBytes && originalBytes > 0 else {
                        try? FileManager.default.removeItem(at: destURL)
                        completion(.failure(NSError(domain: "BatchOptimizer", code: -8, userInfo: [NSLocalizedDescriptionKey: "حجم الفيديو لم ينقص"])))
                        return
                    }
                    
                    PHPhotoLibrary.shared().performChanges({
                        let request = PHAssetCreationRequest.forAsset()
                        request.addResource(with: .video, fileURL: destURL, options: nil)
                        request.creationDate = asset.creationDate
                        request.location = asset.location
                        request.isFavorite = asset.isFavorite
                        
                        for album in containingAlbums {
                            if let albumReq = PHAssetCollectionChangeRequest(for: album),
                               let placeholder = request.placeholderForCreatedAsset {
                                albumReq.addAssets([placeholder] as NSArray)
                            }
                        }
                    }) { success, error in
                        try? FileManager.default.removeItem(at: destURL)
                        if success {
                            completion(.success(originalBytes - compressedBytes))
                        } else {
                            completion(.failure(error ?? NSError(domain: "BatchOptimizer", code: -9, userInfo: [NSLocalizedDescriptionKey: "فشل إدراج الفيديو المضغوط في الاستديو"])))
                        }
                    }
                case .failure(let error):
                    completion(.failure(error))
                }
            }
        }
    }
    
    private func processLivePhoto(
        asset: PHAsset,
        containingAlbums: [PHAssetCollection],
        config: CompressionConfig,
        completion: @escaping (Result<Int64, Error>) -> Void
    ) {
        livePhotoEngine.extractLivePhotoResources(asset: asset) { [weak self] result in
            guard let self = self else { return }
            switch result {
            case .success(let (photoData, videoURL)):
                let origPhotoBytes = Int64(photoData.count)
                let origVideoBytes = (try? FileManager.default.attributesOfItem(atPath: videoURL.path)[.size] as? NSNumber)?.int64Value ?? 0
                let totalOriginal = origPhotoBytes + origVideoBytes
                
                guard let compPhotoData = self.imageOptimizer.compressImageData(photoData, quality: config.imageQuality) else {
                    try? FileManager.default.removeItem(at: videoURL)
                    completion(.failure(NSError(domain: "BatchOptimizer", code: -10, userInfo: [NSLocalizedDescriptionKey: "فشل ضغط صورة Live Photo"])))
                    return
                }
                
                self.videoOptimizer.compressVideo(sourceURL: videoURL, preset: .hevc1080p) { vidResult in
                    try? FileManager.default.removeItem(at: videoURL)
                    
                    switch vidResult {
                    case .success(let (compVideoURL, compVidBytes)):
                        let totalCompressed = Int64(compPhotoData.count) + compVidBytes
                        
                        self.livePhotoEngine.createCompressedLivePhoto(
                            imageData: compPhotoData,
                            videoURL: compVideoURL,
                            targetCollections: containingAlbums
                        ) { creationResult in
                            try? FileManager.default.removeItem(at: compVideoURL)
                            switch creationResult {
                            case .success:
                                let saved = max(0, totalOriginal - totalCompressed)
                                completion(.success(saved))
                            case .failure(let error):
                                completion(.failure(error))
                            }
                        }
                    case .failure(let error):
                        completion(.failure(error))
                    }
                }
            case .failure(let error):
                completion(.failure(error))
            }
        }
    }
    
    private func fetchThumbnail(for asset: PHAsset) {
        let size = CGSize(width: 120, height: 120)
        let options = PHImageRequestOptions()
        options.isNetworkAccessAllowed = false
        options.deliveryMode = .fastFormat
        
        PHImageManager.default().requestImage(for: asset, targetSize: size, contentMode: .aspectFill, options: options) { [weak self] image, _ in
            DispatchQueue.main.async {
                self?.currentThumbnail = image
                self?.currentItemTitle = asset.localIdentifier.components(separatedBy: "/").first ?? "ملف وسائط"
            }
        }
    }
    
    private func updateTelemetry() {
        DispatchQueue.main.async { [weak self] in
            guard let self = self, let start = self.startTime, self.totalCount > 0 else { return }
            
            self.progress = Double(self.processedCount) / Double(self.totalCount)
            
            let elapsed = Date().timeIntervalSince(start)
            if elapsed > 1.0 && self.processedCount > 0 {
                let speedPerSec = Double(self.processedCount) / elapsed
                self.itemsPerMinute = speedPerSec * 60.0
                
                let remainingItems = self.totalCount - self.processedCount
                self.estimatedRemainingSeconds = Double(remainingItems) / speedPerSec
            }
        }
    }
    
    private func beginBackgroundTask() {
        backgroundTaskId = UIApplication.shared.beginBackgroundTask(withName: "KhafeefBatchOptimizer") { [weak self] in
            self?.endBackgroundTask()
        }
    }
    
    private func endBackgroundTask() {
        if backgroundTaskId != .invalid {
            UIApplication.shared.endBackgroundTask(backgroundTaskId)
            backgroundTaskId = .invalid
        }
    }
}
