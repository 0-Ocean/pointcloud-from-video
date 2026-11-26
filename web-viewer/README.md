# Point Cloud Studio

Trình xem point cloud và mesh PLY trên web, đo khoảng cách Euclid giữa hai điểm với nhãn mét ngay trên đoạn nối. Mô hình mặc định là table_test01 đã chuyển sang mét ở bước 6.

## Chạy trên máy

Tại thư mục gốc Point_cloud_project, bật venv rồi chạy:

```powershell
python -m http.server 8765 --bind 127.0.0.1 --directory web-viewer
```

Mở http://127.0.0.1:8765 trong trình duyệt. Không mở index.html bằng cách nhấp đúp vì các ES module và fetch cần HTTP.

## Đo khoảng cách

1. Chọn **Đo khoảng cách**, hoặc giữ Shift khi nhấp lên mô hình.
2. Chọn điểm A rồi B. Số mét hiển thị ngay tại trung điểm đoạn thẳng.
3. **Bỏ điểm** hoặc Shift + chuột phải để bỏ điểm cuối; **Xóa phép đo** hoặc R để làm lại.
4. Chọn điểm thứ ba để bắt đầu cặp mới. Kéo chuột để xoay, chuột phải để dịch chuyển và cuộn để zoom.
5. Trên điện thoại bật chế độ đo rồi chạm hai điểm; kéo để đổi góc nhìn. Các ngón chạm di chuyển sẽ không tạo phép đo.

Đây là khoảng cách thẳng 3D, không phải đường đi dọc bề mặt. Cloud chọn các điểm gốc; mesh chọn điểm trên tam giác được nhìn thấy. Số chữ số hiển thị không phải cam kết độ chính xác đo lường.

## Đưa lên Vercel từ GitHub

1. Import repository **0-Ocean/pointcloud-from-video** trong Vercel → Add New → Project.
2. Chọn **Root Directory: web-viewer**.
3. Framework Preset: **Other**.
4. Không cần Install Command hoặc Build Command. Output Directory là **.** (dấu chấm), đã đặt trong vercel.json.
5. Deploy. Trang sẽ tải assets/table_test01.ply và đọc model.json. Sau đó các commit mới trên production branch sẽ được Vercel triển khai lại nếu Git integration đã kết nối.

Không cần đưa venv, Python, COLMAP, toàn bộ thư mục data hoặc outputs lên Vercel. File mô hình trong assets là bản sao dành riêng cho web đã được chọn để chia sẻ. Người truy cập có thể tải file mô hình này giống các tài nguyên tĩnh khác.

Chưa đăng nhập/kết nối tài khoản Vercel thì không thể tạo URL deployment chỉ bằng file cấu hình. Hướng dẫn chính thức: https://vercel.com/docs/builds/configure-a-build

## Thay mô hình mặc định

Sau bước 6 của thử nghiệm mới, chạy từ gốc dự án:

```powershell
python src/export_web_model.py
```

Script lấy METRIC từ src/project_config.py, xác nhận header đơn vị mét rồi cập nhật assets/table_test01.ply và model.json. Tên tài nguyên được giữ cố định để không tích lũy các bộ dữ liệu cũ; tên hiển thị đổi theo EXPERIMENT. Commit các file web đã thay đổi và push. Hoặc thay url/name/units trong model.json nếu tự quản lý file khác. Không đổi units thành m để giả lập scale cho cloud chưa hiệu chuẩn.

## Mở tệp cá nhân

Nút **Mở file PLY** đọc tệp cục bộ bằng File API. Tệp đó không được upload lên máy chủ. Header do bước 6 sinh ra tự xác nhận đơn vị mét. Nếu không có thông tin đơn vị, công cụ yêu cầu chọn đơn vị đã biết trong thiết lập rồi mới đo. Tệp lớn hơn 200 MB bị từ chối để tránh mở nhầm dữ liệu quá lớn; khả năng tải thực tế phụ thuộc thiết bị và trình duyệt.

## Cấu trúc

- index.html, styles.css: giao diện tiếng Việt và bố cục điện thoại.
- app.js: Three.js, OrbitControls, PLYLoader, chọn điểm và vẽ nhãn.
- measurement.js: tính khoảng cách, trung điểm và đổi đơn vị đã biết sang mét.
- assets/table_test01.ply: cloud mẫu theo mét, giữ nguyên tọa độ.
- model.json: đường dẫn, tên, đơn vị và thông tin nguồn mô hình mặc định.
- vendor/: Three.js 0.187.0, tải từ gói three chính thức; giấy phép MIT trong THREE-LICENSE.txt. Không cần CDN runtime.
- vercel.json: cấu hình hosting tĩnh.

## Kiểm tra

Đã kiểm tra bằng Microsoft Edge: tải đủ 1.324.572 điểm của table_test01, bố cục desktop/mobile, chọn hai điểm chuẩn 0,89 m, nhãn tại trung điểm, bỏ điểm, bắt đầu cặp mới, mở PLY cục bộ và chặn đo khi chưa biết đơn vị. Các phép tái tạo SfM/MVS vẫn chạy ở dự án Python; trang web chỉ xem và đo dữ liệu đã xuất.