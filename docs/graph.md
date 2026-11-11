# Sơ đồ graph (Day 55)

Sinh tự động từ code: `python -c "from agents.graph import graph; print(graph.get_graph().draw_mermaid())"`.
Nét đứt = cạnh có điều kiện (supervisor quyết định theo `route`); nét liền = luôn đi.

```mermaid
---
config:
  flowchart:
    curve: linear
---
graph TD;
	__start__([<p>__start__</p>]):::first
	supervisor(supervisor)
	policy(policy)
	order(order)
	writer(writer)
	__end__([<p>__end__</p>]):::last
	__start__ --> supervisor;
	order --> writer;
	policy --> writer;
	supervisor -.-> order;
	supervisor -.-> policy;
	supervisor -.-> writer;
	writer --> __end__;
	classDef default fill:#f2f0ff,line-height:1.2
	classDef first fill-opacity:0
	classDef last fill:#bfb6fc

```

| Node | Dùng LLM? | Đọc | Ghi |
|---|---|---|---|
| `supervisor` | Có (Nova Lite, temp 0) | `question` | `route`, `order_id` |
| `policy` | Không | `question` | `policy_hits` |
| `order` | Không | `order_id`, `customer_id`, `as_of_date` | `order_data` (+ `return_check`, `warranty_check` từ `agents/rules.py`), `order_lookup` |
| `writer` | Có (Nova Lite, temp 0.2) — trừ câu ngoài phạm vi | tất cả ở trên | `answer`, `sources` |

Mọi node trả `steps: 1`, reducer cộng dồn: cả hai nhánh = 4, một nhánh = 3, ngoài phạm vi = 2.
