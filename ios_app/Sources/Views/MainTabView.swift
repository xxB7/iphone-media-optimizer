import SwiftUI

public struct MainTabView: View {
    
    @StateObject private var photoService = PhotoLibraryService()
    @StateObject private var thermalGuard = ThermalGuard()
    @StateObject private var auditStore = AuditLogStore()
    
    @StateObject private var dashboardViewModel: DashboardViewModel
    @StateObject private var optimizerViewModel: OptimizerViewModel
    @StateObject private var albumsViewModel: AlbumsViewModel
    @StateObject private var settingsViewModel = SettingsViewModel()
    
    @State private var selectedTab: Int = 0
    
    public init() {
        let photo = PhotoLibraryService()
        let thermal = ThermalGuard()
        let audit = AuditLogStore()
        let batch = BatchOptimizer(photoService: photo, thermalGuard: thermal)
        
        _photoService = StateObject(wrappedValue: photo)
        _thermalGuard = StateObject(wrappedValue: thermal)
        _auditStore = StateObject(wrappedValue: audit)
        
        _dashboardViewModel = StateObject(wrappedValue: DashboardViewModel(photoService: photo, auditStore: audit))
        _optimizerViewModel = StateObject(wrappedValue: OptimizerViewModel(batchOptimizer: batch, photoService: photo, auditStore: audit))
        _albumsViewModel = StateObject(wrappedValue: AlbumsViewModel(photoService: photo))
    }
    
    public var body: some View {
        TabView(selection: $selectedTab) {
            
            DashboardView(viewModel: dashboardViewModel, selectedTab: $selectedTab)
                .tabItem {
                    Label("الرئيسية", systemImage: "sparkles")
                }
                .tag(0)
            
            OptimizerView(viewModel: optimizerViewModel, settingsViewModel: settingsViewModel)
                .tabItem {
                    Label("التحسين الحي", systemImage: "bolt.circle.fill")
                }
                .tag(1)
            
            AlbumsView(albumsViewModel: albumsViewModel, optimizerViewModel: optimizerViewModel, selectedTab: $selectedTab)
                .tabItem {
                    Label("الألبومات", systemImage: "rectangle.stack.fill")
                }
                .tag(2)
            
            SettingsView(settingsViewModel: settingsViewModel, auditStore: auditStore)
                .tabItem {
                    Label("الإعدادات", systemImage: "slider.horizontal.3")
                }
                .tag(3)
        }
        .environment(\.layoutDirection, .rightToLeft) // Native RTL support
        .accentColor(.blue)
    }
}
