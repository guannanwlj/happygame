# FP-004 图片元数据持久化 — 测试场景

对应验收标准（任务卡 §7/§8），测试文件 `tests/test_fp004_image_metadata.py`。
所有用例使用临时库（`monkeypatch.setenv("SOCIAL_DB", str(tmp_path/"t.db"))`）＋`db.init_db()`；种子 user（INSERT INTO users）＋种子 post（INSERT INTO posts）；storage_names 用任意唯一串。

## Schema / 升级
1. **新表随 init_db 建立**：init_db 后 `post_images` 表与 `idx_post_images_post` 索引存在。
2. **老库平滑升级**：手工按旧版 DDL（仅 users/posts 等既有表、无 post_images）初始化旧库并插入帖子数据 → 执行 `db.init_db()` → post_images 表建立、既有 posts 数据无损。
3. **升级幂等**：对新库再次（多次）`init_db()` 不报错、数据不变。

## save_post_images
4. **顺序写入**：种子帖子＋`["a.png","b.png","c.png"]` → 3 行入库且 position 依次为 1/2/3（与提交顺序一致）。
5. **空列表**：`save_post_images(pid, [])` → 不写任何行。
6. **UNIQUE 兜底**：同帖同 position 重复写 → `sqlite3.IntegrityError`。
7. **conn 事务语义**：传入 conn 时在调用方事务内执行、不自行 commit——调用方 rollback 后无行落库（为 FP-006 整帖回滚预留的契约）。

## list_post_images
8. **按序返回**：已存 3 条记录的帖子 → 返回按 position 升序、storage_name 与写入对应，且每项含 `image_id`/`post_id`/`storage_name`/`position` 四键。
9. **无图帖子**：无任何图片记录的帖子 → 返回 `[]`（纯文本帖路径不报错）。
10. **帖间隔离**：多帖各存各的图，list 只返回本帖记录。

## 验证命令
- `pytest tests/test_fp004_image_metadata.py -q`
- 回归：`pytest -q`
