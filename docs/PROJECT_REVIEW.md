# Review lại toàn bộ project

Ghi chú cá nhân, viết để hiểu lại project trước khi demo — không phải file nộp bài chính thức (bài nộp chính là `reports/lab_report.md`).

---

## 1. Tóm lại: project này bắt mình làm gì

Đây là bài **Lab Day 08 — LangGraph Agentic Orchestration**. Đề bài cho sẵn một bộ khung code rỗng (starter skeleton), nhiệm vụ là lắp một con **agent xử lý ticket hỗ trợ khách hàng**, dùng thư viện LangGraph để điều phối các bước xử lý theo kiểu sơ đồ trạng thái (state graph) chứ không phải if/else tuyến tính.

Cụ thể phải làm:
1. Định nghĩa state (dữ liệu agent mang theo suốt quá trình xử lý).
2. Viết 10 "node" — mỗi node là một bước xử lý (phân loại câu hỏi, gọi tool, đánh giá kết quả, trả lời, xin duyệt...).
3. Viết logic routing — quyết định sau mỗi bước thì đi đâu tiếp.
4. Ráp tất cả thành một graph hoàn chỉnh, chạy được từ đầu đến cuối.
5. Thêm khả năng lưu trạng thái (persistence) để có thể phục hồi khi crash.
6. Chạy thử trên bộ câu hỏi mẫu, đo kết quả (metrics), viết báo cáo.

Điểm quan trọng nhất đề bài nhấn đi nhấn lại: **không được hard-code theo từng câu hỏi mẫu**. `classify_node` (bước phân loại câu hỏi) phải dùng LLM thật để suy luận, vì bài chấm sẽ thử thêm câu hỏi mà mình chưa từng thấy — nếu hard-code theo câu mẫu thì gặp câu lạ là toang ngay.

---

## 2. Project gồm những phần nào, mỗi phần làm gì

### Code chính — `src/langgraph_agent_lab/`

| File | Vai trò | Nói dễ hiểu |
|---|---|---|
| `state.py` | Định nghĩa "hành lý" mà agent mang theo qua từng bước | Giống như một cái túi chứa: câu hỏi gốc, đã phân loại route gì, tool trả về gì, đã thử lại mấy lần, câu trả lời cuối... |
| `nodes.py` | 10 bước xử lý cụ thể | Mỗi hàm là một "trạm dừng": phân loại câu hỏi, gọi tool giả lập, đánh giá kết quả tool, viết câu trả lời, hỏi lại khi thiếu thông tin, chuẩn bị hành động nhạy cảm, xin duyệt, ghi nhận thử lại, báo thua cuộc, chốt hạ |
| `routing.py` | Quyết định "xong bước này thì đi đâu" | 4 hàm nhỏ, mỗi hàm đọc state rồi trả về tên bước tiếp theo |
| `graph.py` | Ráp tất cả node + routing thành một sơ đồ hoàn chỉnh | Đây là bản thiết kế mạch điện — nối dây từ node này sang node kia |
| `llm.py` | Kết nối tới LLM (OpenAI/Anthropic/Gemini) | Đọc API key trong `.env`, trả về client LLM để các node dùng |
| `persistence.py` | Lưu trạng thái agent | Mặc định lưu tạm trong RAM (mất khi tắt chương trình), có thể chuyển sang lưu vào file SQLite để sống sót qua restart |
| `metrics.py` | Đo kết quả sau khi chạy | Đếm xem route đúng không, thử lại mấy lần, có xin duyệt không, mất bao lâu... |
| `report.py` | Viết báo cáo tự động từ metrics | Biến số liệu thô thành file `.md` có bảng, có phân tích |
| `scenarios.py` | Đọc bộ câu hỏi test từ file | Đọc `data/sample/scenarios.jsonl`, kiểm tra hợp lệ |
| `cli.py` | Cửa vào chạy chương trình | Chạy lệnh `run-scenarios` (chạy hết bộ câu hỏi) hoặc `validate-metrics` (kiểm tra file kết quả có đúng định dạng không) |

### Dữ liệu & cấu hình

| File/thư mục | Vai trò |
|---|---|
| `data/sample/scenarios.jsonl` | Bộ câu hỏi mẫu để test (mỗi dòng 1 câu hỏi + route đúng của nó) |
| `configs/lab.yaml` | Cấu hình cho lần chạy thường (dùng bộ câu hỏi mẫu, lưu RAM) |
| `configs/grading.yaml` | Cấu hình dành cho giảng viên chấm bài (trỏ tới bộ câu hỏi ẩn — mình không có, không được đụng vào) |
| `.env` | Chứa API key thật, **không commit lên Git** |

