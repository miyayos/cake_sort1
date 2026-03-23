import pyxel
import random
from collections import deque
from copy import deepcopy

# ============================================================
# 定数
# ============================================================
BOARD_COLS   = 3
BOARD_ROWS   = 4
MAX_ON_PLATE = 5    # 1皿の最大個数
WHOLE_COUNT  = 6    # 消去に必要な個数
HAND_SIZE    = 3    # 手札枚数

SCREEN_W = 152

# ボード描画
CELL_W  = 44
CELL_H  = 44
BOARD_X = (SCREEN_W - BOARD_COLS * CELL_W) // 2
BOARD_Y = 26

# 手札エリア
HAND_Y        = BOARD_Y + BOARD_ROWS * CELL_H + 10
HAND_CARD_W   = 40
HAND_CARD_H   = 34
HAND_SPACING  = 4
HAND_X        = (SCREEN_W - HAND_SIZE * (HAND_CARD_W + HAND_SPACING) + HAND_SPACING) // 2

# ボタン
BTN_W = 60
BTN_H = 13
BTN_Y = HAND_Y + HAND_CARD_H + 8

# 画面高さをレイアウトから自動計算
SCREEN_H = BTN_Y + BTN_H + 6

# ケーキ種類（レベル別に解放）
#  種類  色    文字  名前
CAKE_DATA = [
    (8,  "S", "いちご"),
    (9,  "O", "みかん"),
    (10, "L", "レモン"),
    (11, "M", "抹茶"),
    (14, "B", "ブルー"),
    (15, "K", "さくら"),
    (4,  "C", "チョコ"),
    (13, "P", "パイン"),
]
# レベルで使う種類数
def types_for_level(lv):
    return min(3 + lv - 1, len(CAKE_DATA))   # Lv1=3,Lv2=4,...

# 消去アニメ
CLEAR_FRAMES = 18

# ============================================================
# ヘルパー
# ============================================================
def make_deck(n_types):
    """山札: 各種類が6の倍数になるよう生成"""
    deck = []
    per_type = 12
    for t in range(n_types):
        deck.extend([t] * per_type)
    random.shuffle(deck)
    return deque(deck)


def make_plate(cake_type, count):
    """皿 = {"type": int, "count": int}"""
    return {"type": cake_type, "count": count}


