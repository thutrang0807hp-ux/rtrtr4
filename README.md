# SimpleFlow Desktop

Ứng dụng cửa sổ Windows: chọn ảnh/video, nhập prompt và hỗ trợ tạo video trên Google Flow.

## Phạm vi thực tế

Video đầu vào được lấy một khung hình tại giây đã chọn làm ảnh tham chiếu. Không tải toàn bộ video lên Flow, không sao chép chuyển động video.

Ứng dụng mở Edge/Chrome, tải ảnh và điền prompt khi nhận diện được giao diện. Bạn đăng nhập Google, mở dự án, kiểm tra ảnh và xác nhận chi phí bằng nút Tiếp tục. Nếu giao diện Flow thay đổi, ứng dụng hướng dẫn tải ảnh/dán prompt/bấm tạo thủ công. Chưa tự phát hiện video tạo xong; bạn bấm tải trên Flow và ứng dụng lưu tệp vào thư mục kết quả.

Cần Internet, Edge hoặc Chrome và tài khoản có quyền dùng Flow. Google có thể từ chối đăng nhập từ trình duyệt tự động. Chưa xác minh tạo video thật trên Google Flow.

## Build EXE trên Windows

Gói này là mã nguồn, chưa chứa EXE Windows đã build. Môi trường phát triển hiện tại là Linux.

- GitHub: đưa mã nguồn lên repository cùng workflow; vào Actions → Build Windows EXE → Run workflow. Khi thành công, tải artifact SimpleFlow-Windows để lấy SimpleFlow.exe.
- Hoặc trên Windows có Python 3.12 x64 kèm Python Launcher, nhấp đúp build_windows.bat. Kết quả: dist/SimpleFlow.exe.

Build giữ Playwright và OpenCV trong EXE, dùng cửa sổ GUI thay cho terminal. Máy chạy EXE không cần Python hoặc cài pip. Workflow kiểm tra khởi tạo GUI và import các dependency từ EXE; không kiểm tra đăng nhập Google.

## Sử dụng

1. Mở SimpleFlow.exe, chọn ảnh/video, nhập prompt. Với video, chọn giây lấy khung hình.
2. Chọn Edge hoặc Chrome, thư mục kết quả và bấm Mở Flow và bắt đầu.
3. Làm theo hướng dẫn hiển thị; bấm Tiếp tục khi hoàn thành mỗi bước trên Flow.
4. Chờ video, bấm tải trên trình duyệt. Kiểm tra thư mục kết quả trước khi kết thúc.

Ảnh lấy từ video lưu trong thư mục references của thư mục kết quả. Hồ sơ Google lưu ở %LOCALAPPDATA%/SimpleFlow/browser-profile. Không chia sẻ thư mục này; chỉ chạy một phiên cùng lúc.

Bản dòng lệnh cũ simple_flow.py không phải giao diện mới. Entry point mới là desktop_app.py.