### Kiểm thử & kết quả

| File/thư mục | Vai trò |
|---|---|
| `tests/` | Bộ test tự động — 4 file có sẵn từ đề (`test_graph_smoke`, `test_metrics`, `test_routing`, `test_state`) + 1 file mình thêm (`test_persistence`) |
| `outputs/metrics.json` | Kết quả chạy thật (route đúng/sai, retry, thời gian...) |
| `reports/lab_report.md` | Báo cáo cuối — **đây mới là file nộp**, tự sinh ra từ `report.py` |

### Tài liệu

| File | Vai trò |
|---|---|
| `docs/LAB_GUIDE.md` | Hướng dẫn làm bài từ giảng viên |
| `docs/METRICS.md`, `docs/RUBRIC.md` | Giải thích cách chấm điểm |
| `docs/PROJECT_REVIEW.md` | File này — ghi chú cá nhân |

---

## 3. Mình (AI) đã sửa những gì, sửa để làm gì

### A. Làm hết 25 chỗ `TODO(student)` — phần việc chính của bài

Lúc mở project ra, 6 file (`state.py`, `nodes.py`, `routing.py`, `graph.py`, `persistence.py`, `report.py`) toàn là hàm rỗng ném lỗi `NotImplementedError`. Đã viết đầy đủ:

- **`state.py`**: thêm 4 field còn thiếu (`evaluation_result`, `pending_question`, `proposed_action`, `approval`) — đây là những field các node cần đọc/ghi mà đề bài cố tình để trống, bắt mình tự phát hiện ra khi code node.
- **`nodes.py`**: viết cả 10 hàm. Hai hàm quan trọng nhất — `classify_node` (phân loại câu hỏi) và `answer_node` (viết câu trả lời) — gọi LLM thật, có structured output (bắt LLM trả về đúng định dạng thay vì text tự do).
- **`routing.py`**: viết 4 hàm quyết định đường đi, đơn giản là các phép so sánh + dict mapping.
- **`graph.py`**: ráp toàn bộ 11 node (10 node + node `intake` có sẵn) thành sơ đồ, nối đúng theo mô tả trong `LAB_GUIDE.md`.
- **`persistence.py`**: thêm phần lưu bằng SQLite (đây là phần "bonus" — đề chỉ bắt buộc có lưu RAM).
- **`report.py`**: viết logic sinh báo cáo `.md` từ số liệu.

**Vì sao làm vậy**: đây đơn giản là yêu cầu cốt lõi của bài — không làm thì code không chạy được.

### B. Phát hiện và vá lỗi `.env` không tự nạp

Sau khi code xong, chạy test thì 6 test cần gọi LLM bị **skip** hết dù `.env` đã có key. Lý do: không có chỗ nào trong code gọi `load_dotenv()` để đọc file `.env` — biến môi trường không tự nhảy vào chương trình.

**Đã sửa**: thêm `python-dotenv` vào `pyproject.toml`, gọi `load_dotenv()` trong `llm.py`, và thêm file `conftest.py` ở gốc project để pytest cũng nạp `.env` **trước khi** kiểm tra điều kiện skip (vì test kiểm tra biến môi trường ngay lúc import, sớm hơn cả lúc `llm.py` được gọi tới).

**Vì sao quan trọng**: không vá thì cả 6 test dùng LLM thật sẽ luôn bị skip — nhìn tưởng "test pass" nhưng thực ra là "test không chạy", dễ đánh lừa người đọc log.

### C. Thêm 3 phần bonus (đẩy điểm hướng 90+)

1. **SQLite persistence** — chứng minh bằng file test riêng `tests/test_persistence.py`: chạy graph qua SQLite, sau đó mở một checkpointer MỚI trỏ vào cùng file để giả lập "khởi động lại sau khi crash", đọc lại được state cũ.
2. **Sơ đồ graph tự động** — `report.py` tự gọi `graph.get_graph().draw_mermaid()` để nhúng sơ đồ Mermaid thật vào báo cáo, không phải hình vẽ tay (nên nếu sau này sửa graph thì sơ đồ tự cập nhật theo).
3. **2 câu hỏi test tự soạn** thêm vào `scenarios.jsonl` — đề bài cho phép và khuyến khích việc này để chứng minh code tổng quát hoá được, không chỉ ăn may trên 7 câu mẫu.

### D. Sửa 1 quyết định kỹ thuật quan trọng — LLM-as-judge

