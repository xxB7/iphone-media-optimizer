import Foundation
import ImageIO
import UniformTypeIdentifiers
import CoreGraphics

/// High-performance native image compression using Apple ImageIO.
/// Preserves 100% of EXIF, TIFF, and GPS metadata.
public class ImageCompressor {
    
    public init() {}
    
    /// Compresses an image data buffer to HEIC or JPEG with custom compression quality.
    /// Retains all EXIF, GPS, and camera metadata dictionaries.
    public func compressImageData(
        _ sourceData: Data,
        targetFormat: UTType = .heic,
        quality: Float = 0.75
    ) -> Data? {
        guard let imageSource = CGImageSourceCreateWithData(sourceData as CFData, nil) else {
            return nil
        }
        
        // Extract existing metadata dictionary
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
            return nil
        }
        
        // Prepare destination options: merge original metadata with compression quality
        var destinationProperties = imageProperties
        destinationProperties[kCGImageDestinationLossyCompressionQuality] = quality
        
        CGImageDestinationAddImageFromSource(imageDestination, imageSource, 0, destinationProperties as CFDictionary)
        
        guard CGImageDestinationFinalize(imageDestination) else {
            return nil
        }
        
        return outputData as Data
    }
}
