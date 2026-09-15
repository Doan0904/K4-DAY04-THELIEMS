---
name: lookup_ticket_status
track: bonus
kind: local_status
provider: mock_ticket_store
requires_env: []
inputs: [ticket_id]
outputs: [ticket_id, status, priority, summary, assigned_to, created_at, updated_at, technical_notes]
side_effect: false
---
# lookup_ticket_status

Tra cứu tiến độ xử lý, trạng thái, mức độ ưu tiên và ghi chú kỹ thuật của một ticket hoặc incident theo `ticket_id`.
Nhận vào `ticket_id` (ví dụ: `INC-1042` hoặc `LAB-XXXXXXXX`).
Trả về `status`, `priority`, `assigned_to`, `created_at`, `updated_at`, và `technical_notes`.
Đây là thao tác đọc (read-only), không có side effect và không cần xác nhận.
Đọc `tickets/<ticket_id>.json` (ticket tạo/cập nhật cục bộ) trước, sau đó mới đến fixture chỉ-đọc `helpdesk_data/tickets.json`.
