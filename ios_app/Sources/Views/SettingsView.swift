import SwiftUI

public struct SettingsView: View {
    
    @ObservedObject var settingsViewModel: SettingsViewModel
    @ObservedObject var auditStore: AuditLogStore
    @State private var showResetAlert: Bool = false
    @State private var showHistorySheet: Bool = false
    
    public init(settingsViewModel: SettingsViewModel, auditStore: AuditLogStore) {
        self.settingsViewModel = settingsViewModel
        self.auditStore = auditStore
    }
    
    public var body: some View {
        NavigationView {
            Form {
                
                // Image Quality Section
                Section(header: Text("جودة ضغط الصور"), footer: Text("القيمة الموصى بها هي 75%. تعطي توفيراً يصل إلى 70% مع بقاء الصورة فائقة الوضوح وبدون أي تشويش ملحوظ للعين البشرية.")) {
                    VStack(alignment: .leading, spacing: 8) {
                        HStack {
                            Text("دقة وجودة الصورة:")
                            Spacer()
                            Text("\(Int(settingsViewModel.config.imageQuality * 100))%")
                                .font(.headline.bold())
                                .foregroundColor(.blue)
                        }
                        Slider(value: $settingsViewModel.config.imageQuality, in: 0.60...0.95, step: 0.05)
                            .accentColor(.blue)
                    }
                    .padding(.vertical, 4)
                }
                
                // Video Compression Preset
                Section(header: Text("ترميز ودقة الفيديو"), footer: Text("يعتمد التطبيق على شريحة Apple Bionic لمعالجة وتشفير الفيديو بتقنية HEVC H.265 العتادية لتوفير أقصى مساحة ممكنة مع الاحتفاظ بالصوت الأصلي وبيانات الـ GPS.")) {
                    Picker("دقة الفيديو", selection: $settingsViewModel.config.videoPreset) {
                        ForEach(CompressionConfig.VideoPreset.allCases) { preset in
                            Text(preset.rawValue).tag(preset)
                        }
                    }
                }
                
                // Safety & Guardrails
                Section(header: Text("إجراءات الأمان والنسخ الأصلية")) {
                    Picker("نمط التعامل مع النسخ الأصلية", selection: $settingsViewModel.config.safetyMode) {
                        ForEach(CompressionConfig.SafetyMode.allCases) { mode in
                            Text(mode.rawValue).tag(mode)
                        }
                    }
                    
                    Toggle("الحفاظ على الصور الحية (Live Photos)", isOn: $settingsViewModel.config.preserveLivePhotos)
                    
                    Toggle("حماية حرارة الجهاز والبطارية (Thermal Guard)", isOn: $settingsViewModel.config.enableThermalGuard)
                }
                
                // Audit History & Space Tracking
                Section(header: Text("سجل التوفير والإحصائيات")) {
                    HStack {
                        Text("إجمالي المساحة الموفرة مدى الحياة:")
                        Spacer()
                        Text(auditStore.formattedLifetimeSavedSpace)
                            .font(.headline.bold())
                            .foregroundColor(.green)
                    }
                    
                    Button(action: {
                        showHistorySheet = true
                    }) {
                        Label("عرض تفاصيل الجلسات السابقة", systemImage: "clock.arrow.circlepath")
                    }
                    
                    Button(action: {
                        showResetAlert = true
                    }) {
                        Text("مسح سجل التوفير وتصفير العداد")
                            .foregroundColor(.red)
                    }
                }
                
                // Technical Engineering Info
                Section(header: Text("المعايير الهندسية والتطبيق")) {
                    HStack {
                        Text("الإصدار البرمجي")
                        Spacer()
                        Text("1.0.0 (Production)")
                            .foregroundColor(.secondary)
                    }
                    HStack {
                        Text("المحرك العتادي")
                        Spacer()
                        Text("Apple ImageIO + VideoToolbox")
                            .foregroundColor(.secondary)
                    }
                    HStack {
                        Text("الأمان والخصوصية")
                        Spacer()
                        Text("100% On-Device (بدون إنترنت)")
                            .foregroundColor(.secondary)
                    }
                }
            }
            .navigationTitle("الإعدادات الهندسية")
            .alert("تأكيد مسح السجل", isPresented: $showResetAlert) {
                Button("مسح السجل", role: .destructive) {
                    auditStore.clearHistory()
                }
                Button("إلغاء", role: .cancel) {}
            } message: {
                Text("هل تريد مسح سجل الجلسات السابقة؟ لن يؤثر هذا على مكتبة الصور.")
            }
            .sheet(isPresented: $showHistorySheet) {
                AuditHistoryView(auditStore: auditStore)
            }
        }
    }
}
