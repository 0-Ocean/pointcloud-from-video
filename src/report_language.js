/* Offline Vietnamese/English controls for the generated diagnostics report. */
(() => {
  'use strict';

  const storageKey = 'pointcloud-report-language';
  const translations = new Map([
    ['Ballroom — SIFT và matching', ['Ballroom — SIFT và ghép điểm', 'Ballroom — SIFT and feature matching']],
    ['Ballroom: điểm SIFT, matching và chất lượng sparse', ['Ballroom: điểm SIFT, ghép điểm và chất lượng mô hình thưa', 'Ballroom: SIFT features, matching and sparse reconstruction quality']],
    ['Dữ liệu đọc trực tiếp từ <code>outputs/database.db</code> và sparse model được chọn. Không chạy lại SIFT, matching hoặc sửa database.', ['Dữ liệu đọc trực tiếp từ <code>outputs/database.db</code> và mô hình thưa được chọn. Không chạy lại SIFT, ghép điểm hoặc sửa cơ sở dữ liệu.', 'Data is read directly from <code>outputs/database.db</code> and the selected sparse model. SIFT extraction and matching are not rerun, and the database is not modified.']],
    ['<strong>Cách đọc:</strong> vòng tròn/hướng biểu diễn keypoint SIFT. Đường nối biểu diễn cặp điểm tương ứng. Xanh = được giữ trong tập kiểm tra hình học; cam = không xuất hiện trong tập đó. Mỗi ảnh matching chỉ vẽ tối đa 100 đường để dễ đọc; mỗi ảnh keypoint vẽ tối đa 500 điểm. Bấm ảnh để mở kích thước đầy đủ.', ['<strong>Cách đọc:</strong> vòng tròn và hướng biểu diễn điểm đặc trưng SIFT. Đường nối biểu diễn cặp điểm tương ứng. Xanh = được giữ trong tập kiểm tra hình học; cam = không xuất hiện trong tập đó. Mỗi ảnh ghép điểm vẽ tối đa 100 đường; mỗi ảnh SIFT vẽ tối đa 500 điểm. Bấm ảnh để mở kích thước đầy đủ.', '<strong>How to read:</strong> circles and orientations represent SIFT keypoints. Lines connect corresponding features. Green = retained in the geometric verification set; orange = absent from that set. Each matching image shows up to 100 lines, and each keypoint image shows up to 500 points. Click an image to open it at full size.']],
    ['Chỉ số đo từ dự án', ['Chỉ số đo từ dự án', 'Measured project metrics']],
    ['Ảnh trong database', ['Ảnh trong cơ sở dữ liệu', 'Images in database']],
    ['Tổng điểm SIFT', ['Tổng điểm SIFT', 'Total SIFT keypoints']],
    ['Bản ghi cặp ảnh', ['Bản ghi cặp ảnh', 'Image-pair records']],
    ['Cặp có inlier', ['Cặp có điểm khớp qua kiểm tra hình học', 'Pairs with geometric inliers']],
    ['Tentative matches', ['Cặp điểm khớp ban đầu', 'Tentative matches']],
    ['Geometric matches', ['Cặp điểm khớp qua kiểm tra hình học', 'Geometrically verified matches']],
    ['Tỷ lệ số lượng được giữ', ['Tỷ lệ số lượng được giữ', 'Match count retention ratio']],
    ['Ảnh đăng ký trong model', ['Ảnh đã đăng ký trong mô hình', 'Registered model images']],
    ['Điểm 3D sparse', ['Điểm 3D thưa', 'Sparse 3D points']],
    ['Mean reprojection error', ['Sai số chiếu lại trung bình', 'Mean reprojection error']],
    ['Median / P95 reprojection error', ['Trung vị / P95 sai số chiếu lại', 'Median / P95 reprojection error']],
    ['Mean track length', ['Độ dài chuỗi quan sát trung bình', 'Mean track length']],
    ['<strong>Không diễn giải tỷ lệ inlier thành “độ chính xác matching”.</strong> Đây là kiểm tra nhất quán theo mô hình hình học. Hoa văn lặp lại vẫn có thể tạo ghép nhầm nhất quán. Sai số chiếu lại đo mức phù hợp giữa điểm 3D và quan sát ảnh trong sparse model; sai số nhỏ không chứng minh kích thước phòng hoặc dense cloud đúng theo centimet. Các điểm bị loại không nằm trong phân bố reprojection error này.', ['<strong>Không diễn giải tỷ lệ điểm qua kiểm tra hình học thành “độ chính xác ghép điểm”.</strong> Đây là kiểm tra tính nhất quán theo mô hình hình học. Hoa văn lặp lại vẫn có thể tạo ghép nhầm nhất quán. Sai số chiếu lại đo mức phù hợp giữa điểm 3D và quan sát ảnh trong mô hình thưa; sai số nhỏ không chứng minh kích thước phòng hoặc đám mây điểm dày đặc đúng theo centimet. Các điểm bị loại không nằm trong phân bố sai số chiếu lại này.', '<strong>Do not interpret the inlier ratio as “matching accuracy”.</strong> It measures consistency with a geometric model. Repeated patterns can still produce geometrically consistent false matches. Reprojection error measures agreement between 3D points and image observations in the sparse model; a small error does not establish centimetre-level accuracy of room dimensions or the dense cloud. Rejected points are excluded from this reprojection error distribution.']],
    ['Ảnh SIFT và matching thật', ['Ảnh SIFT và ghép điểm thực tế', 'Actual SIFT and matching visualizations']],
    ['Các chỉ số của database và sparse model đang đọc.', ['Các chỉ số của cơ sở dữ liệu và mô hình thưa đang đọc. Biểu đồ từ trái sang phải: số điểm SIFT theo ảnh; tỷ lệ điểm khớp qua kiểm tra hình học; phân bố sai số chiếu lại của điểm 3D thưa.', 'Metrics from the database and sparse model being inspected. From left to right: SIFT keypoints by image; geometric match retention; reprojection error distribution of sparse 3D points.']],
    ['Đồ thị matching: trắng = không có bản ghi; màu thể hiện số inlier trên thang log.', ['Đồ thị ghép điểm: hai trục là chỉ số ảnh; trắng = không có bản ghi; màu thể hiện log10(1 + số điểm khớp qua kiểm tra hình học).', 'Match graph: both axes are image indices; white = no stored record; color represents log10(1 + geometric inlier count).']],
    ['Các tham số quan trọng', ['Các tham số quan trọng', 'Key parameters']],
    ['“Mặc định bản cài” là kết quả đọc trợ giúp COLMAP 4.2.1, không phải lịch sử chắc chắn của lần tạo database. “Recipe” là các cờ đang đặt trong mã dự án; sửa cờ không thay đổi dữ liệu đã tính trước đó.', ['“Mặc định bản cài” là kết quả đọc trợ giúp COLMAP 4.2.1, không phải lịch sử chắc chắn của lần tạo cơ sở dữ liệu. “Cấu hình” là các cờ đang đặt trong mã dự án; sửa cờ không thay đổi dữ liệu đã tính trước đó.', '“Installed default” comes from COLMAP 4.2.1 help output; it is not a confirmed record of the settings used to create the database. “Recipe” refers to flags currently set in the project code; changing them does not alter previously computed data.']],
    ['Tham số', ['Tham số', 'Parameter']],
    ['Giá trị', ['Giá trị', 'Value']],
    ['Nguồn', ['Nguồn', 'Source']],
    ['Tác động', ['Tác động', 'Effect']],
    ['Camera model / single_camera', ['Mô hình camera / single_camera', 'Camera model / single_camera']],
    ['Dense max_image_size / source views', ['Mô hình dày đặc: max_image_size / số góc nhìn nguồn', 'Dense max_image_size / source views']],
    ['Recipe hiện tại', ['Cấu hình hiện tại', 'Current recipe']],
    ['Mặc định bản cài', ['Mặc định bản cài', 'Installed default']],
    ['Recipe phục hồi', ['Cấu hình phục hồi', 'Recovery recipe']],
    ['Recipe mesh hiện tại', ['Cấu hình lưới hiện tại', 'Current mesh recipe']],
    ['Chỉ chia sẻ camera khi cùng ống kính, zoom và cấu hình ảnh.', ['Chỉ dùng chung thông số camera khi cùng ống kính, mức thu phóng và cấu hình ảnh.', 'Share camera parameters only when the lens, zoom and image configuration are the same.']],
    ['Giảm kích thước giúp nhanh/nhẹ hơn, có thể mất đặc trưng nhỏ.', ['Giảm kích thước giúp xử lý nhanh và nhẹ hơn, nhưng có thể mất đặc trưng nhỏ.', 'Smaller images reduce processing time and memory use but may lose small features.']],
    ['Mục tiêu số đặc trưng; tăng làm matching và bộ nhớ nặng hơn.', ['Mục tiêu số đặc trưng; tăng giá trị làm ghép điểm và bộ nhớ nặng hơn.', 'Target feature count; increasing it raises matching cost and memory use.']],
    ['Hạ ngưỡng thường tăng điểm yếu và cả nhiễu.', ['Hạ ngưỡng thường tăng số điểm yếu và cả nhiễu.', 'Lowering the threshold usually adds weaker keypoints and more noise.']],
    ['Ratio test loại mô tả mơ hồ; cross-check yêu cầu ghép hai chiều.', ['Kiểm tra tỷ lệ loại mô tả mơ hồ; kiểm tra chéo yêu cầu ghép hai chiều.', 'The ratio test rejects ambiguous descriptors; cross-check requires mutual matches.']],
    ['Phạm vi ghép ảnh theo chuỗi; tăng thêm kết nối và chi phí.', ['Phạm vi ghép ảnh theo chuỗi; tăng giá trị tạo thêm kết nối và chi phí xử lý.', 'Sequential image matching range; increasing it adds connections and processing cost.']],
    ['Ngưỡng kiểm tra hình học 2 ảnh, không phải sai số 3D theo mét.', ['Ngưỡng kiểm tra hình học giữa hai ảnh, không phải sai số 3D theo mét.', 'Two-view geometric verification threshold, not a 3D error measured in metres.']],
    ['Số inlier tối thiểu; đạt ngưỡng chưa chứng minh cặp đúng.', ['Số điểm khớp qua kiểm tra hình học tối thiểu; đạt ngưỡng chưa chứng minh cặp ghép đúng.', 'Minimum geometric inlier count; reaching it does not establish that a pair is correct.']],
    ['Ngưỡng lọc điểm sparse theo sai số chiếu lại.', ['Ngưỡng lọc điểm thưa theo sai số chiếu lại.', 'Threshold for filtering sparse points by reprojection error.']],
    ['Góc tam giác hóa nhỏ khiến ước lượng độ sâu thiếu ổn định.', ['Góc tam giác hóa nhỏ khiến ước lượng độ sâu thiếu ổn định.', 'Small triangulation angles make depth estimates less stable.']],
    ['Các nhóm nội tham được tối ưu trong bundle adjustment.', ['Các nhóm nội tham được tối ưu trong bước bình sai bó (bundle adjustment).', 'Groups of camera intrinsic parameters optimized during bundle adjustment.']],
    ['Cân bằng chi tiết, tốc độ và VRAM.', ['Cân bằng chi tiết, tốc độ và bộ nhớ GPU (VRAM).', 'Balances detail, processing speed and GPU memory (VRAM).']],
    ['Kiểm tra độ sâu giữa nhiều góc nhìn và lọc kết quả.', ['Kiểm tra độ sâu giữa nhiều góc nhìn và lọc kết quả.', 'Checks depth consistency across multiple views and filters the results.']],
    ['Giảm bộ nhớ và số luồng; cache không phải trần tổng RAM.', ['Giảm bộ nhớ và số luồng; bộ nhớ đệm không phải giới hạn tổng RAM.', 'Reduces memory use and thread count; cache size is not a cap on total RAM use.']],
    ['Ảnh hưởng chi tiết và bộ nhớ mesh, không thay đổi SIFT/matching.', ['Ảnh hưởng chi tiết và bộ nhớ lưới, không thay đổi SIFT hoặc ghép điểm.', 'Affects mesh detail and memory use; does not change SIFT extraction or matching.']],
    ['1.5 degrees', ['1.5 độ', '1.5 degrees']],
    ['Xem trực tiếp trong COLMAP GUI', ['Xem trực tiếp trong giao diện COLMAP', 'Inspect directly in the COLMAP GUI']],
    ['Chạy <code>C:\\colmap\\COLMAP.bat gui</code>.', ['Chạy <code>C:\\colmap\\COLMAP.bat gui</code>.', 'Run <code>C:\\colmap\\COLMAP.bat gui</code>.']],
    ['Trong <code>File &gt; New project</code>, trỏ database tới <code>outputs/database.db</code> hiện có và image folder tới <code>data/filtered</code>. Không chạy lại Extract/Match.', ['Trong <code>File &gt; New project</code>, trỏ cơ sở dữ liệu tới <code>outputs/database.db</code> hiện có và thư mục ảnh tới <code>data/filtered</code>. Không chạy lại Extract/Match.', 'Under <code>File &gt; New project</code>, set the database to the existing <code>outputs/database.db</code> and the image folder to <code>data/filtered</code>. Do not rerun Extract/Match.']],
    ['Vào <code>Processing &gt; Manage database</code>; chọn ảnh rồi dùng <code>Show image</code> và <code>Overlapping images</code> để xem điểm và matches. Không sửa dữ liệu hoặc bấm Save nếu chỉ xem.', ['Vào <code>Processing &gt; Manage database</code>; chọn ảnh rồi dùng <code>Show image</code> và <code>Overlapping images</code> để xem điểm và các cặp ghép. Không sửa dữ liệu hoặc bấm Save nếu chỉ xem.', 'Open <code>Processing &gt; Manage database</code>, select an image, then use <code>Show image</code> and <code>Overlapping images</code> to inspect keypoints and matches. Do not edit data or click Save when only inspecting.']],
    ['Nguồn: <a href="https://colmap.github.io/database.html">COLMAP database format</a> · <a href="https://colmap.github.io/tutorial.html#database-management">GUI/database tutorial</a> · <a href="https://colmap.github.io/faq.html">Parameter guidance</a>.', ['Nguồn: <a href="https://colmap.github.io/database.html">Định dạng cơ sở dữ liệu COLMAP</a> · <a href="https://colmap.github.io/tutorial.html#database-management">Hướng dẫn giao diện và cơ sở dữ liệu</a> · <a href="https://colmap.github.io/faq.html">Hướng dẫn tham số</a>.', 'Sources: <a href="https://colmap.github.io/database.html">COLMAP database format</a> · <a href="https://colmap.github.io/tutorial.html#database-management">GUI/database tutorial</a> · <a href="https://colmap.github.io/faq.html">Parameter guidance</a>.']],
    ['Tệp kèm: <a href="summary.json">summary.json</a> · <a href="pairs.csv">pairs.csv</a>. Báo cáo là chẩn đoán nội tại, chưa có ground-truth correspondence hoặc đánh giá metric 3D.', ['Tệp kèm: <a href="summary.json">summary.json</a> · <a href="pairs.csv">pairs.csv</a>. Báo cáo là chẩn đoán nội tại, chưa có đối sánh chuẩn thực tế hoặc đánh giá độ chính xác kích thước 3D.', 'Files: <a href="summary.json">summary.json</a> · <a href="pairs.csv">pairs.csv</a>. This report provides internal diagnostics; no ground-truth correspondences or metric 3D accuracy evaluation are available.']]
  ]);

  function translate(source) {
    if (translations.has(source)) return translations.get(source);
    let match = source.match(/^([\d.]+) ảnh\/điểm$/);
    if (match) return [source, `${match[1]} images/point`];
    match = source.match(/^SIFT: (.+) — ([\d,]+) keypoints, hiển thị tối đa 500 vòng tròn\/hướng\.$/);
    if (match) return [
      `SIFT: ${match[1]} — ${match[2]} điểm đặc trưng, hiển thị tối đa 500 vòng tròn và hướng.`,
      `SIFT: ${match[1]} — ${match[2]} keypoints; up to 500 circles and orientations shown.`
    ];
    match = source.match(/^(strong|medium|weak|rejected|custom\d+): (.+) — (\d+) tentative, (\d+) inliers \(([\d.]+%)\)\.$/);
    if (match) {
      const category = {
        strong: ['Nhiều điểm khớp', 'High inlier count'],
        medium: ['Mức giữ lại trung bình', 'Median retention example'],
        weak: ['Mức giữ lại thấp', 'Low retention example'],
        rejected: ['Không có điểm qua kiểm tra', 'No geometric inliers']
      }[match[1]] || [`Cặp tùy chọn ${match[1].slice(6)}`, `Custom pair ${match[1].slice(6)}`];
      return [
        `${category[0]}: ${match[2]} — ${match[3]} cặp điểm khớp ban đầu, ${match[4]} cặp qua kiểm tra hình học (${match[5]}).`,
        `${category[1]}: ${match[2]} — ${match[3]} tentative matches, ${match[4]} geometric inliers (${match[5]}).`
      ];
    }
    return null;
  }

  // Retain the source once so repeated switching never translates a translation.
  const entries = Array.from(document.querySelectorAll('title, h1, h2, p, .note, td, th, figcaption, li'))
    .map(element => ({element, text: translate(element.innerHTML.trim())}))
    .filter(entry => entry.text);

  const style = document.createElement('style');
  style.textContent = `
    .report-languages{display:flex;align-items:center;justify-content:flex-end;gap:.5rem;flex-wrap:wrap;margin-bottom:1.5rem}
    .report-languages span{font-size:.875rem;margin-right:.25rem}
    .report-languages button{font:inherit;min-height:44px;padding:.4rem .9rem;border:1px solid #075e94;border-radius:6px;background:white;color:#075e94;cursor:pointer}
    .report-languages button[aria-pressed="true"]{background:#075e94;color:white}
    .report-languages button:focus-visible,.table-scroll:focus-visible{outline:3px solid #bc7c19;outline-offset:3px}
    .table-scroll{overflow-x:auto;margin:24px 0}
    .table-scroll table{margin:0}
    .table-scroll thead+tbody td:first-child{overflow-wrap:anywhere}
    @media(max-width:600px){main{padding:20px 16px}.report-languages{justify-content:flex-start}.table-scroll:has(thead) table{min-width:650px}figure{padding:10px}h1{font-size:1.7rem}}
  `;
  document.head.append(style);

  const controls = document.createElement('nav');
  controls.className = 'report-languages';
  const label = document.createElement('span');
  label.textContent = 'Ngôn ngữ / Language';
  controls.append(label);
  const buttons = ['vi', 'en'].map(language => {
    const button = document.createElement('button');
    button.type = 'button';
    button.lang = language;
    button.textContent = language === 'vi' ? 'Tiếng Việt' : 'English';
    button.addEventListener('click', () => setLanguage(language));
    controls.append(button);
    return button;
  });
  document.querySelector('main').prepend(controls);

  const tables = Array.from(document.querySelectorAll('main table')).map(table => {
    const wrapper = document.createElement('div');
    wrapper.className = 'table-scroll';
    wrapper.tabIndex = 0;
    wrapper.setAttribute('role', 'region');
    table.before(wrapper);
    wrapper.append(table);
    return {wrapper, parameters: Boolean(table.tHead)};
  });

  function setLanguage(language) {
    const index = language === 'en' ? 1 : 0;
    document.documentElement.lang = language;
    entries.forEach(({element, text}) => { element.innerHTML = text[index]; });
    buttons.forEach(button => button.setAttribute('aria-pressed', String(button.lang === language)));
    controls.setAttribute('aria-label', index ? 'Report language' : 'Ngôn ngữ báo cáo');
    tables.forEach(({wrapper, parameters}) => wrapper.setAttribute('aria-label', index
      ? (parameters ? 'Key parameters' : 'Measured project metrics')
      : (parameters ? 'Các tham số quan trọng' : 'Chỉ số đo từ dự án')));
    document.querySelectorAll('figure').forEach(figure => {
      const caption = figure.querySelector('figcaption').textContent;
      const image = figure.querySelector('img');
      const link = figure.querySelector('a');
      if (image) image.alt = caption;
      if (link) {
        link.setAttribute('aria-label', `${caption} ${index ? 'Open full-size image in a new tab.' : 'Mở ảnh đầy đủ trong thẻ mới.'}`);
        link.rel = 'noopener';
      }
    });
    try { localStorage.setItem(storageKey, language); } catch (_) { /* Storage may be blocked for local files. */ }
  }

  let initialLanguage = 'vi';
  try {
    if (localStorage.getItem(storageKey) === 'en') initialLanguage = 'en';
  } catch (_) { /* Vietnamese remains the offline default. */ }
  setLanguage(initialLanguage);
})();
