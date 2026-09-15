# FP-004 图片元数据持久化 — 设计说明

## 目标
把「帖子 id ↔ 存储文件名 ↔ 提交顺序」持久化：新增 `post_images` 表（每张图一行）＋读写模块 `social_app/post_images.py`，复用 `db.py` 的幂等 schema 机制平滑升级老数据库。

## 关键决策

1. **表结构＝任务卡拍板口径**：新表 `post_images(id, post_id, storage_name, position, created_at)`＋`UNIQUE(post_id, position)`＋索引 `idx_post_images_post(post_id, position)`。UNIQUE 约束兜底重复写（触发 `sqlite3.IntegrityError`），position 从 1 开始（1..n，与提交顺序一致，决策 D-7）。
2. **幂等升级**：DDL 以 `CREATE TABLE/INDEX IF NOT EXISTS` 追加进 `db.SCHEMA_SQL`，`init_db()` 对老库重复执行不报错、既有数据无损——无需触碰 `_upgrade_schema`（无新列加到既有表）。
3. **模块 API**（契约源头，FP-006 发帖编排将按此调用）：
   - `save_post_images(post_id, storage_names, conn=None)`：按列表顺序写入；空列表不写任何行。传 `conn`＝在调用方事务内执行（不自行 commit，整帖原子性由调用方经 `db.transaction()` 控制）；不传＝自开连接、写完即 commit。
   - `list_post_images(post_id)`：返回 `[{"image_id", "post_id", "storage_name", "position"}]`，按 position ASC；无记录返回 `[]`（纯文本帖路径不报错）。
4. **底层访问**：全部走 `social_app.db` 通用 API（`query_all` / `transaction`），不另开存储通道。

## 非范围
- 图片字节落盘（FP-003）、上传校验（FP-002）、`POST /posts` 编排与事务回滚整合（FP-006）、信息流按帖聚合查询（FP-008）、删帖级联清理。