Ban đầu định để LLM tự chấm luôn xem kết quả tool có "đủ tốt" không, và dùng chính kết quả đó để quyết định có retry hay không (đúng như đề bài gợi ý "bonus"). Nhưng khi test thật thì phát hiện: dù đã set `temperature=0`, OpenAI vẫn không hoàn toàn ổn định — có lần retry oan một scenario lẽ ra phải qua ngay trong 1 lần.

**Đã sửa lại**: heuristic (kiểm tra chuỗi có chữ "ERROR" không) mới là thứ **quyết định retry** — đảm bảo graph luôn dừng đúng lúc, không phụ thuộc may rủi. Còn LLM-as-judge vẫn chạy thật, nhưng chỉ ghi ý kiến vào log (`llm_judge_opinion`) để làm bằng chứng "có dùng LLM" mà không đánh đổi độ tin cậy.

**Vì sao quan trọng**: đây là kiểu quyết định một kỹ sư thật sự phải cân nhắc — không phải cứ "dùng AI cho mọi thứ" là tốt, nhất là khi thứ đang bị AI chấm là dữ liệu giả lập (mock), không có nội dung thật để đánh giá.

### E. Làm số liệu trong report trung thực hơn

Có một tài liệu chi tiết hơn (do người coach/giảng viên cung cấp) chỉ ra vài chỗ dễ bị hiểu nhầm trong scaffold:
- `latency_ms` mặc định luôn là 0 vì không ai đo thời gian thật.
- `resume_success` luôn `False` bất kể có dùng SQLite hay không.
- `interrupt_count` chỉ đếm số lần ghé qua node `approval`, không chứng minh có pause thật (vì approval đang chạy ở chế độ mock, luôn tự động duyệt).

**Đã sửa**:
- Đo `time.perf_counter()` thật quanh mỗi lần chạy graph trong `cli.py` → `latency_ms` giờ là số thật.
- Thêm hẳn mục "Metric caveats" trong report để giải thích rõ ý nghĩa thật của từng con số, tránh report "nổ" hơn thực tế.
- Viết lại phần "Failure analysis" theo đúng 5 yếu tố: lỗi bắt đầu từ đâu → dấu hiệu phát hiện → graph đi đường nào → vì sao chắc chắn dừng được → rủi ro còn sót lại.

**Vì sao quan trọng**: một báo cáo nói đúng-đủ, không phóng đại, tự nó đã là một phần điểm ("Report & demo"). Nói "có persistence" mà không có bằng chứng cụ thể thì cũng như không nói.

### F. Dọn code sạch (lint/type) — chỉ ở phần mình viết

Chạy `ruff` và `mypy` để đối chiếu, sửa các lỗi thật ở code mình viết (dòng quá dài, thiếu type hint, dùng `Any` khi có thể dùng type cụ thể hơn). **Không đụng vào các file test có sẵn từ đề** (`test_graph_smoke.py`, `test_metrics.py`, `test_routing.py`, `test_state.py`) dù chúng cũng dính vài lỗi style — vì đó là bài giảng viên viết sẵn, sửa vào có thể bị hiểu lầm là "chỉnh bài chấm để che gap".

---

## 3b. Luồng chạy tổng thể — file nào lo phần nào

Có 2 tầng luồng khác nhau, dễ nhầm nếu không tách ra:

- **Luồng ngoài**: từ lúc gõ lệnh `run-scenarios` tới lúc có file kết quả.
- **Luồng trong**: bên trong MỖI câu hỏi, agent đi qua những bước nào (đây là cái sơ đồ Mermaid đã nhúng trong `reports/lab_report.md`).

### Luồng ngoài — chạy `run-scenarios`

```
1. cli.py đọc configs/lab.yaml
      ↓
2. scenarios.py đọc data/sample/scenarios.jsonl → ra danh sách câu hỏi (Scenario)
      ↓
3. persistence.py dựng checkpointer (memory hoặc sqlite tuỳ config)
      ↓
4. graph.py ráp toàn bộ node (nodes.py) + routing (routing.py) thành 1 graph, compile cùng checkpointer
      ↓
5. Với TỪNG câu hỏi:
     state.py::initial_state() tạo state khởi đầu
        ↓
     graph.invoke(state) → chạy hết "luồng trong" (xem mục dưới), llm.py được gọi
     bên trong mỗi lần node cần LLM (classify_node, answer_node, evaluate_node)
        ↓
     metrics.py::metric_from_state() đọc state cuối cùng → tính ra 1 ScenarioMetric
      ↓
6. metrics.py::summarize_metrics() gộp tất cả ScenarioMetric → MetricsReport
      ↓
7. Ghi ra outputs/metrics.json (metrics.py::write_metrics)
      ↓
8. report.py::render_report() đọc MetricsReport → sinh reports/lab_report.md
```

