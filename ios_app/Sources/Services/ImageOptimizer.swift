import Foundation
import ImageIO
import UniformTypeIdentifiers
import CoreGraphics

/// High-performance native image compression using Apple ImageIO.
/// Preserves 100% of EXIF, TIFF, Color Profiles, and GPS metadata.
public class ImageOptimizer {
    
    public init() {}
    
    /// Compresses image data to HEIC (or JPEG fallback) while preserving full metadata.
    public func compressImageData(
        _ sourceData: Data,
        quality: Float = 0.75,
        targetFormat: UTType = .heic
    ) -> Data? {
        guard let imageSource = CGImageSourceCreateWithData(sourceData as CFData, nil) else {
            return nil
        }
        
        let options: [CFString: Any] = [kCGImageSourceShouldCache: false]
        guard let imageProperties = CGImageSourceCopyPropertiesAtIndex(imageSource, 0, options as CFDictionary) as? [CFString: Any] else {
            return nil
        }
        
        let outputData = NSMutableData()
        guard let imageDestination = CGImageDestinationCreateWithData(
            outputData as CFMutableData,
            targetFormat.identifier as CFString,
            1,
            nil
        ) else {
            // Fallback to JPEG if HEIC destination cannot be created
            if targetFormat == .heic {
                return compressImageData(sourceData, quality: quality, targetFormat: .jpeg)
            }
            return nil
        }
        
        var destinationProperties = imageProperties
        destinationProperties[kCGImageDestinationLossyCompressionQuality] = quality
        
        CGImageDestinationAddImageFromSource(imageDestination, imageSource, 0, destinationProperties as CFDictionary)
        
        guard CGImageDestinationFinalize(imageDestination) else {
            return nil
        }
        
        return outputData as Data
    }
}