def draw_plate(x, y, plate, selected=False, small=False):
    """皿＋積まれたケーキを描画"""
    cw = HAND_CARD_W if small else CELL_W
    ch = HAND_CARD_H if small else CELL_H

    # 皿の背景
    bg     = 7 if selected else 13
    border = 10 if selected else 6
    pyxel.rect(x + 2, y + 2, cw - 4, ch - 4, bg)
    pyxel.rectb(x + 1, y + 1, cw - 2, ch - 2, border)

    if plate is None:
        # 空セル
        pyxel.rect(x + 2, y + 2, cw - 4, ch - 4, 1)
        pyxel.rectb(x + 1, y + 1, cw - 2, ch - 2, 5)
        return

    cake_type  = plate["type"]
    count      = plate["count"]
    col        = CAKE_DATA[cake_type][0]
    ch_char    = CAKE_DATA[cake_type][1]

    # 皿（底）
    plate_y = y + ch - 7
    pyxel.rect(x + 4, plate_y, cw - 8, 4, 7)
    pyxel.rect(x + 6, plate_y + 4, cw - 12, 2, 6)

    # ケーキを縦に積む（最大5個）
    cake_h   = max(3, (ch - 14) // MAX_ON_PLATE)
    stack_h  = count * cake_h
    stack_y  = plate_y - stack_h - 1

    for i in range(count):
        ky = stack_y + i * cake_h
        # 本体
        pyxel.rect(x + 6, ky, cw - 12, cake_h - 1, col)
        # クリーム（最上段のみ）
        if i == count - 1:
            pyxel.rect(x + 5, ky - 2, cw - 10, 3, 7)
        # 影ライン
        pyxel.line(x + 6, ky + cake_h - 2, x + cw - 7, ky + cake_h - 2, max(1, col - 2))

    # 個数テキスト
    cnt_str = str(count)
    tx = x + cw - 10
    ty = y + 3
    pyxel.rect(tx - 1, ty - 1, 9, 8, 0)
    pyxel.text(tx, ty, cnt_str, 7)

    # 種類文字（中央）
    pyxel.text(x + cw // 2 - 2, y + ch // 2 + 2, ch_char, 0)

    # 選択時：上に▲
    if selected:
        ax = x + cw // 2
        pyxel.tri(ax - 4, y - 1, ax + 4, y - 1, ax, y - 6, 10)


# ============================================================
# アプリ
# ============================================================
class App:
    def __init__(self):
        pyxel.init(SCREEN_W, SCREEN_H, title="ケーキソートパズル", fps=60, display_scale=2)
        pyxel.mouse(True)
        pyxel.gamepad = 0
        self.level = 1
        self.total_score = 0
        self.new_game()
        pyxel.run(self.update, self.draw)

    # ----------------------------------------------------------
    def new_game(self):
        self.n_types  = types_for_level(self.level)
        self.board    = [[None] * BOARD_COLS for _ in range(BOARD_ROWS)]
        self.deck     = make_deck(self.n_types)
        self.hand     = []
        self.selected = None
        self.score    = 0
        self.combo    = 0
        self.combo_timer  = 0
        self.game_over    = False
        self.cleared_count = 0
        self.level_goal   = self.n_types * 3   # 消去n回でレベルアップ
        self.anim_cells   = {}  # {(r,c): frames_left}
        self.btn_flash    = None
        self.timer        = 0
        self._refill_hand()

    # ----------------------------------------------------------
    def _refill_hand(self):
        while len(self.hand) < HAND_SIZE and self.deck:
            t = self.deck.popleft()
            count = random.randint(1, MAX_ON_PLATE - 1)
            self.hand.append(make_plate(t, count))

    # ----------------------------------------------------------
    def _place(self, row, col):
        if self.selected is None:
            return
        if self.board[row][col] is not None:
            return
        plate = self.hand.pop(self.selected)
        self.selected = None
        self.board[row][col] = plate
        self._run_chain()
        self._refill_hand()
        self._check_game_over()

    # ----------------------------------------------------------
    def _run_chain(self):
        """全体を繰り返しスキャンして連鎖を解決"""
        changed = True
        while changed:
            changed = False
            # 隣接する同種を合体させる
            if self._merge_step():
                changed = True
            # 6個以上を消去
            if self._clear_step():
                changed = True

    def _merge_step(self):
        """隣接する同種皿を合体（移動）。変化があればTrue"""
        changed = False
        for r in range(BOARD_ROWS):
            for c in range(BOARD_COLS):
                p = self.board[r][c]
                if p is None:
                    continue
                for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
                    nr, nc = r+dr, c+dc
                    if not (0 <= nr < BOARD_ROWS and 0 <= nc < BOARD_COLS):
                        continue
                    nb = self.board[nr][nc]
                    if nb is None or nb["type"] != p["type"]:
                        continue
                    # 合体できる（合計がいくつでも合体）
                    total = p["count"] + nb["count"]
                    # 合体先に集約（nr,ncへ）
                    self.board[nr][nc] = make_plate(p["type"], total)
                    self.board[r][c]   = None
                    changed = True
                    break
                if changed:
                    break
            if changed:
                break
        return changed

    def _clear_step(self):
        """WHOLE_COUNT以上の皿を消去。変化があればTrue"""
        changed = False
        for r in range(BOARD_ROWS):
            for c in range(BOARD_COLS):
                p = self.board[r][c]
                if p is None:
                    continue
                if p["count"] >= WHOLE_COUNT:
                    extra = p["count"] - WHOLE_COUNT
                    self.board[r][c] = None
                    self.anim_cells[(r, c)] = CLEAR_FRAMES
                    pts = 100 * max(1, self.combo)
                    self.score       += pts
                    self.total_score += pts
                    self.combo       += 1
                    self.combo_timer  = 90
                    self.cleared_count += 1
                    # 余剰分は新しい皿として残す
                    if extra > 0:
                        self.board[r][c] = make_plate(p["type"], extra)
                    changed = True
        return changed

    # ----------------------------------------------------------
    def _check_game_over(self):
        # 空きマスなし かつ 手札あり かつ 合体もできない
        empty = any(
            self.board[r][c] is None
            for r in range(BOARD_ROWS)
            for c in range(BOARD_COLS)
        )
        if not empty and self.hand:
            # 隣接合体可能か確認
            if not self._can_merge_any():
                self.game_over = True

    def _can_merge_any(self):
        for r in range(BOARD_ROWS):
            for c in range(BOARD_COLS):
                p = self.board[r][c]
                if p is None:
                    continue
                for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
                    nr, nc = r+dr, c+dc
                    if 0 <= nr < BOARD_ROWS and 0 <= nc < BOARD_COLS:
                        nb = self.board[nr][nc]
                        if nb and nb["type"] == p["type"]:
                            return True
        return False

    # ----------------------------------------------------------
    def _board_pos(self, mx, my):
        bx, by = mx - BOARD_X, my - BOARD_Y
        if bx < 0 or by < 0:
            return None, None
        col, row = bx // CELL_W, by // CELL_H
        if 0 <= col < BOARD_COLS and 0 <= row < BOARD_ROWS:
            return row, col
        return None, None

    def _hand_index(self, mx, my):
        for i in range(len(self.hand)):
            hx = HAND_X + i * (HAND_CARD_W + HAND_SPACING)
            if hx <= mx <= hx + HAND_CARD_W and HAND_Y <= my <= HAND_Y + HAND_CARD_H:
                return i
        return None

    # ----------------------------------------------------------
    def update(self):
        self.timer += 1

        # アニメ更新
        done = [k for k, v in self.anim_cells.items() if v <= 1]
        for k in done:
            del self.anim_cells[k]
        for k in list(self.anim_cells):
            self.anim_cells[k] -= 1

        # コンボタイマー
        if self.combo_timer > 0:
            self.combo_timer -= 1
        else:
            self.combo = 0

        # ボタンフラッシュ
        if self.btn_flash:
            nm, t = self.btn_flash
            self.btn_flash = (nm, t-1) if t > 1 else None

        # レベルアップ判定
        if self.cleared_count >= self.level_goal and not self.game_over:
            self.level += 1
            self.cleared_count = 0
            self.new_game()
            return

        if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
            mx, my = pyxel.mouse_x, pyxel.mouse_y

            # Resetボタン
            bx = (SCREEN_W - BTN_W) // 2
            if bx <= mx <= bx + BTN_W and BTN_Y <= my <= BTN_Y + BTN_H:
                self.level = 1
                self.total_score = 0
                self.new_game()
                self.btn_flash = ("reset", 10)
                return

            if self.game_over:
                return

            # 手札タップ
            hi = self._hand_index(mx, my)
            if hi is not None:
                self.selected = hi if self.selected != hi else None
                return

            # ボードタップ
            if self.selected is not None:
                row, col = self._board_pos(mx, my)
                if row is not None and self.board[row][col] is None:
                    self._place(row, col)

    # ----------------------------------------------------------
    def draw(self):
        pyxel.cls(0)

        # タイトル＆レベル
        pyxel.text(28, 3, "CAKE SORT PUZZLE", 14)
        pyxel.text(4,  13, f"Lv.{self.level}  SCORE:{self.score}", 7)

        # レベル進捗バー
        goal  = self.level_goal
        prog  = min(self.cleared_count, goal)
        bar_w = BOARD_COLS * CELL_W
        pyxel.rect(BOARD_X, BOARD_Y - 5, bar_w, 3, 5)
        pyxel.rect(BOARD_X, BOARD_Y - 5, bar_w * prog // max(goal, 1), 3, 11)

        # ボード
        for r in range(BOARD_ROWS):
            for c in range(BOARD_COLS):
                x = BOARD_X + c * CELL_W
                y = BOARD_Y + r * CELL_H

                # 消去アニメ
                if (r, c) in self.anim_cells:
                    t = self.anim_cells[(r, c)]
                    flash_col = 7 if t % 4 < 2 else 10
                    pyxel.rect(x + 2, y + 2, CELL_W - 4, CELL_H - 4, flash_col)
                    pyxel.rectb(x + 1, y + 1, CELL_W - 2, CELL_H - 2, 9)
                    continue

                draw_plate(x, y, self.board[r][c])

        # ボード外枠
        pyxel.rectb(BOARD_X - 1, BOARD_Y - 1,
                    BOARD_COLS * CELL_W + 2, BOARD_ROWS * CELL_H + 2, 6)

        # コンボ表示
        if self.combo_timer > 0 and self.combo > 1:
            c = 9 if self.combo_timer > 30 else 6
            pyxel.text(BOARD_X + BOARD_COLS * CELL_W - 38,
                       BOARD_Y - 5, f"x{self.combo} COMBO!", c)

        # 手札ラベル
        pyxel.text(HAND_X, HAND_Y - 9, "NEXT:", 13)

        # 手札描画
        for i in range(HAND_SIZE):
            hx = HAND_X + i * (HAND_CARD_W + HAND_SPACING)
            if i < len(self.hand):
                draw_plate(hx, HAND_Y, self.hand[i],
                           selected=(self.selected == i), small=True)
            else:
                # 空スロット
                pyxel.rectb(hx, HAND_Y, HAND_CARD_W, HAND_CARD_H, 5)

        # ケーキ種類凡例
        legend_y = HAND_Y + HAND_CARD_H + 6
        pyxel.text(4, legend_y, "Types:", 13)
        for i in range(self.n_types):
            col, ch, name = CAKE_DATA[i]
            lx = 4 + i * 20
            pyxel.rect(lx, legend_y + 7, 10, 8, col)
            pyxel.text(lx + 2, legend_y + 8, ch, 0)

        # Resetボタン
        bx = (SCREEN_W - BTN_W) // 2
        is_fl = self.btn_flash and self.btn_flash[0] == "reset"
        pyxel.rect(bx, BTN_Y, BTN_W, BTN_H, 7 if is_fl else 5)
        pyxel.rectb(bx, BTN_Y, BTN_W, BTN_H, 13)
        pyxel.text(bx + (BTN_W - 5*4)//2, BTN_Y + 4,
                   "Reset", 0 if is_fl else 7)

        # ゲームオーバー
        if self.game_over:
            for i in range(0, SCREEN_W, 2):
                for j in range(0, SCREEN_H, 2):
                    pyxel.pset(i, j, 0)
            pw, ph = 130, 85
            px = (SCREEN_W - pw) // 2
            py = (SCREEN_H - ph) // 2
            pyxel.rect(px, py, pw, ph, 1)
            pyxel.rectb(px, py, pw, ph, 8)
            pyxel.rectb(px+1, py+1, pw-2, ph-2, 9)
            if (self.timer // 20) % 2 == 0:
                pyxel.text(px + 24, py + 10, "GAME  OVER!", 8)
            pyxel.text(px + 16, py + 26, f"Level:  {self.level}", 7)
            pyxel.text(px + 16, py + 36, f"Score:  {self.score}", 7)
            pyxel.text(px + 16, py + 46, f"Total:  {self.total_score}", 14)
            pyxel.text(px + 10, py + 60, "Tap [Reset] to retry", 13)


App()
