import SwiftUI
import Photos

public struct ContentView: View {
    
    @StateObject private var photoManager = PhotoKitManager()
    @StateObject private var thermalGuard = ThermalGuard()
    
    @State private var isProcessing: Bool = false
    @State private var progress: Double = 0.0
    @State private var processedCount: Int = 0
    @State private var savedMegabytes: Double = 0.0
    
    public init() {}
    
    public var body: some View {
        NavigationView {
            ZStack {
                Color(.systemGroupedBackground)
                    .ignoresSafeArea()
                
                VStack(spacing: 24) {
                    // Header Dashboard Card
                    VStack(spacing: 12) {
                        Image(systemName: "photo.stack.fill")
                            .font(.system(size: 48))
                            .foregroundColor(.blue)
                        
                        Text("مخفف استديو الآيفون")
                            .font(.title2.bold())
                        
                        Text("ضغط عتادي آمن • حفاظ 100% على التواريخ والألبومات")
                            .font(.caption)
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.center)
                    }
                    .padding()
                    .frame(maxWidth: .infinity)
                    .background(Color(.secondarySystemGroupedBackground))
                    .cornerRadius(16)
                    .shadow(color: Color.black.opacity(0.04), radius: 8, x: 0, y: 2)
                    
                    // Library Stats Grid
                    HStack(spacing: 16) {
                        StatCard(title: "الصور", count: "\(photoManager.totalPhotoCount)", icon: "photo", color: .blue)
                        StatCard(title: "الفيديوهات", count: "\(photoManager.totalVideoCount)", icon: "video.fill", color: .purple)
                        StatCard(title: "صور حية", count: "\(photoManager.totalLivePhotoCount)", icon: "livephoto", color: .green)
                    }
                    
                    // Thermal & Safety Status
                    if thermalGuard.shouldThrottle {
                        HStack {
                            Image(systemName: "flame.fill")
                                .foregroundColor(.orange)
                            Text("حرارة الجهاز مرتفعة، تم تهدئة سرعة المعالجة لحماية البطارية.")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                        .padding(10)
                        .background(Color.orange.opacity(0.1))
                        .cornerRadius(10)
                    }
                    
                    Spacer()
                    
                    // Progress Indicator (during processing)
                    if isProcessing {
                        VStack(spacing: 8) {
                            ProgressView(value: progress, total: 1.0)
                                .accentColor(.blue)
                            Text("جاري الضغط والتحقق... (\(processedCount))")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                        .padding()
                    }
                    
                    // Main Action Button
                    Button(action: {
                        startOptimization()
                    }) {
                        HStack {
                            Image(systemName: isProcessing ? "pause.fill" : "bolt.fill")
                            Text(isProcessing ? "إيقاف مؤقت" : "بدء التخفيف الذكي")
                                .fontWeight(.semibold)
                        }
                        .font(.headline)
                        .foregroundColor(.white)
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(isProcessing ? Color.orange : Color.blue)
                        .cornerRadius(14)
                    }
                }
                .padding(20)
            }
            .navigationBarTitleDisplayMode(.inline)
            .onAppear {
                photoManager.scanLibrary {}
            }
        }
    }
    
    private func startOptimization() {
        if photoManager.authorizationStatus != .authorized && photoManager.authorizationStatus != .limited {
            photoManager.requestPermission { granted in
                if granted {
                    photoManager.scanLibrary {}
                }
            }
            return
        }
        
        isProcessing.toggle()
    }
}

struct StatCard: View {
    let title: String
    let count: String
    let icon: String
    let color: Color
    
    var body: some View {
        VStack(spacing: 8) {
            Image(systemName: icon)
                .font(.title3)
                .foregroundColor(color)
            Text(count)
                .font(.title3.bold())
            Text(title)
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 16)
        .background(Color(.secondarySystemGroupedBackground))
        .cornerRadius(14)
    }
}
