# Thông tin thành viên nhóm — THELIEMS

- **Tên nhóm:** THELIEMS
- **Khóa:** K4
- **Repository nộp bài:** https://github.com/Doan0904/K4-DAY04-THELIEMS

## Danh sách thành viên

| STT | Họ và tên | MSSV | GitHub Username | Email | Vai trò chính trong dự án |
|:---:|---|:---:|---|---|---|
| 1 | **Đặng Đỉnh Đoàn** | 2A202602927 | [@Doan0904](https://github.com/Doan0904) | dangnhatdoan@gmail.com | **Nhóm trưởng — Agent & Prompt Lead**<br>Chủ trì tối ưu `system_prompt.md`, `tools.yaml`, điều phối các vòng lặp v0–v6, rà soát routing accuracy và ranh giới xác nhận. |
| 2 | **Ngô Anh Khoa** | 2A202602965 | [@drpie143](https://github.com/drpie143) | khoaanhngo113@gmail.com | **Tool & Backend Lead**<br>Chủ trì kiểm thử toàn diện các tool nội bộ, xây dựng bộ smoke test tự động `scripts/test_all_tools.py`, script phân tích lỗi `scripts/analyze_failures.py`, tối ưu provider adapters với cơ chế xoay vòng key (round-robin) và auto-retry 429/503. |
| 3 | **Mai Quang Dũng** | 2A202602966 | [@QuangDung](https://github.com/QuangDung) | maidung2005bk18@gmail.com | **Bonus Tool, Eval & UI Lead**<br>Chủ trì triển khai 2 bonus tools (`lookup_ticket_status`, `update_ticket`), thiết kế 10 test case team eval `eval_group.json`, xây dựng giao diện Streamlit Chat UI (`app.py`). |

## Phân công trách nhiệm và đóng góp kỹ thuật

- **Đặng Đỉnh Đoàn:** Thiết kế các vòng lặp v0 ➔ v6, giải quyết các failure traces, tối ưu prompt chống rò rỉ dữ liệu và hoàn thiện các phần mô tả Báo cáo (REPORT.md).
- **Ngô Anh Khoa:** Khảo sát toàn bộ interface trong `tools/`, kiểm tra ranh giới bảo mật và trust boundary, phát triển test suite tự động kiểm tra contract cho 9 tools, xử lý vấn đề rate limit/quota của model provider với backoff retry, rà soát tính hợp lệ của các run evidence.
- **Mai Quang Dũng:** Hiện thực hóa logic của 2 bonus tools, tạo fixture dữ liệu `helpdesk_data/tickets.json`, xây dựng các test cases nhóm bao phủ đơn và đa lượt, xây dựng giao diện Streamlit UI audit tool calls trực quan.