File nào lo bước nào, tóm tắt 1 dòng:

| Bước | File |
|---|---|
| Đọc config | `cli.py` |
| Đọc bộ câu hỏi | `scenarios.py` |
| Dựng nơi lưu trạng thái | `persistence.py` |
| Dựng agent (graph) | `graph.py` (dùng `nodes.py` + `routing.py`) |
| Tạo state khởi đầu cho 1 câu hỏi | `state.py` |
| Chạy agent qua 1 câu hỏi | `graph.py` đã compile, gọi `nodes.py` từng bước, `nodes.py` gọi `llm.py` khi cần LLM |
| Tính điểm cho 1 câu hỏi | `metrics.py` |
| Gộp điểm toàn bộ | `metrics.py` |
| Ghi file kết quả thô | `metrics.py` |
| Viết báo cáo | `report.py` |

### Luồng trong — 1 câu hỏi đi qua agent như thế nào

Đây là phần `graph.py` ráp, chạy trong `nodes.py`, quyết định đường đi bởi `routing.py`:

```
intake (chuẩn hoá câu hỏi)
   ↓
classify (LLM phân loại: simple / tool / missing_info / risky / error)
   ↓ (routing.py::route_after_classify quyết định rẽ nhánh)
   ├─ simple        → answer → finalize
   ├─ tool           → tool → evaluate → (đủ tốt? answer : retry)
   ├─ missing_info  → clarify → finalize
   ├─ risky          → risky_action → approval → (được duyệt? tool... : clarify)
   └─ error          → retry → (còn lượt? tool... : dead_letter) → finalize
```

Mỗi ô trong sơ đồ trên = 1 hàm trong `nodes.py`. Mỗi mũi tên rẽ nhánh = 1 hàm trong `routing.py`.

---

## 3c. Vì sao có `tests/test_persistence.py` dù đề không bắt buộc file test này

Đề bài **không** bắt phải có file test tên `test_persistence.py` cụ thể — đúng, cái đó tôi tự thêm. Nhưng đề bài **có** bắt buộc phải có "persistence/recovery evidence" (bằng chứng lưu & phục hồi trạng thái) — đây là mục **Phase 3, 10 điểm riêng** trong rubric (`docs/LAB_GUIDE.md`), không phải phần tự chọn.

Vấn đề là: sau khi viết xong `persistence.py` (thêm SQLite), tôi cần **chứng minh** nó thật sự hoạt động, chứ không chỉ viết trong báo cáo "tôi đã dùng SQLite" suông. Có 2 cách chứng minh:
1. Chạy tay 1 lần, chụp/dán log vào báo cáo — nhưng chỉ là bằng chứng "đã từng chạy 1 lần", không tự động kiểm tra lại được, và không nằm trong repo nộp bài (chỉ nằm trong lịch sử chat).
2. **Viết thành test** — chạy lại bao nhiêu lần cũng ra cùng kết quả, nằm trong repo, ai cũng chạy `pytest` là thấy ngay, không thể "nói suông".

Tôi chọn cách 2. File `test_persistence.py` có 2 test:

- **`test_sqlite_checkpointer_records_state_history`**: chạy 1 câu hỏi qua graph với checkpointer SQLite, xong gọi `graph.get_state_history()` — kiểm tra có **nhiều hơn 1 checkpoint** được ghi lại (tức là mỗi bước đi qua đều có lưu, không phải chỉ lưu mỗi lúc xong).
- **`test_sqlite_checkpointer_survives_process_restart`**: chạy 1 câu hỏi qua graph, xong **tạo hẳn một checkpointer và graph MỚI** (giả lập việc tắt chương trình rồi mở lại — như bị crash), trỏ vào **cùng 1 file SQLite** — rồi đọc lại state cũ. Nếu đọc được, nghĩa là trạng thái sống sót được qua một lần "chết đi sống lại", không phụ thuộc bộ nhớ RAM của lần chạy trước.

Nói cách khác: test 1 chứng minh "có lưu dọc đường", test 2 chứng minh "lưu thật, không phải giả — tắt máy vẫn còn". Đây chính là 2 loại evidence mà `docs/LAB_GUIDE.md` liệt kê là đủ điều kiện: *"Show evidence: thread_id per run, state history, or crash-resume."*

## 4. Việc còn lại (không code được hộ)

- Đọc lại code một lượt để tự tin giải thích lúc demo (bắt buộc trong checklist nộp bài).
- Commit + push lên GitHub.
- Điền dòng "Repo/commit" trong `reports/lab_report.md` sau khi có link repo thật.
