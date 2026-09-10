import SwiftUI
import Photos

public struct OptimizerView: View {
    
    @ObservedObject var viewModel: OptimizerViewModel
    @ObservedObject var settingsViewModel: SettingsViewModel
    @State private var showCancelConfirmation: Bool = false
    
    public init(viewModel: OptimizerViewModel, settingsViewModel: SettingsViewModel) {
        self.viewModel = viewModel
        self.settingsViewModel = settingsViewModel
    }
    
    public var body: some View {
        NavigationView {
            ScrollView {
                VStack(spacing: 24) {
                    
                    // State Banner
                    HStack(spacing: 12) {
                        Circle()
                            .fill(stateColor)
                            .frame(width: 12, height: 12)
                        Text(stateTitle)
                            .font(.headline)
                        Spacer()
                        Text("الهدف: \(viewModel.selectedFilterTitle)")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                    .padding(14)
                    .background(Color(.secondarySystemGroupedBackground))
                    .cornerRadius(14)
                    
                    // Active Thumbnail & File Info
                    VStack(spacing: 12) {
                        if let image = viewModel.batchOptimizer.currentThumbnail {
                            Image(uiImage: image)
                                .resizable()
                                .aspectRatio(contentMode: .fill)
                                .frame(width: 140, height: 140)
                                .clipShape(RoundedRectangle(cornerRadius: 18))
                                .shadow(radius: 6)
                        } else {
                            ZStack {
                                RoundedRectangle(cornerRadius: 18)
                                    .fill(Color(.tertiarySystemGroupedBackground))
                                    .frame(width: 140, height: 140)
                                Image(systemName: "photo.fill")
                                    .font(.system(size: 44))
                                    .foregroundColor(.secondary.opacity(0.6))
                            }
                        }
                        
                        Text(viewModel.batchOptimizer.currentItemTitle.isEmpty ? "بانتظار بدء العملية" : viewModel.batchOptimizer.currentItemTitle)
                            .font(.caption)
                            .foregroundColor(.secondary)
                            .lineLimit(1)
                    }
                    .padding(.vertical, 8)
                    
                    // Live Telemetry Grid
                    HStack(spacing: 14) {
                        StatCardView(
                            title: "المساحة المحررة",
                            value: viewModel.formattedSavedSpace,
                            icon: "arrow.down.circle.fill",
                            color: .green
                        )
                        StatCardView(
                            title: "السرعة",
                            value: String(format: "%.1f ملف/د", viewModel.batchOptimizer.itemsPerMinute),
                            icon: "speedometer",
                            color: .blue
                        )
                    }
                    
                    HStack(spacing: 14) {
                        StatCardView(
                            title: "تم إنجازه",
                            value: "\(viewModel.batchOptimizer.processedCount) / \(viewModel.batchOptimizer.totalCount)",
                            icon: "checkmark.circle.fill",
                            color: .purple
                        )
                        StatCardView(
                            title: "الوقت المتبقي",
                            value: viewModel.formattedRemainingTime,
                            icon: "clock.fill",
                            color: .orange
                        )
                    }
                    
                    // Progress Bar
                    VStack(alignment: .leading, spacing: 8) {
                        HStack {
                            Text("نسبة الإنجاز")
                                .font(.caption.bold())
                                .foregroundColor(.secondary)
                            Spacer()
                            Text("\(Int(viewModel.batchOptimizer.progress * 100))%")
                                .font(.caption.bold())
                                .foregroundColor(.blue)
                        }
                        ProgressView(value: viewModel.batchOptimizer.progress, total: 1.0)
                            .accentColor(.blue)
                            .scaleEffect(x: 1, y: 1.6, anchor: .center)
                    }
                    .padding(16)
                    .background(Color(.secondarySystemGroupedBackground))
                    .cornerRadius(16)
                    
                    // Control Buttons
                    HStack(spacing: 14) {
                        switch viewModel.batchOptimizer.state {
                        case .idle, .completed, .cancelled:
                            Button(action: {
                                viewModel.start(config: settingsViewModel.config)
                            }) {
                                HStack {
                                    Image(systemName: "play.fill")
                                    Text("بدء التحسين والتخفيف")
                                        .bold()
                                }
                                .frame(maxWidth: .infinity)
                                .padding()
                                .background(Color.blue)
                                .foregroundColor(.white)
                                .cornerRadius(14)
                            }
                            
                        case .running:
                            Button(action: { viewModel.pause() }) {
                                HStack {
                                    Image(systemName: "pause.fill")
                                    Text("إيقاف مؤقت")
                                }
                                .frame(maxWidth: .infinity)
                                .padding()
                                .background(Color.orange)
                                .foregroundColor(.white)
                                .cornerRadius(14)
                            }
                            
                            Button(action: { showCancelConfirmation = true }) {
                                HStack {
                                    Image(systemName: "xmark.circle.fill")
                                    Text("إلغاء")
                                }
                                .frame(maxWidth: .infinity)
                                .padding()
                                .background(Color.red)
                                .foregroundColor(.white)
                                .cornerRadius(14)
                            }
                            
                        case .paused:
                            Button(action: { viewModel.resume() }) {
                                HStack {
                                    Image(systemName: "play.fill")
                                    Text("استئناف")
                                }
                                .frame(maxWidth: .infinity)
                                .padding()
                                .background(Color.green)
                                .foregroundColor(.white)
                                .cornerRadius(14)
                            }
                            
                            Button(action: { showCancelConfirmation = true }) {
                                HStack {
                                    Image(systemName: "xmark.circle.fill")
                                    Text("إنهاء")
                                }
                                .frame(maxWidth: .infinity)
                                .padding()
                                .background(Color.red)
                                .foregroundColor(.white)
                                .cornerRadius(14)
                            }
                        }
                    }
                    .padding(.top, 8)
                }
                .padding(20)
            }
            .background(Color(.systemGroupedBackground).ignoresSafeArea())
            .navigationTitle("محرك التخفيف الحي")
            .alert("تأكيد إيقاف المعالجة", isPresented: $showCancelConfirmation) {
                Button("إلغاء العملية", role: .destructive) {
                    viewModel.cancel()
                }
                Button("متابعة", role: .cancel) {}
            } message: {
                Text("لن تتأثر الملفات التي تم ضغطها بالفعل، وسيتم إيقاف معالجة باقي القائمة بأمان.")
            }
            .alert("اكتمل التخفيف بنجاح! 🎉", isPresented: $viewModel.showCompletionAlert) {
                Button("ممتاز", role: .cancel) {}
            } message: {
                if let session = viewModel.lastSession {
                    Text("تم توفير مساحة \(session.formattedSavedSpace) بنجاح عبر ضغط \(session.totalProcessed) عنصراً.")
                } else {
                    Text("تمت معالجة العناصر وحفظ المساحة بنجاح.")
                }
            }
        }
    }
    
    private var stateTitle: String {
        switch viewModel.batchOptimizer.state {
        case .idle: return "جاهز للبدء"
        case .running: return "جاري الضغط والتحقق..."
        case .paused: return "متوقف مؤقتاً"
        case .completed: return "اكتمل بنجاح"
        case .cancelled: return "تم الإلغاء"
        }
    }
    
    private var stateColor: Color {
        switch viewModel.batchOptimizer.state {
        case .idle: return .gray
        case .running: return .green
        case .paused: return .orange
        case .completed: return .blue
        case .cancelled: return .red
        }
    }
}
