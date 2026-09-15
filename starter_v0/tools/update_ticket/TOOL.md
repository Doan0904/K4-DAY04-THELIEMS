---
name: update_ticket
track: bonus
kind: action
requires_env: []
inputs: [ticket_id, priority, status, note, confirmed]
outputs: [status, ticket_id, before, after]
side_effect: local_file_write
requires_confirmation: true
---
# update_ticket

Cập nhật mức độ ưu tiên (`priority`), trạng thái (`status`), hoặc thêm ghi chú kỹ thuật (`note`) cho một ticket đã tồn tại.
Nhận vào `ticket_id` (bắt buộc), cùng ít nhất một trường cần cập nhật (`priority`, `status`, hoặc `note`).
Vì đây là hành động ghi (write action), tool **bắt buộc yêu cầu xác nhận rõ ràng** (`confirmed == True`).
Nếu `confirmed` là `false` hoặc thiếu, tool trả về `status: "needs_confirmation"` và không thay đổi dữ liệu.
Chặn các nội dung nhạy cảm (password, tokens, MFA/OTP).
