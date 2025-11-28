import requests
import numpy as np
import copy
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, render_template, jsonify, request
import json

#==========================================Database Configuration==========================================
CLICKHOUSE_HTTP = "http://localhost:8123"
CLICKHOUSE_USER = "default"
CLICKHOUSE_PASS = "admin"
DATABASE = "tictactoe"

# Connection pooling
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(
    pool_connections=50,
    pool_maxsize=50,
    max_retries=2
)
session.mount('http://', adapter)


def execute_query(sql: str) -> int:
    """
    Thực thi SQL query và trả về COUNT
    
    Args:
        sql: SQL query string
        
    Returns:
        Số lượng rows (int)
    """
    try:
        response = session.post(
            CLICKHOUSE_HTTP,
            params={
                "user": CLICKHOUSE_USER,
                "password": CLICKHOUSE_PASS,
                "database": DATABASE
            },
            data=sql,
            timeout=10
        )
        
        if response.status_code != 200:
            print(f"❌ Query error {response.status_code}: {response.text}")
            return 0
        
        result = response.text.strip()
        if not result:
            return 0
        
        return int(result)
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        return 0


def get_odd_table_names(move_count: int) -> str:
    """
    Lấy danh sách tên bảng odd (lượt lẻ)
    
    Args:
        move_count: Số nước đã đi (không dùng, chỉ để giữ signature)
        
    Returns:
        String format SQL: ttt_5_l9, ttt_5_l11, ..., ttt_5_l25
    """
    tables = []
    
    # Lấy tất cả các level lẻ từ 9 đến 25
    for level in range(9, 26, 2):  # 9, 11, 13, ..., 25
        tables.append(f"ttt_5_l{level}")
    
    return ", ".join(tables)


def get_even_table_names(move_count: int) -> str:
    """
    Lấy danh sách tên bảng even (lượt chẵn)
    
    Args:
        move_count: Số nước đã đi (không dùng, chỉ để giữ signature)
        
    Returns:
        String format SQL: ttt_5_l10, ttt_5_l12, ..., ttt_5_l24
    """
    tables = []
    
    # Lấy tất cả các level chẵn từ 10 đến 24
    for level in range(10, 25, 2):  # 10, 12, 14, ..., 24
        tables.append(f"ttt_5_l{level}")
    
    return ", ".join(tables)


