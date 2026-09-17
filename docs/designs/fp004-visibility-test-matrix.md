# FP-004 Design: Visibility Rules Test Matrix (pytest)

Task card: `input/tasks/comment-visibility-mutual-friends/FP-004-visibility-test-matrix.task.md`
(sole spec). Goal: freeze every visible/hidden boundary of UC-001/UC-002/UC-003
as a passing checklist-style pytest matrix, so the visibility semantics
(dispatch, visible set, per-row reply judgment, promotion, empty state,
fail-closed, real-time fallback) cannot drift. Pure test deliverable — no
product code changes (card §5).

## Approach

- **One matrix file.** `tests/test_visibility_matrix.py` groups the card §8
  use-case groups: dispatch (friend-post filter / own-post full / one-way-post
  full / unfollow fallback), nested replies (reply-level hiding / hidden-parent
  promotion), empty state, fail-closed, primitive boundaries (real-time
  judgment + set recalculation), and a black-box `GET /` end-to-end group on
  the card §3.2 assertion surface.
- **Seed-data factory.** One `world` fixture builds the persona group in a
  single sweep (card §4): reader R, friend author P, mutual friends M and M2
  (union breadth), N = mutual with R only, O = mutual with P only (set
  boundary: "mutual with BOTH" is required), stranger S, one-way follower T of
  R, one-way followee W of R — plus the follow graph and the three dispatch
  posts (friend / own / one-way). A `seeded_comments` fixture layers a fixed
  comment tree (top-level rows from every persona, replies nested under a
  visible and under a hidden parent) with deterministic ids/timestamps for the
  golden snapshot. Seeds follow card §6: `SOCIAL_DB` → tmp_path +
  `db.init_db()`, direct inserts, `DELETE FROM follows` for unfollows,
  monkeypatched raisers for fail-closed.
- **Checklist/parametrized coverage.** The author × context boundaries are
  `pytest.mark.parametrize` tables (visible set membership; dispatch context ×
  author; reply parent × reply author), so every matrix cell is an independent
  test id and a new boundary is one table row. Non-table cases (fallback,
  promotion, empty state, fail-closed, primitives) stay as named tests for
  readable failure output.
- **Real implementations, no shims.** Wave-3 start: FP-001/FP-002/FP-003 are
  merged (git log), so per card §6 the matrix exercises the real
  `is_mutual_follow` / `mutual_friend_ids` / `visible_comments` / feed / HTTP
  stack directly — no inline substitute shims.
- **Assertion surfaces.** Feed level: `feed.get_feed(R)` rows' `comments`
  (contents/ids/order, FP-009 dict shape). HTTP level: logged-in `GET /` body —
  `<li class="comment">` vs `<li class="comment reply">`, promoted replies at
  top level, `<p class="comments-empty">暂无评论</p>`, anonymous 303 →
  `/login`. Unique persona-prefixed content strings make body-level
  presence/absence unambiguous.

## Key decisions

1. **Two boundary personas beyond the card's five (N, O)**: the visible set is
   mutual-with-both ∪ {author, reader}, so "mutual with reader only" and
   "mutual with author only" must be *hidden* — that is the sharpest set edge
   and the matrix's job to freeze.
2. **Unfollow fallback deletes P→R, never R→P**: `get_feed` shows self +
   followees; deleting R→P would remove the post from the feed entirely (feed
   scope), while deleting P→R keeps the post visible and flips only the
   mutual-follow dispatch — exactly the UC-003 回落 boundary.
3. **Golden snapshot + parametrized cells**: one full-tree snapshot test pins
   the combined outcome (filter ∪ promotion ∪ ordering) while the parametrized
   cells pin each boundary in isolation; both share the same factory.
4. **Fail-closed asserted per post**: a raising primitive must empty only the
   friend post's comments (own post short-circuits before the primitives), at
   both feed and HTTP level — "宁可少显示" never becomes "少显示一切".
5. **Primitive real-time tests call the primitives directly AND through the
   filter**: `is_mutual_follow` / `mutual_friend_ids` flip on the next call
   after a `DELETE FROM follows`, and the composed path (M leaves the circle →
   M's comment disappears; M rejoins → reappears) proves no snapshot/cache sits
   in between (weak-dependency integration面 FP-001/FP-002).
6. **No product-code edits** (card §5): a red matrix cell means an issue task
   back to FP-001/FP-002/FP-003, not a fix here.

## Verification

`python3 -m pytest -q tests/test_visibility_matrix.py` (matrix), then the full
regression `python3 -m pytest -q` (acceptance 4). Scenarios documented in
`docs/test-cases/fp004-visibility-matrix.md`.
