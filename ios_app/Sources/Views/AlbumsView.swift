import SwiftUI
import Photos

public struct AlbumsView: View {
    
    @ObservedObject var albumsViewModel: AlbumsViewModel
    @ObservedObject var optimizerViewModel: OptimizerViewModel
    @Binding var selectedTab: Int
    
    public init(albumsViewModel: AlbumsViewModel, optimizerViewModel: OptimizerViewModel, selectedTab: Binding<Int>) {
        self.albumsViewModel = albumsViewModel
        self.optimizerViewModel = optimizerViewModel
        self._selectedTab = selectedTab
    }
    
    public var body: some View {
        NavigationView {
            List {
                Section(header: Text("التحكم بالاختيار")) {
                    HStack {
                        Button(action: {
                            albumsViewModel.toggleSelectAll()
                        }) {
                            HStack {
                                Image(systemName: albumsViewModel.isSelectAll ? "checkmark.circle.fill" : "circle")
                                    .foregroundColor(.blue)
                                Text(albumsViewModel.isSelectAll ? "إلغاء تحديد الكل" : "تحديد كافة الألبومات")
                            }
                        }
                        Spacer()
                        Text("\(albumsViewModel.albums.filter { $0.isSelected }.count) ألبوم محدد")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
                
                Section(header: Text("الألبومات المكتشفة (\(albumsViewModel.albums.count))")) {
                    if albumsViewModel.albums.isEmpty {
                        Text("لم يتم العثور على ألبومات مخصصة بعد.")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    } else {
                        ForEach(albumsViewModel.albums) { album in
                            HStack {
                                Button(action: {
                                    albumsViewModel.toggleAlbum(album.id)
                                }) {
                                    HStack(spacing: 14) {
                                        Image(systemName: album.isSelected ? "checkmark.circle.fill" : "circle")
                                            .font(.title3)
                                            .foregroundColor(album.isSelected ? .blue : .gray)
                                        
                                        VStack(alignment: .leading, spacing: 2) {
                                            Text(album.title)
                                                .font(.body.bold())
                                                .foregroundColor(.primary)
                                            Text("\(album.count) عنصر")
                                                .font(.caption)
                                                .foregroundColor(.secondary)
                                        }
                                    }
                                }
                                .buttonStyle(PlainButtonStyle())
                                
                                Spacer()
                                
                                Image(systemName: "folder.fill")
                                    .foregroundColor(.orange.opacity(0.8))
                            }
                            .padding(.vertical, 4)
                        }
                    }
                }
                
                Section {
                    Button(action: {
                        let selectedAssets = albumsViewModel.fetchSelectedAssets()
                        optimizerViewModel.customAssetsToProcess = selectedAssets
                        optimizerViewModel.selectedFilterTitle = "\(albumsViewModel.albums.filter { $0.isSelected }.count) ألبومات محددة (\(selectedAssets.count) ملف)"
                        selectedTab = 1 // Navigate to Optimizer tab
                    }) {
                        HStack {
                            Spacer()
                            Image(systemName: "bolt.badge.checkmark.fill")
                            Text("تخفيف الألبومات المحددة فقط")
                                .bold()
                            Spacer()
                        }
                        .foregroundColor(.white)
                        .padding(.vertical, 6)
                    }
                    .listRowBackground(Color.blue)
                }
            }
            .listStyle(InsetGroupedListStyle())
            .navigationTitle("الألبومات والمجلدات")
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(action: {
                        albumsViewModel.refresh()
                    }) {
                        Image(systemName: "arrow.clockwise")
                    }
                }
            }
        }
    }
}
