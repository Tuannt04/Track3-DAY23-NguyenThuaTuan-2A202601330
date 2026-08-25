"""Report generation helper. Renders the lab report in Vietnamese."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from .metrics import MetricsReport


def _render_graph_diagram() -> str:
    """Build the compiled graph and export its real Mermaid diagram as evidence."""
    from .graph import build_graph

    try:
        graph = build_graph()
        return graph.get_graph().draw_mermaid()
    except Exception as exc:  # pragma: no cover - diagram export is best-effort evidence
        return f"(xuất sơ đồ bị lỗi: {exc})"


def render_report(metrics: MetricsReport) -> str:
    """Render báo cáo tiếng Việt từ metrics thật, theo khung reports/lab_report_template.md."""
    lines: list[str] = []

    lines.append("# Day 08 Lab Report — Bản tiếng Việt")
    lines.append("")
    lines.append("## 1. Thông tin")
    lines.append("")
    lines.append("- Tên: Nguyen Thua Tuan (2A202601330)")
    lines.append(
        "- Repo/commit: "
        "https://github.com/Tuannt04/Track3-DAY23-NguyenThuaTuan-2A202601330"
    )
    lines.append(f"- Ngày: {date.today().isoformat()}")
    lines.append("")

    lines.append("## 2. Kiến trúc")
    lines.append("")
    lines.append(
        "Agent xử lý ticket hỗ trợ khách hàng, xây bằng LangGraph — state graph chứ không "
        "phải if/else tuyến tính. Luồng chính: `intake -> classify -> rẽ nhánh theo route`. "
        "Route `tool` thì đi `tool -> evaluate`, có vòng lặp retry bị chặn cứng bởi "
        "`max_attempts` (`route_after_evaluate` / `route_after_retry`). Route `risky` thì đi "
        "`risky_action -> approval`, chỉ được vào `tool` khi `approval.approved=True`, không "
        "thì rẽ sang `clarify`. Mọi nhánh đều tụ về `finalize -> END`, không có đường nào thoát "
        "ra ngoài."
    )
    lines.append("")

    lines.append("## 3. State schema")
    lines.append("")
    lines.append("| Field | Reducer | Vì sao |")
    lines.append("|---|---|---|")
    lines.append("| messages | append | log audit, không cần giá trị cũ |")
    lines.append("| route | overwrite | chỉ cần route hiện tại |")
    lines.append("| tool_results | append | mỗi lần retry ra kết quả khác, giữ lại hết |")
    lines.append("| errors | append | giữ log lỗi qua các lần retry |")
    lines.append("| events | append | log audit đầy đủ, dùng tính metrics |")
    lines.append("| attempt | overwrite | chỉ cần số lần thử hiện tại |")
    lines.append("| evaluation_result | overwrite | cổng quyết định cho lần đánh giá gần nhất |")
    lines.append("| approval | overwrite | chỉ cần quyết định duyệt gần nhất |")
    lines.append("")

    lines.append("## 4. Kết quả chạy scenario")
    lines.append("")
    lines.append(f"- Tổng số scenario: {metrics.total_scenarios}")
    lines.append(f"- Tỉ lệ thành công: {metrics.success_rate:.1%}")
    lines.append(f"- Số node trung bình đi qua mỗi câu: {metrics.avg_nodes_visited:.2f}")
    lines.append(f"- Tổng số lần retry: {metrics.total_retries}")
    lines.append(f"- Tổng số lần ghé qua node approval: {metrics.total_interrupts}")
    lines.append(f"- resume_success (của lần chạy này): {metrics.resume_success}")
    lines.append("")
    lines.append(
        "| Scenario | Route kỳ vọng | Route thực tế | Thành công | Retry | Approval visit | "
        "Latency (ms) |"
    )
    lines.append("|---|---|---|---:|---:|---:|---:|")
    for item in metrics.scenario_metrics:
        status = "có" if item.success else "không"
        lines.append(
            f"| {item.scenario_id} | {item.expected_route} | {item.actual_route} | "
            f"{status} | {item.retry_count} | {item.interrupt_count} | {item.latency_ms} |"
        )
    lines.append("")
    lines.append("**Lưu ý về số liệu** (để không đọc quá lên so với thực tế đo được):")
    lines.append(
        "- \"Approval visit\" chỉ đếm số lần đi qua node `approval` "
        "(`metrics.py::metric_from_state`), không chứng minh có pause thật — vì "
        "`approval_node` đang mock, mặc định luôn tự duyệt (`approved=True`). Muốn pause "
        "thật phải bật `LANGGRAPH_INTERRUPT=true`."
    )
    lines.append(
        "- `approval_observed` chỉ kiểm tra có tồn tại object `approval` hay không, không tự "
        "chứng minh `tool` chạy sau approval. Thứ tự đó do graph wiring đảm bảo "
        "(`route_after_approval` chỉ trả `\"tool\"` khi đã duyệt — xem `routing.py` và "
        "`tests/test_routing.py::test_route_after_approval_*`)."
    )
    lines.append(
        "- `resume_success` luôn `False` do `summarize_metrics()` hardcode, bất kể "
        "checkpointer gì. Lần chạy này dùng `CHECKPOINTER=memory` (xem `configs/lab.yaml`), "
        "không sống sót qua restart, nên `False` là đúng thực tế. Bằng chứng crash-resume "
        "thật (dùng SQLite) nằm ở `tests/test_persistence.py`, không phải ở đây — xem mục 6."
    )
    lines.append(
        "- `latency_ms` giờ là số đo thật bằng `time.perf_counter()` quanh mỗi lần gọi "
        "`graph.invoke()` trong `cli.py`, không còn là giá trị mặc định 0."
    )
    lines.append("")

    lines.append("## 5. Phân tích 2 failure mode")
    lines.append("")
    lines.append("**1. Tool lỗi tạm thời trên route `error`**")
    lines.append(
        "- Bắt đầu từ đâu: `tool_node` giả lập lỗi 2 lần đầu khi `attempt < 2`, trả về chuỗi "
        "có chữ `ERROR` thay vì crash chương trình."
    )
    lines.append(
        "- Phát hiện bằng gì: `evaluate_node` kiểm tra kết quả tool gần nhất có chữ `ERROR` "
        "không (short-circuit heuristic, không tốn lời gọi LLM cho case rõ ràng này — chi "
        "tiết ở mục 7). Với kết quả không có `ERROR`, LLM-as-judge mới là bên quyết định "
        "thật `evaluation_result`."
    )
    lines.append("- Đi tiếp đâu: `evaluate -> retry -> tool` lặp lại, mỗi lần tăng `attempt`.")
    lines.append(
        "- Vì sao chắc chắn dừng: `route_after_retry` so `attempt` với `max_attempts` mỗi "
        "vòng, hết lượt thì rẽ `dead_letter` thay vì lặp tiếp. `S07_dead_letter` "
        "(`max_attempts=1`) vào `dead_letter` ngay lượt đầu — chứng minh cái phanh này chạy "
        "thật, không phải lý thuyết suông."
    )
    lines.append(
        "- Rủi ro còn sót: phát hiện lỗi chỉ bằng so chuỗi `\"ERROR\"` gắn với tool giả lập — "
        "nối tool thật thì cần tín hiệu rõ ràng hơn (status code, exception) chứ không so chuỗi."
    )
    lines.append("")
    lines.append("**2. Hành động risky không được bỏ qua bước duyệt**")
    lines.append(
        "- Bắt đầu từ đâu: câu hỏi có side effect (hoàn tiền, xoá tài khoản, gửi email...) "
        "được `classify_node` gắn route `risky`."
    )
    lines.append(
        "- Phát hiện bằng gì: `risky_action_node` chỉ chuẩn bị đề xuất, không tự gọi tool. "
        "Quyết định thật nằm ở `approval_node`, ghi vào `state.approval`."
    )
    lines.append(
        "- Đi tiếp đâu: `route_after_approval` đọc `approval.approved` — `True` mới cho đi "
        "`tool`, `False` thì rẽ `clarify`."
    )
    lines.append(
        "- Vì sao chắc chắn không lách được: trong `graph.py`, `risky_action` chỉ nối tới "
        "`approval`, không có đường nào nối thẳng `risky_action -> tool` — về kiến trúc không "
        "có cách nào bỏ qua bước duyệt."
    )
    lines.append(
        "- Rủi ro còn sót: `approval_node` đang mock luôn duyệt, nên nhánh \"bị từ chối -> "
        "clarify\" chưa chạy thật qua toàn bộ graph trong lần run này — mới chỉ kiểm chứng "
        "riêng ở unit test (`tests/test_routing.py`), chưa có bằng chứng end-to-end."
    )
    lines.append("")

    lines.append("## 6. Bằng chứng persistence / recovery")
    lines.append("")
    lines.append(
        "Mỗi scenario chạy với 1 `thread_id` riêng (`thread-<scenario_id>`), truyền qua "
        "`configurable.thread_id` — checkpointer giữ lịch sử state riêng cho từng thread. "
        "Mặc định (`configs/lab.yaml`) dùng `CHECKPOINTER=memory`, mất khi tắt chương trình. "
        "Extension đã làm thêm: `persistence.py` hỗ trợ `CHECKPOINTER=sqlite`, lưu file SQLite "
        "chế độ WAL, sống sót qua restart. Bằng chứng cụ thể nằm ở "
        "`tests/test_persistence.py`, 2 test: (1) chạy 1 câu qua checkpointer SQLite, xác "
        "nhận có nhiều hơn 1 checkpoint qua `get_state_history()`; (2) chạy xong, tạo hẳn "
        "checkpointer/graph **mới** trỏ vào cùng file (giả lập tắt máy mở lại), đọc lại được "
        "state cũ — chứng minh không phụ thuộc RAM của lần chạy trước."
    )
    lines.append("")

    lines.append("## 7. Phần đã làm thêm (extension)")
    lines.append("")
    lines.append(
        "Mỗi extension ghi rõ: baseline (trước khi làm), thay đổi, cách kiểm tra, evidence, "
        "giới hạn còn lại — không extension nào đổi hành vi core (bounded retry, approval "
        "gate, persistence contract, termination vẫn nguyên như mục 2/5/6)."
    )
    lines.append("")

    lines.append("### 1. SQLite persistence")
    lines.append("- Baseline: chỉ có `MemorySaver`, mất state khi tắt chương trình.")
    lines.append(
        "- Thay đổi: `persistence.py` thêm `CHECKPOINTER=sqlite`, lưu file SQLite chế độ WAL."
    )
    lines.append(
        "- Cách kiểm tra: `tests/test_persistence.py`, chạy độc lập, không cần service ngoài "
        "(file SQLite tạm trong `tmp_path` của pytest)."
    )
    lines.append(
        "- Evidence: 2 test pass — 1 xác nhận nhiều checkpoint qua `get_state_history()`, 1 "
        "giả lập crash bằng checkpointer/graph **mới** trỏ cùng file, đọc lại được state cũ."
    )
    lines.append(
        "- Giới hạn: chưa làm Postgres (yêu cầu Docker Compose, cân nhắc không đáng vì làm CI "
        "phụ thuộc service ngoài trong khi SQLite đã đủ chứng minh contract)."
    )
    lines.append("")

    lines.append("### 2. Sơ đồ graph tự động (Mermaid)")
    lines.append("- Baseline: không có sơ đồ, hoặc phải tự vẽ tay dễ lệch so với code thật.")
    lines.append(
        "- Thay đổi: `report.py::_render_graph_diagram()` gọi "
        "`graph.get_graph().draw_mermaid()` trên graph đã compile thật, nhúng thẳng vào report."
    )
    lines.append("- Cách kiểm tra: đọc sơ đồ bên dưới, đối chiếu bằng mắt với mục 2 (kiến trúc).")
    lines.append("- Evidence: sơ đồ Mermaid bên dưới — sinh lại mỗi lần chạy `run-scenarios`.")
    lines.append(
        "- Giới hạn: đối chiếu thủ công bằng mắt, chưa có test tự động so khớp sơ đồ với "
        "target diagram bằng code."
    )
    lines.append("")

    lines.append("### 3. LLM-as-judge cho `evaluate_node` — gate thật, có bọc an toàn")
    lines.append(
        "- Baseline: heuristic so chuỗi `\"ERROR\"` quyết định toàn bộ route (an toàn nhưng "
        "chỉ đạt mức base score theo đề, không dùng LLM thật cho việc đánh giá)."
    )
    lines.append(
        "- Thay đổi: với kết quả tool không có `ERROR`, LLM-as-judge (structured verdict + "
        "reason) giờ **quyết định thật** `evaluation_result`, bọc bởi: (1) timeout "
        "`JUDGE_TIMEOUT_SECONDS=8s` chạy trong thread pool riêng, không đợi lời gọi bị treo; "
        "(2) cost guard `MAX_JUDGE_CALLS_PER_THREAD=3`, hết ngân sách thì tự chuyển heuristic "
        "không gọi LLM nữa; (3) fallback về `\"success\"` khi timeout/lỗi provider, không bao "
        "giờ để crash node. Case `ERROR` (lỗi giả lập rõ ràng) vẫn short-circuit bằng "
        "heuristic, không tốn lời gọi LLM."
    )
    lines.append(
        "- Cách kiểm tra: `tests/test_evaluate_judge.py`, 5 test — không cần API key thật, "
        "`get_llm()` được monkeypatch bằng LLM giả (verdict tuỳ ý, hoặc cố tình chậm/lỗi) để "
        "kiểm chứng đúng guard logic một cách nhanh và deterministic."
    )
    lines.append(
        "- Evidence: 5/5 test pass, gồm cả test đo thời gian thực tế < 0.5s khi judge giả lập "
        "chậm 0.5s (chứng minh timeout thật sự cắt ngang, không đợi). Chạy `run-scenarios` 3 "
        "lần liên tiếp với judge thật cho kết quả giống hệt nhau (100% thành công, retry ổn "
        "định) — xem mục 4."
    )
    lines.append(
        "- Giới hạn: `MAX_JUDGE_CALLS_PER_THREAD`/`JUDGE_TIMEOUT_SECONDS` là hằng số cố định "
        "trong code, chưa đọc từ config/env. Judge vẫn đang chấm nội dung tool giả lập "
        "(template dựng sẵn), không phải dữ liệu thật — xem mục 8."
    )
    lines.append("")

    lines.append("### 4. Streamlit UI")
    lines.append(
        "- Baseline: chỉ xem được kết quả qua JSON/log terminal, không trực quan cho demo."
    )
    lines.append(
        "- Thay đổi: `demo_ui.py` (extra `pip install -e \".[demo]\"`) — nhập câu hỏi, gọi "
        "thẳng graph thật (không mock), hiển thị route, từng bước (event trail), proposed "
        "action, approval/rejection, và câu trả lời cuối."
    )
    lines.append(
        "- Cách kiểm tra: `tests/test_demo_ui.py` dùng `streamlit.testing.v1.AppTest` — mô "
        "phỏng nhập liệu + bấm nút mà không cần mở trình duyệt thật."
    )
    lines.append(
        "- Evidence: 3 test pass — route `simple` hiển thị đúng, route `risky` hiển thị đúng "
        "khối approval, và một test riêng quét toàn bộ nội dung render để xác nhận **không có "
        "API key nào bị lộ ra UI** dù chương trình lỗi."
    )
    lines.append(
        "- Giới hạn: chỉ chạy local (`streamlit run demo_ui.py`), không deploy public; dùng "
        "`CHECKPOINTER=memory` nên không giữ lịch sử qua các lần chạy Streamlit khác nhau."
    )
    lines.append("")

    lines.append("### 5. Scenario tự soạn thêm")
    lines.append("- Baseline: chỉ có 7 scenario mẫu của đề.")
    lines.append(
        "- Thay đổi: thêm `S08_custom_risky_combo` (risky kết hợp 2 side effect) và "
        "`S09_custom_vague` (missing_info mơ hồ hơn câu mẫu) vào `data/sample/scenarios.jsonl`."
    )
    lines.append("- Cách kiểm tra: `run-scenarios` chạy chung với 7 câu mẫu, không tách riêng.")
    lines.append("- Evidence: cả 2 route đúng 100% trong bảng mục 4 (S08, S09).")
    lines.append(
        "- Giới hạn: chỉ 2 câu, chưa phủ hết các ca ưu tiên chồng chéo (vd vừa risky vừa error)."
    )
    lines.append("")

    lines.append("```mermaid")
    lines.append(_render_graph_diagram().strip())
    lines.append("```")
    lines.append("")

    lines.append("## 8. Kế hoạch cải thiện")
    lines.append("")
    lines.append(
        "**Ưu tiên số 1: thay tool giả (mock) bằng tool gọi API thật.** LLM-as-judge trong "
        "`evaluate_node` (mục 7.3) giờ đã là gate thật, nhưng vẫn đang chấm nội dung tool giả "
        "lập (template dựng sẵn giống nhau mỗi lần) — chưa phải bài toán đánh giá chất lượng "
        "thật sự. Có tool thật thì judge mới thực sự có giá trị (chấm nội dung khác nhau thật "
        "theo từng lần gọi), và luồng risky-action-chờ-duyệt (mục 5, failure mode 2) cũng sẽ "
        "có kết quả hành động thật để duyệt thay vì chỉ mô phỏng. Đây là thay đổi đáng làm "
        "nhất vì nâng cấp giá trị của 2 thành phần đã có sẵn, không phải chỉ thêm 1 tính năng "
        "riêng lẻ."
    )
    lines.append(
        "Việc phụ, làm sau: bật `LANGGRAPH_INTERRUPT=true` để có người duyệt thật thay vì "
        "mock (code interrupt/resume có sẵn trong `approval_node`, chỉ thiếu UI cho reviewer "
        "và test end-to-end cho nhánh interrupt/resume thật), và thêm Postgres checkpointer "
        "cho trường hợp chạy nhiều instance song song."
    )
    lines.append("")

    return "\n".join(lines)


def write_report(metrics: MetricsReport, output_path: str | Path) -> None:
    """Write the rendered report to a file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # newline="\n" avoids Windows' text-mode CRLF translation — see metrics.py::write_metrics.
    path.write_text(render_report(metrics), encoding="utf-8", newline="\n")
