import SwiftUI
import Photos

public struct DashboardView: View {
    
    @ObservedObject var viewModel: DashboardViewModel
    @Binding var selectedTab: Int
    
    public init(viewModel: DashboardViewModel, selectedTab: Binding<Int>) {
        self.viewModel = viewModel
        self._selectedTab = selectedTab
    }
    
    public var body: some View {
        NavigationView {
            ScrollView {
                VStack(spacing: 20) {
                    
                    // Permission Denied Warning Card
                    if viewModel.isPermissionDenied {
                        VStack(alignment: .leading, spacing: 10) {
                            HStack {
                                Image(systemName: "exclamationmark.triangle.fill")
                                    .font(.title3)
                                    .foregroundColor(.orange)
                                Text("إذن الوصول للصور معطّل")
                                    .font(.headline)
                                    .foregroundColor(.primary)
                                Spacer()
                            }
                            Text("يحتاج تطبيق خفيف إلى إذن قراءة وتعديل الصور ليتمكن من حساب المساحة وضغط الاستديو بأمان.")
                                .font(.caption)
                                .foregroundColor(.secondary)
                            
                            Button(action: {
                                viewModel.openSettings()
                            }) {
                                HStack {
                                    Image(systemName: "gear")
                                    Text("فتح إعدادات الآيفون لمنح الإذن")
                                        .bold()
                                }
                                .font(.caption)
                                .foregroundColor(.white)
                                .frame(maxWidth: .infinity)
                                .padding(10)
                                .background(Color.orange)
                                .cornerRadius(10)
                            }
                        }
                        .padding(16)
                        .background(Color.orange.opacity(0.12))
                        .cornerRadius(16)
                    }
                    
                    // Hero Savings Card
                    VStack(spacing: 16) {
                        HStack {
                            VStack(alignment: .leading, spacing: 4) {
                                Text("توفير متوقع لمساحة الاستديو")
                                    .font(.subheadline)
                                    .foregroundColor(.white.opacity(0.85))
                                Text(viewModel.formattedPotentialSavings)
                                    .font(.system(size: 38, weight: .heavy, design: .rounded))
                                    .foregroundColor(.white)
                            }
                            Spacer()
                            Image(systemName: "sparkles")
                                .font(.system(size: 40))
                                .foregroundColor(.white.opacity(0.9))
                        }
                        
                        Divider().background(Color.white.opacity(0.2))
                        
                        HStack {
                            Label("الاستديو: ~\(viewModel.formattedEstimatedStorage)", systemImage: "photo.stack")
                                .font(.caption.bold())
                                .foregroundColor(.white.opacity(0.95))
                            Spacer()
                            Label("سعة الآيفون: \(viewModel.formattedDeviceStorage)", systemImage: "iphone")
                                .font(.caption)
                                .foregroundColor(.white.opacity(0.85))
                        }
                    }
                    .padding(22)
                    .background(
                        LinearGradient(
                            gradient: Gradient(colors: [Color.blue, Color(red: 0.1, green: 0.35, blue: 0.85)]),
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )
                    .cornerRadius(22)
                    .shadow(color: Color.blue.opacity(0.3), radius: 12, x: 0, y: 6)
                    
                    // Library Breakdown Grid
                    VStack(alignment: .leading, spacing: 12) {
                        Text("محتويات الاستديو")
                            .font(.headline)
                            .padding(.horizontal, 4)
                        
                        LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 14) {
                            StatCardView(
                                title: "الصور الثابتة",
                                value: "\(viewModel.totalPhotos)",
                                subtitle: "ضغط HEIC عالي الدقة",
                                icon: "photo.stack",
                                color: .blue
                            )
                            StatCardView(
                                title: "مقاطع الفيديو",
                                value: "\(viewModel.totalVideos)",
                                subtitle: "ترميز عتادي HEVC",
                                icon: "video.fill",
                                color: .purple
                            )
                            StatCardView(
                                title: "صور حية (Live)",
                                value: "\(viewModel.totalLivePhotos)",
                                subtitle: "حفاظ كامل على الحركة",
                                icon: "livephoto",
                                color: .green
                            )
                            StatCardView(
                                title: "الألبومات المنظمة",
                                value: "\(viewModel.photoService.availableAlbums.count)",
                                subtitle: "حفاظ 100% على الألبومات",
                                icon: "rectangle.stack.fill",
                                color: .orange
                            )
                        }
                    }
                    
                    // Quick Action Button
                    Button(action: {
                        if viewModel.hasPermission {
                            selectedTab = 1 // Switch to Optimizer tab
                        } else if viewModel.isPermissionDenied {
                            viewModel.openSettings()
                        } else {
                            viewModel.requestAccess { granted in
                                if granted {
                                    selectedTab = 1
                                }
                            }
                        }
                    }) {
                        HStack(spacing: 10) {
                            Image(systemName: "bolt.fill")
                            Text(viewModel.hasPermission ? "بدء التخفيف الذكي الآن" : (viewModel.isPermissionDenied ? "فتح الإعدادات لمنح الإذن" : "منح إذن الوصول للصور"))
                                .fontWeight(.bold)
                        }
                        .font(.headline)
                        .foregroundColor(.white)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 16)
                        .background(viewModel.isPermissionDenied ? Color.orange : Color.blue)
                        .cornerRadius(16)
                        .shadow(color: (viewModel.isPermissionDenied ? Color.orange : Color.blue).opacity(0.25), radius: 8, x: 0, y: 4)
                    }
                    .padding(.top, 6)
                }
                .padding(20)
            }
            .background(Color(.systemGroupedBackground).ignoresSafeArea())
            .navigationTitle("خفيف الاستديو")
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(action: {
                        viewModel.refreshLibrary()
                    }) {
                        Image(systemName: "arrow.clockwise")
                            .font(.subheadline.bold())
                    }
                }
            }
            .onAppear {
                viewModel.checkAndRequestPermission()
            }
        }
    }
}