def build_where_clause(board: list) -> str:
    """
    Xây dựng WHERE clause từ board
    
    Args:
        board: Board hiện tại
        
    Returns:
        WHERE clause string
    """
    n = 5
    conditions = []
    
    for idx, cell in enumerate(board):
        if cell != 0:
            row = (idx // n) + 1  # +1 vì index bắt đầu từ 1
            col = (idx % n) + 1
            col_name = f"i{row}{col}"
            player_mark = 'X' if cell == 1 else 'O'
            conditions.append(f"{col_name} = '{player_mark}'")
    
    return " AND ".join(conditions) if conditions else "1=1"


def query_odd_table(board: list) -> int:
    """
    Query bảng odd (lượt lẻ) - đếm số trận X thắng
    
    Args:
        board: Bảng hiện tại (list of int, size 25)
        
    Returns:
        Số lượng rows có win_actor = 'X'
    """
    move_count = sum(1 for cell in board if cell != 0)
    
    if move_count == 0:
        return 0
    
    where_clause = build_where_clause(board)
    
    # Đếm trực tiếp từng bảng và cộng lại
    total_count = 0
    for level in range(9, 26, 2):  # 9, 11, 13, ..., 25
        if level < move_count:
            continue
        
        table_name = f"ttt_5_l{level}"
        sql = f"SELECT COUNT(win_actor) FROM {table_name} WHERE {where_clause} AND win_actor = 'X'"
        
        count = execute_query(sql)
        total_count += count
    
    return total_count


def query_even_table(board: list) -> int:
    """
    Query bảng even (lượt chẵn) - đếm số trận O thắng
    
    Args:
        board: Bảng hiện tại (list of int, size 25)
        
    Returns:
        Số lượng rows có win_actor = 'O'
    """
    move_count = sum(1 for cell in board if cell != 0)
    
    if move_count == 0:
        return 0
    
    where_clause = build_where_clause(board)
    
    # Đếm trực tiếp từng bảng và cộng lại
    total_count = 0
    for level in range(10, 25, 2):  # 10, 12, 14, ..., 24
        if level < move_count:
            continue
        
        table_name = f"ttt_5_l{level}"
        sql = f"SELECT COUNT(win_actor) FROM {table_name} WHERE {where_clause} AND win_actor = 'O'"
        
        count = execute_query(sql)
        total_count += count
    
    return total_count


def query_draw_table(board: list) -> int:
    """
    Query bảng draw (ttt_5_draw) - đếm số trận hòa
    
    Args:
        board: Bảng hiện tại (list of int, size 25)
        
    Returns:
        Số lượng rows có win_actor = 'D'
    """
    move_count = sum(1 for cell in board if cell != 0)
    
    if move_count == 0:
        return 0
    
    where_clause = build_where_clause(board)
    
    # Query table ttt_5_draw
    sql = f"SELECT COUNT(win_actor) FROM ttt_5_draw WHERE {where_clause} AND win_actor = 'D'"
    
    return execute_query(sql)

#=========================================Symmetric==========================================
N = 5  # Board size constant

# Transformation functions
def t_identity(r, c):
    return (r, c)

def t_rot90(r, c):
    return (c, N-1-r)

def t_rot180(r, c):
    return (N-1-r, N-1-c)

def t_rot270(r, c):
    return (N-1-c, r)

def t_reflect_h(r, c):
    return (N-1-r, c)

def t_reflect_v(r, c):
    return (r, N-1-c)

def t_reflect_main(r, c):
    return (c, r)

def t_reflect_anti(r, c):
    return (N-1-c, N-1-r)


def apply_transformation(board: list, transform_func) -> list:
    """
    Áp dụng transformation function lên board
    
    Args:
        board: Board 1D (25 elements)
        transform_func: Hàm transformation (r,c) -> (r',c')
        
    Returns:
        Board mới sau khi transform
    """
    n = N
    new_board = [0] * (n * n)
    
    for idx in range(n * n):
        r = idx // n
        c = idx % n
        
        # Apply transformation
        new_r, new_c = transform_func(r, c)
        new_idx = new_r * n + new_c
        
        new_board[new_idx] = board[idx]
    
    return new_board


def get_symmetries(board: list) -> list:
    """
    Tạo tất cả các phép biến đổi đối xứng của board 5x5
    Dùng cùng transformations như lúc gen data
    
    Args:
        board: Board hiện tại (list 25 elements)
        
    Returns:
        List các board đối xứng (8 biến đổi)
    """
    transformations = [
        t_identity,
        t_rot90,
        t_rot180,
        t_rot270,
        t_reflect_h,
        t_reflect_v,
        t_reflect_main,
        t_reflect_anti
    ]
    
    symmetries = []
    for transform in transformations:
        sym_board = apply_transformation(board, transform)
        symmetries.append(sym_board)
    
    return symmetries


def canonical_board(board: list) -> list:
    """
    Tìm canonical form của board (form nhỏ nhất theo lexicographic order)
    Giống như lúc gen data
    
    Args:
        board: Board hiện tại
        
    Returns:
        Canonical board
    """
    symmetries = get_symmetries(board)
    
    # Convert to tuples for comparison
    sym_tuples = [tuple(sym) for sym in symmetries]
    
    # Return the lexicographically smallest
    return list(min(sym_tuples))

#=========================================5x5 Logic==========================================
def get_steps_with_rate(currBoard: list[list[int]], player: int) -> list[list[list[int]]]:
    """
    Tìm nước đi tốt nhất cho AI dựa trên database
    
    Args:
        currBoard: Board hiện tại (2D array 5x5)
        player: Player hiện tại (1 hoặc 2)
        
    Returns:
        3D array [5][5][4] với [win_count, lose_count, draw_count, total_count]
    """
    # Log số ô trống
    empty_cells = sum(1 for cell in currBoard if cell == 0)
    print(f"\n🤔 AI đang suy nghĩ... (Còn {empty_cells} ô trống)")

    steps_with_rate = [[[] for _ in range(5)] for _ in range(5)]

    for r in range(5):
        for c in range(5):
            if currBoard[r][c] != 0:
                continue

            newBoard = copy.deepcopy(currBoard)
            newBoard[r][c] = player

            # Convert 2D -> 1D trước khi gọi canonical
            newBoard_1d = board_2d_to_1d(newBoard)
            canonical = canonical_board(newBoard_1d)
            
            # Query với canonical form
            x_win_count = query_odd_table(canonical)
            o_win_count = query_even_table(canonical)
            draw_count = query_draw_table(canonical)
            
            total_count = x_win_count + o_win_count + draw_count
            
            if total_count <= 0:
                steps_with_rate[r][c] = [0.0, 0.0, 0.0, 0.0]
                continue
            
            # Tính win rate và lose rate cho player hiện tại
            win_count = x_win_count if player == 1 else o_win_count
            lose_count = o_win_count if player == 1 else x_win_count
            steps_with_rate[r][c] = [win_count, lose_count, draw_count, total_count]
    
    return steps_with_rate

#===================================Unlimited Space logic====================================
BOARD_SIZE = 15

def best_steps_unlimited(currBoard: list[list[int]], player: int, last_move_col: int, last_move_row: int) -> tuple[int, int]:
    """Tìm nước đi tốt nhất cho AI trong unlimited space"""
    
    col_index = get_col_index_5_x_5(last_move_col)
    row_index = get_row_index_5_x_5(last_move_row)

    # Identify 5x5 checking area
    col_min = last_move_col - 2 + col_index
    col_max = last_move_col + 2 + col_index
    row_min = last_move_row - 2 + row_index
    row_max = last_move_row + 2 + row_index

    # Accumulate counts cho mỗi ô trống
    board_accumulated = {}  # ✅ Dùng dictionary với tuple key
    
    for r in range(row_min, row_max + 1):
        for c in range(col_min, col_max + 1):
            if currBoard[r][c] != player:
                continue
            
            # Lấy board 5x5 xung quanh vị trí player này
            board_1d = get_board_5_x_5(currBoard, r, c)
            board_2d = board_1d_to_2d(board_1d)
            
            steps_with_rate = get_steps_with_rate(board_2d, player)
            
            # Map local 5x5 coordinates về global
            p_col_index = get_col_index_5_x_5(c)
            p_row_index = get_row_index_5_x_5(r)
            
            for local_r in range(5):
                for local_c in range(5):
                    global_r = r - 2 + p_row_index + local_r
                    global_c = c - 2 + p_col_index + local_c
                    
                    # ✅ Chỉ accumulate ô trống
                    if currBoard[global_r][global_c] != 0:
                        continue
                    
                    rates = steps_with_rate[local_r][local_c]
                    
                    # ✅ Dùng tuple key đúng format
                    if (global_r, global_c) not in board_accumulated:
                        board_accumulated[(global_r, global_c)] = [0, 0, 0, 0]
                    
                    board_accumulated[(global_r, global_c)][0] += rates[0]
                    board_accumulated[(global_r, global_c)][1] += rates[1]
                    board_accumulated[(global_r, global_c)][2] += rates[2]
                    board_accumulated[(global_r, global_c)][3] += rates[3]
    
    # ✅ Check empty
    if not board_accumulated:
        return (-1, -1)
    
    # ✅ Tính rates SAU KHI thoát khỏi loop (indent đúng)
    board_rate = {}
    for (r, c), counts in board_accumulated.items():
        total = counts[3]
        
        # ✅ Avoid division by zero
        if total == 0:
            continue
        
        win_rate = counts[0] / total
        lose_rate = counts[1] / total
        board_rate[(r, c)] = [win_rate, lose_rate]
    
    # ✅ Check nếu không có valid moves
    if not board_rate:
        return (-1, -1)

    # Tìm best move
    best_column = -1
    best_row = -1
    best_win_rate = -1.0
    least_lose_rate = float('inf')

    for (r, c), rates in board_rate.items():
        win_rate = rates[0]
        lose_rate = rates[1]

        if win_rate > best_win_rate:
            best_win_rate = win_rate
            least_lose_rate = lose_rate
            best_column = c
            best_row = r
        elif win_rate == best_win_rate and lose_rate < least_lose_rate:
            least_lose_rate = lose_rate
            best_column = c
            best_row = r

    return (best_row, best_column)

#=========================================Conversion Functions==========================================
def board_2d_to_1d(board_2d: list[list[int]]) -> list[int]:
    """
    Convert board 2D (5x5) sang 1D (25 elements)
    
    Args:
        board_2d: Board 2D array [[...], [...], ...]
        
    Returns:
        Board 1D array [...]
    """
    return [cell for row in board_2d for cell in row]


def board_1d_to_2d(board_1d: list[int]) -> list[list[int]]:
    """
    Convert board 1D (25 elements) sang 2D (5x5)
    
    Args:
        board_1d: Board 1D array [...]
        
    Returns:
        Board 2D array [[...], [...], ...]
    """
    return [board_1d[i:i+5] for i in range(0, 25, 5)]

#==========================================Support===========================================
def get_board_5_x_5(currBoard: list[list[int]], center_row: int, center_col: int) -> list:
    col_index = get_col_index_5_x_5(center_col)
    row_index = get_row_index_5_x_5(center_row)
    result = [0] * 25

    for c in range(center_col - 2 + col_index, center_col + 2 + col_index + 1):
        for r in range(center_row - 2 + row_index, center_row + 2 + row_index + 1):
            board_5_x_5_index = (r - (center_row - 2 + row_index)) * 5 + (c - (center_col - 2 + col_index))
            result[board_5_x_5_index] = currBoard[r][c]

    return result

def get_col_index_5_x_5(last_move_col: int) -> int:
    # col limit (board edge)
    col_index = 0
    if last_move_col > BOARD_SIZE - 3:
        col_index = last_move_col - BOARD_SIZE
    elif last_move_col < 0:
        col_index = -1 * (2 - last_move_col)

    return col_index
    
def get_row_index_5_x_5(last_move_row: int) -> int:
    # row limit (board edge)
    row_index = 0
    if last_move_row > BOARD_SIZE - 3:
        row_index = last_move_row - BOARD_SIZE
    elif last_move_row < 0:
        row_index = -1 * (2 - last_move_row)

    return row_index


#==========================================Game Logic với Flask==========================================
app = Flask(__name__)

# Global game state
game_state = {
    'board': [[0 for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)],
    'current_player': 1,
    'last_move': [BOARD_SIZE // 2, BOARD_SIZE // 2],
    'move_count': 0,
    'winner': 0,
    'game_over': False
}


def check_winner_5_in_row(board: list[list[int]], row: int, col: int) -> int:
    """Kiểm tra xem có người thắng không (5 ô liên tiếp)"""
    player = board[row][col]
    if player == 0:
        return 0
    
    directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
    
    for dr, dc in directions:
        count = 1
        
        r, c = row + dr, col + dc
        while 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE and board[r][c] == player:
            count += 1
            r += dr
            c += dc
        
        r, c = row - dr, col - dc
        while 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE and board[r][c] == player:
            count += 1
            r -= dr
            c -= dc
        
        if count >= 5:
            return player
    
    return 0


@app.route('/')
def index():
    """Trang chủ game"""
    return render_template('index.html', board_size=BOARD_SIZE)


@app.route('/api/game/state', methods=['GET'])
def get_game_state():
    """Lấy trạng thái game hiện tại"""
    return jsonify(game_state)


@app.route('/api/game/reset', methods=['POST'])
def reset_game():
    """Reset game về trạng thái ban đầu"""
    global game_state
    
    game_state = {
        'board': [[0 for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)],
        'current_player': 1,  # Human đi đầu
        'last_move': [BOARD_SIZE // 2, BOARD_SIZE // 2],
        'move_count': 0,
        'winner': 0,
        'game_over': False
    }
    
    return jsonify(game_state)


@app.route('/api/game/move', methods=['POST'])
def make_move():
    """Thực hiện nước đi của player"""
    global game_state
    
    data = request.json
    row = data.get('row')
    col = data.get('col')
    
    if game_state['game_over']:
        return jsonify({'error': 'Game is over'}), 400
    
    if game_state['current_player'] != 1:
        return jsonify({'error': 'Not your turn'}), 400
    
    if not (0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE):
        return jsonify({'error': 'Invalid position'}), 400
    
    if game_state['board'][row][col] != 0:
        return jsonify({'error': 'Position occupied'}), 400
    
    game_state['board'][row][col] = 1
    game_state['last_move'] = [row, col]
    game_state['move_count'] += 1
    
    winner = check_winner_5_in_row(game_state['board'], row, col)
    if winner != 0:
        game_state['winner'] = winner
        game_state['game_over'] = True
        return jsonify(game_state)
    
    game_state['current_player'] = 2
    
    # AI move
    ai_row, ai_col = best_steps_unlimited(
        game_state['board'], 
        2, 
        game_state['last_move'][1], 
        game_state['last_move'][0]
    )
    
    if ai_row == -1 or ai_col == -1:
        import random
        attempts = 0
        while attempts < 100:
            ai_row = game_state['last_move'][0] + random.randint(-3, 3)
            ai_col = game_state['last_move'][1] + random.randint(-3, 3)
            if (0 <= ai_row < BOARD_SIZE and 
                0 <= ai_col < BOARD_SIZE and 
                game_state['board'][ai_row][ai_col] == 0):
                break
            attempts += 1
        
        if attempts >= 100:
            game_state['game_over'] = True
            return jsonify(game_state)
    
    game_state['board'][ai_row][ai_col] = 2
    game_state['last_move'] = [ai_row, ai_col]
    game_state['move_count'] += 1
    
    winner = check_winner_5_in_row(game_state['board'], ai_row, ai_col)
    if winner != 0:
        game_state['winner'] = winner
        game_state['game_over'] = True
        return jsonify(game_state)
    
    if game_state['move_count'] >= BOARD_SIZE * BOARD_SIZE:
        game_state['game_over'] = True
    
    game_state['current_player'] = 1
    
    return jsonify(game_state)


if __name__ == "__main__":
    # Khởi tạo game với board trống, Human đi đầu
    game_state['current_player'] = 1  # Human đi đầu tiên
    game_state['last_move'] = [BOARD_SIZE // 2, BOARD_SIZE // 2]
    
    print("🎮 Starting Tic-Tac-Toe Game Server...")
    print("=" * 60)
    print(f"Board Size: {BOARD_SIZE}x{BOARD_SIZE}")
    print("Win Condition: 5 in a row")
    print("Player 1 (X): Human - YOU GO FIRST!")
    print("Player 2 (O): AI")
    print("=" * 60)
    print("\n🌐 Open browser: http://localhost:5000")
    print("=" * 60)
    
    app.run(debug=True, host='0.0.0.0', port=5000)