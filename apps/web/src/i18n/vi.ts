// Mọi chữ hiển thị cho người dùng nằm ở đây.
// Khu vực /verify (người dân) KHÔNG được chứa điểm số hay chữ "giả mạo" — có test kiểm.

export const vi = {
  app: {
    name: "VeriClue",
  },
  verify: {
    title: "Xác minh danh tính",
    description: "Làm theo hướng dẫn trên màn hình để hoàn tất xác minh.",
  },
  review: {
    title: "Bàn duyệt",
    description: "Danh sách hồ sơ cần nhân viên xem xét.",
  },
  forensic: {
    title: "Giám định",
    description: "Tải lên video hoặc âm thanh cần giám định.",
  },
} as const;

export type ViMessages = typeof vi;
