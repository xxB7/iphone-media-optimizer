import SwiftUI

public struct AuditHistoryView: View {
    
    @ObservedObject var auditStore: AuditLogStore
    @Environment(\.presentationMode) var presentationMode
    
    public init(auditStore: AuditLogStore) {
        self.auditStore = auditStore
    }
    
    public var body: some View {
        NavigationView {
            Group {
                if auditStore.sessions.isEmpty {
                    VStack(spacing: 16) {
                        Image(systemName: "tray")
                            .font(.system(size: 56))
                            .foregroundColor(.secondary)
                        Text("لا يوجد سجلات سابقة بعد")
                            .font(.headline)
                        Text("ستظهر هنا تفاصيل كل جلسة تخفيف ومقدار المساحة التي تم توفيرها في كل مرة.")
                            .font(.caption)
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.center)
                            .padding(.horizontal, 40)
                    }
                } else {
                    List {
                        ForEach(auditStore.sessions) { session in
                            VStack(alignment: .leading, spacing: 8) {
                                HStack {
                                    Text(formattedDate(session.date))
                                        .font(.caption)
                                        .foregroundColor(.secondary)
                                    Spacer()
                                    Text("+\(session.formattedSavedSpace)")
                                        .font(.headline.bold())
                                        .foregroundColor(.green)
                                }
                                
                                HStack(spacing: 16) {
                                    Label("\(session.totalProcessed) تم معالجته", systemImage: "checkmark.circle")
                                    if session.livePhotosOptimized > 0 {
                                        Label("\(session.livePhotosOptimized) صور حية", systemImage: "livephoto")
                                    }
                                    if session.videosOptimized > 0 {
                                        Label("\(session.videosOptimized) فيديو", systemImage: "video")
                                    }
                                }
                                .font(.caption2)
                                .foregroundColor(.secondary)
                            }
                            .padding(.vertical, 4)
                        }
                    }
                    .listStyle(InsetGroupedListStyle())
                }
            }
            .navigationTitle("سجل الجلسات السابقة")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("إغلاق") {
                        presentationMode.wrappedValue.dismiss()
                    }
                }
            }
        }
    }
    
    private func formattedDate(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.dateStyle = .medium
        formatter.timeStyle = .short
        return formatter.string(from: date)
    }
}
