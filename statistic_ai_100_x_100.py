import requests
import numpy as np
import copy
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

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
def get_best_step_5x5(currBoard: list[list[int]], player: int, glob_r: int, glob_c: int):
    """
    Tìm nước đi tốt nhất cho AI dựa trên database
    
    Args:
        currBoard: Board hiện tại (2D array 5x5)
        player: Player hiện tại (1 hoặc 2)
        
    Returns:
        3D array [5][5][3] với [win_rate, lose_rate, draw_rate]
    """

    best_move = (-1, -1)
    win_rate = 0
    lose_rate = 1.0  # Khởi tạo = 1.0 để tìm min
    best_move_by_lose = -1

    # Log số ô trống
    empty_cells = sum(1 for cell in currBoard if cell == 0)
    print(f"\n🤔 AI đang suy nghĩ...")

    moves_checked = 0
    moves_with_data = 0

    for c in range(5):
        for r in range(5):
            if currBoard[r][c] != 0:
                continue
            
            # Tìm canonical form
            newBoard = copy.deepcopy(currBoard)
            newBoard[r][c] = player
            board_1d = convert_to_db_schema_1d(newBoard)
            canonical = canonical_board(board_1d)
            
            # Query với canonical form
            x_win_count = query_odd_table(canonical)
            o_win_count = query_even_table(canonical)
            draw_count = query_draw_table(canonical)
            
            total_count = x_win_count + o_win_count + draw_count
            
            if total_count <= 0:
                continue
        
            moves_with_data += 1
            
            # Tính win rate và lose rate cho player hiện tại
            win_count = x_win_count if player == 1 else o_win_count
            lose_count = o_win_count if player == 1 else x_win_count

            # Tính win rate và lose rate cho player hiện tại
            current_win_rate = win_count / total_count
            current_lose_rate = lose_count / total_count
            draw_rate = draw_count / total_count

            if current_win_rate > win_rate:
                win_rate = current_win_rate
                best_move = (r + glob_r - 2, c + glob_c - 2)

            if current_lose_rate > lose_rate:
                lose_rate = current_lose_rate
            
            # Log chi tiết
            print(f"  Ô [{r + glob_c - 2},{c + glob_r - 2}]): "
                f"win={current_win_rate:.2%}, lose={current_lose_rate:.2%}, draw={draw_rate:.2%} "
                f"(X:{x_win_count}, O:{o_win_count}, D:{draw_count}, total:{total_count})")
            
    # Nếu không tìm thấy nước thắng, chọn nước ít thua nhất
    if best_move == (-1, -1):
        best_move = best_move_by_lose
    
    return best_move

#============================================================================================
#====================================Board Priority Data=====================================
#============================================================================================

#==========================================X Format - ROW 1==========================================
ROW_X_1_H1_1_PRIORITY = 0
ROW_X_1_H1_2_PRIORITY = 0.5
ROW_X_1_H1_3_PRIORITY = 1 * 2
ROW_X_1_H1_4_PRIORITY = 0.5
ROW_X_1_H1_5_PRIORITY = 0

ROW_X_1_H2_1_PRIORITY = 0.5
ROW_X_1_H2_2_PRIORITY = 1
ROW_X_1_H2_3_PRIORITY = 1.5
ROW_X_1_H2_4_PRIORITY = 1
ROW_X_1_H2_5_PRIORITY = 0.5

ROW_X_1_H3_1_PRIORITY = 1
ROW_X_1_H3_2_PRIORITY = 1.5
ROW_X_1_H3_3_PRIORITY = 2 * 2
ROW_X_1_H3_4_PRIORITY = 1.5
ROW_X_1_H3_5_PRIORITY = 1

ROW_X_1_D1_1_PRIORITY = 0
ROW_X_1_D1_2_PRIORITY = 1
ROW_X_1_D1_3_PRIORITY = 2 * 2
ROW_X_1_D1_4_PRIORITY = 1
ROW_X_1_D1_5_PRIORITY = 0

ROW_O_1_H1_1_PRIORITY = 0
ROW_O_1_H1_2_PRIORITY = 0.5
ROW_O_1_H1_3_PRIORITY = 1 * 2
ROW_O_1_H1_4_PRIORITY = 0.5
ROW_O_1_H1_5_PRIORITY = 0

ROW_O_1_H2_1_PRIORITY = 0.5
ROW_O_1_H2_2_PRIORITY = 1
ROW_O_1_H2_3_PRIORITY = 1.5 * 2
ROW_O_1_H2_4_PRIORITY = 1
ROW_O_1_H2_5_PRIORITY = 0.5

ROW_O_1_H3_1_PRIORITY = 1
ROW_O_1_H3_2_PRIORITY = 1.5
ROW_O_1_H3_3_PRIORITY = 2 * 2
ROW_O_1_H3_4_PRIORITY = 1.5
ROW_O_1_H3_5_PRIORITY = 1

ROW_O_1_D1_1_PRIORITY = 0
ROW_O_1_D1_2_PRIORITY = 1
ROW_O_1_D1_3_PRIORITY = 2 * 2
ROW_O_1_D1_4_PRIORITY = 1
ROW_O_1_D1_5_PRIORITY = 0


#==========================================X Format - ROW 2==========================================
ROW_X_2_H1_1_PRIORITY = 5
ROW_X_2_H1_2_PRIORITY = 5
ROW_X_2_H1_3_PRIORITY = 5
ROW_X_2_H1_4_PRIORITY = 6
ROW_X_2_H1_5_PRIORITY = 5
ROW_X_2_H1_6_PRIORITY = 5
ROW_X_2_H1_7_PRIORITY = 5
ROW_X_2_H1_8_PRIORITY = 6
ROW_X_2_H1_9_PRIORITY = 6 * 2

ROW_X_2_H2_1_PRIORITY = 5
ROW_X_2_H2_2_PRIORITY = 5
ROW_X_2_H2_3_PRIORITY = 5
ROW_X_2_H2_4_PRIORITY = 6
ROW_X_2_H2_5_PRIORITY = 5
ROW_X_2_H2_6_PRIORITY = 5
ROW_X_2_H2_7_PRIORITY = 5
ROW_X_2_H2_8_PRIORITY = 6
ROW_X_2_H2_9_PRIORITY = 6 * 2

ROW_X_2_H3_1_PRIORITY = 14
ROW_X_2_H3_2_PRIORITY = 14
ROW_X_2_H3_3_PRIORITY = 14
ROW_X_2_H3_4_PRIORITY = 15
ROW_X_2_H3_5_PRIORITY = 14
ROW_X_2_H3_6_PRIORITY = 14
ROW_X_2_H3_7_PRIORITY = 14
ROW_X_2_H3_8_PRIORITY = 15
ROW_X_2_H3_9_PRIORITY = 15 * 2

ROW_X_2_D1_1_PRIORITY = 14
ROW_X_2_D1_2_PRIORITY = 14
ROW_X_2_D1_3_PRIORITY = 14
ROW_X_2_D1_4_PRIORITY = 15
ROW_X_2_D1_5_PRIORITY = 14
ROW_X_2_D1_6_PRIORITY = 14
ROW_X_2_D1_7_PRIORITY = 14
ROW_X_2_D1_8_PRIORITY = 15
ROW_X_2_D1_9_PRIORITY = 15 * 2

#==========================================X Format - ROW 3==========================================
ROW_X_3_H1_1_PRIORITY = 30
ROW_X_3_H1_2_PRIORITY = 30
ROW_X_3_H1_3_PRIORITY = 30
ROW_X_3_H1_4_PRIORITY = 31
ROW_X_3_H1_5_PRIORITY = 30
ROW_X_3_H1_6_PRIORITY = 31
ROW_X_3_H1_7_PRIORITY = 31 * 2

ROW_X_3_H2_1_PRIORITY = 40
ROW_X_3_H2_2_PRIORITY = 40
ROW_X_3_H2_3_PRIORITY = 40
ROW_X_3_H2_4_PRIORITY = 41
ROW_X_3_H2_5_PRIORITY = 40
ROW_X_3_H2_6_PRIORITY = 41
ROW_X_3_H2_7_PRIORITY = 41 * 2

ROW_X_3_H3_1_PRIORITY = 50
ROW_X_3_H3_2_PRIORITY = 50
ROW_X_3_H3_3_PRIORITY = 50
ROW_X_3_H3_4_PRIORITY = 51
ROW_X_3_H3_5_PRIORITY = 50
ROW_X_3_H3_6_PRIORITY = 51
ROW_X_3_H3_7_PRIORITY = 51 * 2

ROW_X_3_D1_1_PRIORITY = 50
ROW_X_3_D1_2_PRIORITY = 50
ROW_X_3_D1_3_PRIORITY = 50
ROW_X_3_D1_4_PRIORITY = 51
ROW_X_3_D1_5_PRIORITY = 50
ROW_X_3_D1_6_PRIORITY = 51
ROW_X_3_D1_7_PRIORITY = 51 * 2

#==========================================X Format - ROW 4==========================================
ROW_X_4_H1_1_PRIORITY = 4000
ROW_X_4_H1_2_PRIORITY = 4000
ROW_X_4_H1_3_PRIORITY = 4001 * 2
ROW_X_4_H1_4_PRIORITY = 4000
ROW_X_4_H1_5_PRIORITY = 4000

ROW_X_4_H2_1_PRIORITY = 5000
ROW_X_4_H2_2_PRIORITY = 5000
ROW_X_4_H2_3_PRIORITY = 5001 * 2
ROW_X_4_H2_4_PRIORITY = 5000
ROW_X_4_H2_5_PRIORITY = 5000

ROW_X_4_H3_1_PRIORITY = 6000
ROW_X_4_H3_2_PRIORITY = 6000
ROW_X_4_H3_3_PRIORITY = 6001 * 2
ROW_X_4_H3_4_PRIORITY = 6000
ROW_X_4_H3_5_PRIORITY = 6000

ROW_X_4_D1_1_PRIORITY = 6000
ROW_X_4_D1_2_PRIORITY = 6000
ROW_X_4_D1_3_PRIORITY = 6001 * 2
ROW_X_4_D1_4_PRIORITY = 6000
ROW_X_4_D1_5_PRIORITY = 6000

#==========================================O Format - ROW 2==========================================
ROW_O_2_H1_1_PRIORITY = 15
ROW_O_2_H1_2_PRIORITY = 15
ROW_O_2_H1_3_PRIORITY = 15
ROW_O_2_H1_4_PRIORITY = 16
ROW_O_2_H1_5_PRIORITY = 15
ROW_O_2_H1_6_PRIORITY = 15
ROW_O_2_H1_7_PRIORITY = 15
ROW_O_2_H1_8_PRIORITY = 16
ROW_O_2_H1_9_PRIORITY = 16 * 2

ROW_O_2_H2_1_PRIORITY = 25
ROW_O_2_H2_2_PRIORITY = 25
ROW_O_2_H2_3_PRIORITY = 25
ROW_O_2_H2_4_PRIORITY = 26
ROW_O_2_H2_5_PRIORITY = 25
ROW_O_2_H2_6_PRIORITY = 25
ROW_O_2_H2_7_PRIORITY = 25
ROW_O_2_H2_8_PRIORITY = 26
ROW_O_2_H2_9_PRIORITY = 26 * 2

ROW_O_2_H3_1_PRIORITY = 35
ROW_O_2_H3_2_PRIORITY = 35
ROW_O_2_H3_3_PRIORITY = 35
ROW_O_2_H3_4_PRIORITY = 36
ROW_O_2_H3_5_PRIORITY = 35
ROW_O_2_H3_6_PRIORITY = 35
ROW_O_2_H3_7_PRIORITY = 35
ROW_O_2_H3_8_PRIORITY = 36
ROW_O_2_H3_9_PRIORITY = 36 * 2

ROW_O_2_D1_1_PRIORITY = 35
ROW_O_2_D1_2_PRIORITY = 35
ROW_O_2_D1_3_PRIORITY = 35
ROW_O_2_D1_4_PRIORITY = 36
ROW_O_2_D1_5_PRIORITY = 35
ROW_O_2_D1_6_PRIORITY = 35
ROW_O_2_D1_7_PRIORITY = 35
ROW_O_2_D1_8_PRIORITY = 36
ROW_O_2_D1_9_PRIORITY = 36 * 2

#==========================================O Format - ROW 3==========================================
ROW_O_3_H1_1_PRIORITY = 90
ROW_O_3_H1_2_PRIORITY = 90
ROW_O_3_H1_3_PRIORITY = 90
ROW_O_3_H1_4_PRIORITY = 91
ROW_O_3_H1_5_PRIORITY = 90
ROW_O_3_H1_6_PRIORITY = 91
ROW_O_3_H1_7_PRIORITY = 91 * 2

ROW_O_3_H2_1_PRIORITY = 100
ROW_O_3_H2_2_PRIORITY = 100
ROW_O_3_H2_3_PRIORITY = 100
ROW_O_3_H2_4_PRIORITY = 101
ROW_O_3_H2_5_PRIORITY = 100
ROW_O_3_H2_6_PRIORITY = 101
ROW_O_3_H2_7_PRIORITY = 101 * 2

ROW_O_3_H3_1_PRIORITY = 110
ROW_O_3_H3_2_PRIORITY = 110
ROW_O_3_H3_3_PRIORITY = 110
ROW_O_3_H3_4_PRIORITY = 111
ROW_O_3_H3_5_PRIORITY = 110
ROW_O_3_H3_6_PRIORITY = 111
ROW_O_3_H3_7_PRIORITY = 111 * 2

ROW_O_3_D1_1_PRIORITY = 110
ROW_O_3_D1_2_PRIORITY = 110
ROW_O_3_D1_3_PRIORITY = 110
ROW_O_3_D1_4_PRIORITY = 111
ROW_O_3_D1_5_PRIORITY = 110
ROW_O_3_D1_6_PRIORITY = 111
ROW_O_3_D1_7_PRIORITY = 111 * 2

#==========================================O Format - ROW 4==========================================
ROW_O_4_H1_1_PRIORITY = 900
ROW_O_4_H1_2_PRIORITY = 900
ROW_O_4_H1_3_PRIORITY = 901 * 2
ROW_O_4_H1_4_PRIORITY = 900
ROW_O_4_H1_5_PRIORITY = 900

ROW_O_4_H2_1_PRIORITY = 1000
ROW_O_4_H2_2_PRIORITY = 1000
ROW_O_4_H2_3_PRIORITY = 1001 * 2
ROW_O_4_H2_4_PRIORITY = 1000
ROW_O_4_H2_5_PRIORITY = 1000

ROW_O_4_H3_1_PRIORITY = 1100
ROW_O_4_H3_2_PRIORITY = 1100
ROW_O_4_H3_3_PRIORITY = 1101 * 2
ROW_O_4_H3_4_PRIORITY = 1100
ROW_O_4_H3_5_PRIORITY = 1100

ROW_O_4_D1_1_PRIORITY = 1100
ROW_O_4_D1_2_PRIORITY = 1100
ROW_O_4_D1_3_PRIORITY = 1101 * 2
ROW_O_4_D1_4_PRIORITY = 1100
ROW_O_4_D1_5_PRIORITY = 1100


#============================================================================================
#====================================Board Pattern Cases=====================================
#============================================================================================

#==========================================X Format - ROW 1 - H1==========================================
ROW_X_1_H1_1 = [1, 3, 3, 3, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_1_H1_2 = [3, 1, 3, 3, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_1_H1_3 = [3, 3, 1, 3, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_1_H1_4 = [3, 3, 3, 1, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_1_H1_5 = [3, 3, 3, 3, 1,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

#==========================================X Format - ROW 1 - H2==========================================
ROW_X_1_H2_1 = [0, 0, 0, 0, 0,
                1, 3, 3, 3, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_1_H2_2 = [0, 0, 0, 0, 0,
                3, 1, 3, 3, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_1_H2_3 = [0, 0, 0, 0, 0,
                3, 3, 1, 3, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_1_H2_4 = [0, 0, 0, 0, 0,
                3, 3, 3, 1, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_1_H2_5 = [0, 0, 0, 0, 0,
                3, 3, 3, 3, 1,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

#==========================================X Format - ROW 1 - H3==========================================
ROW_X_1_H3_1 = [0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                1, 3, 3, 3, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_1_H3_2 = [0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                3, 1, 3, 3, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_1_H3_3 = [0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                3, 3, 1, 3, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_1_H3_4 = [0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                3, 3, 3, 1, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_1_H3_5 = [0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                3, 3, 3, 3, 1,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

#==========================================X Format - ROW 1 - D1==========================================
ROW_X_1_D1_1 = [1, 0, 0, 0, 0,
                0, 3, 0, 0, 0,
                0, 0, 3, 0, 0,
                0, 0, 0, 3, 0,
                0, 0, 0, 0, 3]

ROW_X_1_D1_2 = [3, 0, 0, 0, 0,
                0, 1, 0, 0, 0,
                0, 0, 3, 0, 0,
                0, 0, 0, 3, 0,
                0, 0, 0, 0, 3]

ROW_X_1_D1_3 = [3, 0, 0, 0, 0,
                0, 3, 0, 0, 0,
                0, 0, 1, 0, 0,
                0, 0, 0, 3, 0,
                0, 0, 0, 0, 3]

ROW_X_1_D1_4 = [3, 0, 0, 0, 0,
                0, 3, 0, 0, 0,
                0, 0, 3, 0, 0,
                0, 0, 0, 1, 0,
                0, 0, 0, 0, 3]

ROW_X_1_D1_5 = [3, 0, 0, 0, 0,
                0, 3, 0, 0, 0,
                0, 0, 3, 0, 0,
                0, 0, 0, 3, 0,
                0, 0, 0, 0, 1]

#==========================================O Format - ROW 1 - H1==========================================
ROW_O_1_H1_1 = [2, 3, 3, 3, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_1_H1_2 = [3, 2, 3, 3, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_1_H1_3 = [3, 3, 2, 3, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_1_H1_4 = [3, 3, 3, 2, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_1_H1_5 = [3, 3, 3, 3, 2,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

#==========================================O Format - ROW 1 - H2==========================================
ROW_O_1_H2_1 = [0, 0, 0, 0, 0,
                2, 3, 3, 3, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_1_H2_2 = [0, 0, 0, 0, 0,
                3, 2, 3, 3, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_1_H2_3 = [0, 0, 0, 0, 0,
                3, 3, 2, 3, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_1_H2_4 = [0, 0, 0, 0, 0,
                3, 3, 3, 2, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_1_H2_5 = [0, 0, 0, 0, 0,
                3, 3, 3, 3, 2,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

#==========================================O Format - ROW 1 - H3==========================================
ROW_O_1_H3_1 = [0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                2, 3, 3, 3, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_1_H3_2 = [0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                3, 2, 3, 3, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_1_H3_3 = [0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                3, 3, 2, 3, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_1_H3_4 = [0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                3, 3, 3, 2, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_1_H3_5 = [0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                3, 3, 3, 3, 2,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

#==========================================O Format - ROW 1 - D1==========================================
ROW_O_1_D1_1 = [2, 0, 0, 0, 0,
                0, 3, 0, 0, 0,
                0, 0, 3, 0, 0,
                0, 0, 0, 3, 0,
                0, 0, 0, 0, 3]

ROW_O_1_D1_2 = [3, 0, 0, 0, 0,
                0, 2, 0, 0, 0,
                0, 0, 3, 0, 0,
                0, 0, 0, 3, 0,
                0, 0, 0, 0, 3]

ROW_O_1_D1_3 = [3, 0, 0, 0, 0,
                0, 3, 0, 0, 0,
                0, 0, 2, 0, 0,
                0, 0, 0, 3, 0,
                0, 0, 0, 0, 3]

ROW_O_1_D1_4 = [3, 0, 0, 0, 0,
                0, 3, 0, 0, 0,
                0, 0, 3, 0, 0,
                0, 0, 0, 2, 0,
                0, 0, 0, 0, 3]

ROW_O_1_D1_5 = [3, 0, 0, 0, 0,
                0, 3, 0, 0, 0,
                0, 0, 3, 0, 0,
                0, 0, 0, 3, 0,
                0, 0, 0, 0, 2]

#==========================================X Format - ROW 2 - H1==========================================
ROW_X_2_H1_1 = [1, 1, 3, 3, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_2_H1_2 = [1, 3, 1, 3, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_2_H1_3 = [1, 3, 3, 1, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_2_H1_4 = [3, 1, 1, 3, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_2_H1_5 = [3, 3, 3, 1, 1,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_2_H1_6 = [3, 3, 1, 3, 1,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_2_H1_7 = [3, 1, 3, 3, 1,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_2_H1_8 = [3, 3, 1, 1, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_2_H1_9 = [3, 1, 3, 1, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

#==========================================X Format - ROW 2 - H2==========================================
ROW_X_2_H2_1 = [0, 0, 0, 0, 0,
                1, 1, 3, 3, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]
ROW_X_2_H2_2 = [0, 0, 0, 0, 0,
                1, 3, 1, 3, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]
ROW_X_2_H2_3 = [0, 0, 0, 0, 0,
                1, 3, 3, 1, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]
ROW_X_2_H2_4 = [0, 0, 0, 0, 0,
                3, 1, 1, 3, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]
ROW_X_2_H2_5 = [0, 0, 0, 0, 0,
                3, 3, 3, 1, 1,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]
ROW_X_2_H2_6 = [0, 0, 0, 0, 0,
                3, 3, 1, 3, 1,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]
ROW_X_2_H2_7 = [0, 0, 0, 0, 0,
                3, 1, 3, 3, 1,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]
ROW_X_2_H2_8 = [0, 0, 0, 0, 0,
                3, 3, 1, 1, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]
ROW_X_2_H2_9 = [0, 0, 0, 0, 0,
                3, 1, 3, 1, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]
#==========================================X Format - ROW 2 - H3==========================================
ROW_X_2_H3_1 = [0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                1, 1, 3, 3, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_2_H3_2 = [0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                1, 3, 1, 3, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_2_H3_3 = [0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                1, 3, 3, 1, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_2_H3_4 = [0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                3, 1, 1, 3, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_2_H3_5 = [0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                3, 3, 3, 1, 1,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_2_H3_6 = [0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                3, 3, 1, 3, 1,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_2_H3_7 = [0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                3, 1, 3, 3, 1,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_2_H3_8 = [0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                3, 3, 1, 1, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_2_H3_9 = [0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                3, 1, 3, 1, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

#==========================================X Format - ROW 2 - D1==========================================
ROW_X_2_D1_1 = [1, 0, 0, 0, 0,
                0, 1, 0, 0, 0,
                0, 0, 3, 0, 0,
                0, 0, 0, 3, 0,
                0, 0, 0, 0, 3]

ROW_X_2_D1_2 = [1, 0, 0, 0, 0,
                0, 3, 0, 0, 0,
                0, 0, 1, 0, 0,
                0, 0, 0, 3, 0,
                0, 0, 0, 0, 3]

ROW_X_2_D1_3 = [1, 0, 0, 0, 0,
                0, 3, 0, 0, 0,
                0, 0, 3, 0, 0,
                0, 0, 0, 1, 0,
                0, 0, 0, 0, 3]

ROW_X_2_D1_4 = [3, 0, 0, 0, 0,
                0, 1, 0, 0, 0,
                0, 0, 1, 0, 0,
                0, 0, 0, 3, 0,
                0, 0, 0, 0, 3]

ROW_X_2_D1_5 = [3, 0, 0, 0, 0,
                0, 3, 0, 0, 0,
                0, 0, 3, 0, 0,
                0, 0, 0, 1, 0,
                0, 0, 0, 0, 1]

ROW_X_2_D1_6 = [3, 0, 0, 0, 0,
                0, 3, 0, 0, 0,
                0, 0, 1, 0, 0,
                0, 0, 0, 3, 0,
                0, 0, 0, 0, 1]

ROW_X_2_D1_7 = [3, 0, 0, 0, 0,
                0, 1, 0, 0, 0,
                0, 0, 3, 0, 0,
                0, 0, 0, 3, 0,
                0, 0, 0, 0, 1]

ROW_X_2_D1_8 = [3, 0, 0, 0, 0,
                0, 3, 0, 0, 0,
                0, 0, 1, 0, 0,
                0, 0, 0, 1, 0,
                0, 0, 0, 0, 3]

ROW_X_2_D1_9 = [3, 0, 0, 0, 0,
                0, 1, 0, 0, 0,
                0, 0, 3, 0, 0,
                0, 0, 0, 1, 0,
                0, 0, 0, 0, 3]

#==========================================X Format - ROW 3 - H1==========================================
ROW_X_3_H1_1 = [1, 1, 1, 3, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_3_H1_2 = [1, 1, 3, 1, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_3_H1_3 = [3, 1, 1, 3, 1,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_3_H1_4 = [3, 3, 1, 1, 1,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_3_H1_5 = [3, 1, 3, 1, 1,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_3_H1_6 = [1, 3, 1, 1, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_3_H1_7 = [3, 1, 1, 1, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

#==========================================X Format - ROW 3 - H2==========================================
ROW_X_3_H2_1 = [0, 0, 0, 0, 0,
                1, 1, 1, 3, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_3_H2_2 = [0, 0, 0, 0, 0,
                1, 1, 3, 1, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_3_H2_3 = [0, 0, 0, 0, 0,
                1, 3, 1, 1, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_3_H2_4 = [0, 0, 0, 0, 0,
                3, 3, 1, 1, 1,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_3_H2_5 = [0, 0, 0, 0, 0,
                3, 1, 3, 1, 1,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_3_H2_6 = [0, 0, 0, 0, 0,
                3, 1, 1, 3, 1,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_3_H2_7 = [0, 0, 0, 0, 0,
                3, 1, 1, 1, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

#==========================================X Format - ROW 3 - H3==========================================
ROW_X_3_H3_1 = [0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                1, 1, 1, 3, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_3_H3_2 = [0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                1, 1, 3, 1, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_3_H3_3 = [0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                1, 3, 1, 1, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_3_H3_4 = [0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                3, 3, 1, 1, 1,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_3_H3_5 = [0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                3, 1, 3, 1, 1,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_3_H3_6 = [0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                3, 1, 1, 3, 1,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_3_H3_7 = [0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                3, 1, 1, 1, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

#==========================================X Format - ROW 3 - D1==========================================
ROW_X_3_D1_1 = [1, 0, 0, 0, 0,
                0, 1, 0, 0, 0,
                0, 0, 1, 0, 0,
                0, 0, 0, 3, 0,
                0, 0, 0, 0, 3]

ROW_X_3_D1_2 = [1, 0, 0, 0, 0,
                0, 1, 0, 0, 0,
                0, 0, 3, 0, 0,
                0, 0, 0, 1, 0,
                0, 0, 0, 0, 3]

ROW_X_3_D1_3 = [1, 0, 0, 0, 0,
                0, 3, 0, 0, 0,
                0, 0, 1, 0, 0,
                0, 0, 0, 1, 0,
                0, 0, 0, 0, 3]

ROW_X_3_D1_4 = [3, 0, 0, 0, 0,
                0, 3, 0, 0, 0,
                0, 0, 1, 0, 0,
                0, 0, 0, 1, 0,
                0, 0, 0, 0, 1]

ROW_X_3_D1_5 = [3, 0, 0, 0, 0,
                0, 1, 0, 0, 0,
                0, 0, 3, 0, 0,
                0, 0, 0, 1, 0,
                0, 0, 0, 0, 1]

ROW_X_3_D1_6 = [3, 0, 0, 0, 0,
                0, 1, 0, 0, 0,
                0, 0, 1, 0, 0,
                0, 0, 0, 3, 0,
                0, 0, 0, 0, 1]

ROW_X_3_D1_7 = [3, 0, 0, 0, 0,
                0, 1, 0, 0, 0,
                0, 0, 1, 0, 0,
                0, 0, 0, 1, 0,
                0, 0, 0, 0, 3]

#==========================================X Format - ROW 4 - H1==========================================
ROW_X_4_H1_1 = [3, 1, 1, 1, 1,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_4_H1_2 = [1, 3, 1, 1, 1,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_4_H1_3 = [1, 1, 3, 1, 1,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_4_H1_4 = [1, 1, 1, 3, 1,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_4_H1_5 = [1, 1, 1, 1, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

#==========================================X Format - ROW 4 - H2==========================================
ROW_X_4_H2_1 = [0, 0, 0, 0, 0,
                3, 1, 1, 1, 1,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_4_H2_2 = [0, 0, 0, 0, 0,
                1, 3, 1, 1, 1,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_4_H2_3 = [0, 0, 0, 0, 0,
                1, 1, 3, 1, 1,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_4_H2_4 = [0, 0, 0, 0, 0,
                1, 1, 1, 3, 1,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_4_H2_5 = [0, 0, 0, 0, 0,
                1, 1, 1, 1, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

#==========================================X Format - ROW 4 - H3==========================================
ROW_X_4_H3_1 = [0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                3, 1, 1, 1, 1,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_4_H3_2 = [0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                1, 3, 1, 1, 1,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_4_H3_3 = [0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                1, 1, 3, 1, 1,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_4_H3_4 = [0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                1, 1, 1, 3, 1,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_X_4_H3_5 = [0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                1, 1, 1, 1, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

#==========================================X Format - ROW 4 - D1==========================================
ROW_X_4_D1_1 = [3, 0, 0, 0, 0,
                0, 1, 0, 0, 0,
                0, 0, 1, 0, 0,
                0, 0, 0, 1, 0,
                0, 0, 0, 0, 1]

ROW_X_4_D1_2 = [1, 0, 0, 0, 0,
                0, 3, 0, 0, 0,
                0, 0, 1, 0, 0,
                0, 0, 0, 1, 0,
                0, 0, 0, 0, 1]

ROW_X_4_D1_3 = [1, 0, 0, 0, 0,
                0, 1, 0, 0, 0,
                0, 0, 3, 0, 0,
                0, 0, 0, 1, 0,
                0, 0, 0, 0, 1]

ROW_X_4_D1_4 = [1, 0, 0, 0, 0,
                0, 1, 0, 0, 0,
                0, 0, 1, 0, 0,
                0, 0, 0, 3, 0,
                0, 0, 0, 0, 1]

ROW_X_4_D1_5 = [1, 0, 0, 0, 0,
                0, 1, 0, 0, 0,
                0, 0, 1, 0, 0,
                0, 0, 0, 1, 0,
                0, 0, 0, 0, 3]

#==========================================O Format - ROW 2 - H1==========================================
ROW_O_2_H1_1 = [2, 2, 3, 3, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_2_H1_2 = [2, 3, 2, 3, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_2_H1_3 = [2, 3, 3, 2, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_2_H1_4 = [3, 2, 2, 3, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_2_H1_5 = [3, 3, 3, 2, 2,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_2_H1_6 = [3, 3, 2, 3, 2,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_2_H1_7 = [3, 2, 3, 3, 2,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_2_H1_8 = [3, 3, 2, 2, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_2_H1_9 = [3, 2, 3, 2, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

#==========================================O Format - ROW 2 - H2==========================================
ROW_O_2_H2_1 = [0, 0, 0, 0, 0,
                2, 2, 3, 3, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_2_H2_2 = [0, 0, 0, 0, 0,
                2, 3, 2, 3, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_2_H2_3 = [0, 0, 0, 0, 0,
                2, 3, 3, 2, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_2_H2_4 = [0, 0, 0, 0, 0,
                3, 2, 2, 3, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_2_H2_5 = [0, 0, 0, 0, 0,
                3, 3, 3, 2, 2,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_2_H2_6 = [0, 0, 0, 0, 0,
                3, 3, 2, 3, 2,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_2_H2_7 = [0, 0, 0, 0, 0,
                3, 2, 3, 3, 2,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_2_H2_8 = [0, 0, 0, 0, 0,
                3, 3, 2, 2, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_2_H2_9 = [0, 0, 0, 0, 0,
                3, 2, 3, 2, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

#==========================================O Format - ROW 2 - H3==========================================
ROW_O_2_H3_1 = [0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                2, 2, 3, 3, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_2_H3_2 = [0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                2, 3, 2, 3, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_2_H3_3 = [0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                2, 3, 3, 2, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_2_H3_4 = [0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                3, 2, 2, 3, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_2_H3_5 = [0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                3, 3, 3, 2, 2,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_2_H3_6 = [0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                3, 3, 2, 3, 2,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_2_H3_7 = [0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                3, 2, 3, 3, 2,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_2_H3_8 = [0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                3, 3, 2, 2, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_2_H3_9 = [0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                3, 2, 3, 2, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

#==========================================O Format - ROW 2 - D1==========================================
ROW_O_2_D1_1 = [2, 0, 0, 0, 0,
                0, 2, 0, 0, 0,
                0, 0, 3, 0, 0,
                0, 0, 0, 3, 0,
                0, 0, 0, 0, 3]

ROW_O_2_D1_2 = [2, 0, 0, 0, 0,
                0, 3, 0, 0, 0,
                0, 0, 2, 0, 0,
                0, 0, 0, 3, 0,
                0, 0, 0, 0, 3]

ROW_O_2_D1_3 = [2, 0, 0, 0, 0,
                0, 3, 0, 0, 0,
                0, 0, 3, 0, 0,
                0, 0, 0, 2, 0,
                0, 0, 0, 0, 3]

ROW_O_2_D1_4 = [3, 0, 0, 0, 0,
                0, 2, 0, 0, 0,
                0, 0, 2, 0, 0,
                0, 0, 0, 3, 0,
                0, 0, 0, 0, 3]

ROW_O_2_D1_5 = [3, 0, 0, 0, 0,
                0, 3, 0, 0, 0,
                0, 0, 3, 0, 0,
                0, 0, 0, 2, 0,
                0, 0, 0, 0, 2]

ROW_O_2_D1_6 = [3, 0, 0, 0, 0,
                0, 3, 0, 0, 0,
                0, 0, 2, 0, 0,
                0, 0, 0, 3, 0,
                0, 0, 0, 0, 2]

ROW_O_2_D1_7 = [3, 0, 0, 0, 0,
                0, 2, 0, 0, 0,
                0, 0, 3, 0, 0,
                0, 0, 0, 3, 0,
                0, 0, 0, 0, 2]

ROW_O_2_D1_8 = [3, 0, 0, 0, 0,
                0, 3, 0, 0, 0,
                0, 0, 2, 0, 0,
                0, 0, 0, 2, 0,
                0, 0, 0, 0, 3]

ROW_O_2_D1_9 = [3, 0, 0, 0, 0,
                0, 2, 0, 0, 0,
                0, 0, 3, 0, 0,
                0, 0, 0, 2, 0,
                0, 0, 0, 0, 3]

#==========================================O Format - ROW 3 - H1==========================================
ROW_O_3_H1_1 = [2, 2, 2, 3, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_3_H1_2 = [2, 2, 3, 2, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_3_H1_3 = [3, 2, 2, 3, 2,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_3_H1_4 = [3, 3, 2, 2, 2,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_3_H1_5 = [3, 2, 3, 2, 2,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_3_H1_6 = [2, 3, 2, 2, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_3_H1_7 = [3, 2, 2, 2, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

#==========================================O Format - ROW 3 - H2==========================================
ROW_O_3_H2_1 = [0, 0, 0, 0, 0,
                2, 2, 2, 3, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_3_H2_2 = [0, 0, 0, 0, 0,
                2, 2, 3, 2, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_3_H2_3 = [0, 0, 0, 0, 0,
                2, 3, 2, 2, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_3_H2_4 = [0, 0, 0, 0, 0,
                3, 3, 2, 2, 2,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_3_H2_5 = [0, 0, 0, 0, 0,
                3, 2, 3, 2, 2,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_3_H2_6 = [0, 0, 0, 0, 0,
                3, 2, 2, 3, 2,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_3_H2_7 = [0, 0, 0, 0, 0,
                3, 2, 2, 2, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

#==========================================O Format - ROW 3 - H3==========================================
ROW_O_3_H3_1 = [0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                2, 2, 2, 3, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_3_H3_2 = [0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                2, 2, 3, 2, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_3_H3_3 = [0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                2, 3, 2, 2, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_3_H3_4 = [0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                3, 3, 2, 2, 2,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_3_H3_5 = [0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                3, 2, 3, 2, 2,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_3_H3_6 = [0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                3, 2, 2, 3, 2,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_3_H3_7 = [0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                3, 2, 2, 2, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

#==========================================O Format - ROW 3 - D1==========================================
ROW_O_3_D1_1 = [2, 0, 0, 0, 0,
                0, 2, 0, 0, 0,
                0, 0, 2, 0, 0,
                0, 0, 0, 3, 0,
                0, 0, 0, 0, 3]

ROW_O_3_D1_2 = [2, 0, 0, 0, 0,
                0, 2, 0, 0, 0,
                0, 0, 3, 0, 0,
                0, 0, 0, 2, 0,
                0, 0, 0, 0, 3]

ROW_O_3_D1_3 = [2, 0, 0, 0, 0,
                0, 3, 0, 0, 0,
                0, 0, 2, 0, 0,
                0, 0, 0, 2, 0,
                0, 0, 0, 0, 3]

ROW_O_3_D1_4 = [3, 0, 0, 0, 0,
                0, 3, 0, 0, 0,
                0, 0, 2, 0, 0,
                0, 0, 0, 2, 0,
                0, 0, 0, 0, 2]

ROW_O_3_D1_5 = [3, 0, 0, 0, 0,
                0, 2, 0, 0, 0,
                0, 0, 3, 0, 0,
                0, 0, 0, 2, 0,
                0, 0, 0, 0, 2]

ROW_O_3_D1_6 = [3, 0, 0, 0, 0,
                0, 2, 0, 0, 0,
                0, 0, 2, 0, 0,
                0, 0, 0, 3, 0,
                0, 0, 0, 0, 2]

ROW_O_3_D1_7 = [3, 0, 0, 0, 0,
                0, 2, 0, 0, 0,
                0, 0, 2, 0, 0,
                0, 0, 0, 2, 0,
                0, 0, 0, 0, 3]

#==========================================O Format - ROW 4 - H1==========================================
ROW_O_4_H1_1 = [3, 2, 2, 2, 2,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_4_H1_2 = [2, 3, 2, 2, 2,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_4_H1_3 = [2, 2, 3, 2, 2,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_4_H1_4 = [2, 2, 2, 3, 2,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_4_H1_5 = [2, 2, 2, 2, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

#==========================================O Format - ROW 4 - H2==========================================
ROW_O_4_H2_1 = [0, 0, 0, 0, 0,
                3, 2, 2, 2, 2,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_4_H2_2 = [0, 0, 0, 0, 0,
                2, 3, 2, 2, 2,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_4_H2_3 = [0, 0, 0, 0, 0,
                2, 2, 3, 2, 2,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_4_H2_4 = [0, 0, 0, 0, 0,
                2, 2, 2, 3, 2,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_4_H2_5 = [0, 0, 0, 0, 0,
                2, 2, 2, 2, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

#==========================================O Format - ROW 4 - H3==========================================
ROW_O_4_H3_1 = [0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                3, 2, 2, 2, 2,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_4_H3_2 = [0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                2, 3, 2, 2, 2,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_4_H3_3 = [0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                2, 2, 3, 2, 2,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_4_H3_4 = [0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                2, 2, 2, 3, 2,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

ROW_O_4_H3_5 = [0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                2, 2, 2, 2, 3,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]

#==========================================O Format - ROW 4 - D1==========================================
ROW_O_4_D1_1 = [3, 0, 0, 0, 0,
                0, 2, 0, 0, 0,
                0, 0, 2, 0, 0,
                0, 0, 0, 2, 0,
                0, 0, 0, 0, 2]

ROW_O_4_D1_2 = [2, 0, 0, 0, 0,
                0, 3, 0, 0, 0,
                0, 0, 2, 0, 0,
                0, 0, 0, 2, 0,
                0, 0, 0, 0, 2]

ROW_O_4_D1_3 = [2, 0, 0, 0, 0,
                0, 2, 0, 0, 0,
                0, 0, 3, 0, 0,
                0, 0, 0, 2, 0,
                0, 0, 0, 0, 2]

ROW_O_4_D1_4 = [2, 0, 0, 0, 0,
                0, 2, 0, 0, 0,
                0, 0, 2, 0, 0,
                0, 0, 0, 3, 0,
                0, 0, 0, 0, 2]

ROW_O_4_D1_5 = [2, 0, 0, 0, 0,
                0, 2, 0, 0, 0,
                0, 0, 2, 0, 0,
                0, 0, 0, 2, 0,
                0, 0, 0, 0, 3]

#===================================Board Priority Method====================================

# Pattern collections với priority riêng: (pattern, priority)
BOT_PATTERNS = [
    # ROW 1
    (ROW_X_1_H1_1, ROW_X_1_H1_1_PRIORITY), (ROW_X_1_H1_2, ROW_X_1_H1_2_PRIORITY),
    (ROW_X_1_H1_3, ROW_X_1_H1_3_PRIORITY), (ROW_X_1_H1_4, ROW_X_1_H1_4_PRIORITY),
    (ROW_X_1_H1_5, ROW_X_1_H1_5_PRIORITY),
    (ROW_X_1_H2_1, ROW_X_1_H2_1_PRIORITY), (ROW_X_1_H2_2, ROW_X_1_H2_2_PRIORITY),
    (ROW_X_1_H2_3, ROW_X_1_H2_3_PRIORITY), (ROW_X_1_H2_4, ROW_X_1_H2_4_PRIORITY),
    (ROW_X_1_H2_5, ROW_X_1_H2_5_PRIORITY),
    (ROW_X_1_H3_1, ROW_X_1_H3_1_PRIORITY), (ROW_X_1_H3_2, ROW_X_1_H3_2_PRIORITY),
    (ROW_X_1_H3_3, ROW_X_1_H3_3_PRIORITY), (ROW_X_1_H3_4, ROW_X_1_H3_4_PRIORITY),
    (ROW_X_1_H3_5, ROW_X_1_H3_5_PRIORITY),
    (ROW_X_1_D1_1, ROW_X_1_D1_1_PRIORITY), (ROW_X_1_D1_2, ROW_X_1_D1_2_PRIORITY),
    (ROW_X_1_D1_3, ROW_X_1_D1_3_PRIORITY), (ROW_X_1_D1_4, ROW_X_1_D1_4_PRIORITY),
    (ROW_X_1_D1_5, ROW_X_1_D1_5_PRIORITY),
    # ROW 2
    (ROW_X_2_H1_1, ROW_X_2_H1_1_PRIORITY), (ROW_X_2_H1_2, ROW_X_2_H1_2_PRIORITY),
    (ROW_X_2_H1_3, ROW_X_2_H1_3_PRIORITY), (ROW_X_2_H1_4, ROW_X_2_H1_4_PRIORITY),
    (ROW_X_2_H1_5, ROW_X_2_H1_5_PRIORITY), (ROW_X_2_H1_6, ROW_X_2_H1_6_PRIORITY),
    (ROW_X_2_H1_7, ROW_X_2_H1_7_PRIORITY), (ROW_X_2_H1_8, ROW_X_2_H1_8_PRIORITY),
    (ROW_X_2_H1_9, ROW_X_2_H1_9_PRIORITY),
    (ROW_X_2_H2_1, ROW_X_2_H2_1_PRIORITY), (ROW_X_2_H2_2, ROW_X_2_H2_2_PRIORITY),
    (ROW_X_2_H2_3, ROW_X_2_H2_3_PRIORITY), (ROW_X_2_H2_4, ROW_X_2_H2_4_PRIORITY),
    (ROW_X_2_H2_5, ROW_X_2_H2_5_PRIORITY), (ROW_X_2_H2_6, ROW_X_2_H2_6_PRIORITY),
    (ROW_X_2_H2_7, ROW_X_2_H2_7_PRIORITY), (ROW_X_2_H2_8, ROW_X_2_H2_8_PRIORITY),
    (ROW_X_2_H2_9, ROW_X_2_H2_9_PRIORITY),
    (ROW_X_2_H3_1, ROW_X_2_H3_1_PRIORITY), (ROW_X_2_H3_2, ROW_X_2_H3_2_PRIORITY),
    (ROW_X_2_H3_3, ROW_X_2_H3_3_PRIORITY), (ROW_X_2_H3_4, ROW_X_2_H3_4_PRIORITY),
    (ROW_X_2_H3_5, ROW_X_2_H3_5_PRIORITY), (ROW_X_2_H3_6, ROW_X_2_H3_6_PRIORITY),
    (ROW_X_2_H3_7, ROW_X_2_H3_7_PRIORITY), (ROW_X_2_H3_8, ROW_X_2_H3_8_PRIORITY),
    (ROW_X_2_H3_9, ROW_X_2_H3_9_PRIORITY),
    (ROW_X_2_D1_1, ROW_X_2_D1_1_PRIORITY), (ROW_X_2_D1_2, ROW_X_2_D1_2_PRIORITY),
    (ROW_X_2_D1_3, ROW_X_2_D1_3_PRIORITY), (ROW_X_2_D1_4, ROW_X_2_D1_4_PRIORITY),
    (ROW_X_2_D1_5, ROW_X_2_D1_5_PRIORITY), (ROW_X_2_D1_6, ROW_X_2_D1_6_PRIORITY),
    (ROW_X_2_D1_7, ROW_X_2_D1_7_PRIORITY), (ROW_X_2_D1_8, ROW_X_2_D1_8_PRIORITY),
    (ROW_X_2_D1_9, ROW_X_2_D1_9_PRIORITY),
    # ROW 3
    (ROW_X_3_H1_1, ROW_X_3_H1_1_PRIORITY), (ROW_X_3_H1_2, ROW_X_3_H1_2_PRIORITY),
    (ROW_X_3_H1_3, ROW_X_3_H1_3_PRIORITY), (ROW_X_3_H1_4, ROW_X_3_H1_4_PRIORITY),
    (ROW_X_3_H1_5, ROW_X_3_H1_5_PRIORITY), (ROW_X_3_H1_6, ROW_X_3_H1_6_PRIORITY),
    (ROW_X_3_H1_7, ROW_X_3_H1_7_PRIORITY),
    (ROW_X_3_H2_1, ROW_X_3_H2_1_PRIORITY), (ROW_X_3_H2_2, ROW_X_3_H2_2_PRIORITY),
    (ROW_X_3_H2_3, ROW_X_3_H2_3_PRIORITY), (ROW_X_3_H2_4, ROW_X_3_H2_4_PRIORITY),
    (ROW_X_3_H2_5, ROW_X_3_H2_5_PRIORITY), (ROW_X_3_H2_6, ROW_X_3_H2_6_PRIORITY),
    (ROW_X_3_H2_7, ROW_X_3_H2_7_PRIORITY),
    (ROW_X_3_H3_1, ROW_X_3_H3_1_PRIORITY), (ROW_X_3_H3_2, ROW_X_3_H3_2_PRIORITY),
    (ROW_X_3_H3_3, ROW_X_3_H3_3_PRIORITY), (ROW_X_3_H3_4, ROW_X_3_H3_4_PRIORITY),
    (ROW_X_3_H3_5, ROW_X_3_H3_5_PRIORITY), (ROW_X_3_H3_6, ROW_X_3_H3_6_PRIORITY),
    (ROW_X_3_H3_7, ROW_X_3_H3_7_PRIORITY),
    (ROW_X_3_D1_1, ROW_X_3_D1_1_PRIORITY), (ROW_X_3_D1_2, ROW_X_3_D1_2_PRIORITY),
    (ROW_X_3_D1_3, ROW_X_3_D1_3_PRIORITY), (ROW_X_3_D1_4, ROW_X_3_D1_4_PRIORITY),
    (ROW_X_3_D1_5, ROW_X_3_D1_5_PRIORITY), (ROW_X_3_D1_6, ROW_X_3_D1_6_PRIORITY),
    (ROW_X_3_D1_7, ROW_X_3_D1_7_PRIORITY),
    # ROW 4
    (ROW_X_4_H1_1, ROW_X_4_H1_1_PRIORITY), (ROW_X_4_H1_2, ROW_X_4_H1_2_PRIORITY),
    (ROW_X_4_H1_3, ROW_X_4_H1_3_PRIORITY), (ROW_X_4_H1_4, ROW_X_4_H1_4_PRIORITY),
    (ROW_X_4_H1_5, ROW_X_4_H1_5_PRIORITY),
    (ROW_X_4_H2_1, ROW_X_4_H2_1_PRIORITY), (ROW_X_4_H2_2, ROW_X_4_H2_2_PRIORITY),
    (ROW_X_4_H2_3, ROW_X_4_H2_3_PRIORITY), (ROW_X_4_H2_4, ROW_X_4_H2_4_PRIORITY),
    (ROW_X_4_H2_5, ROW_X_4_H2_5_PRIORITY),
    (ROW_X_4_H3_1, ROW_X_4_H3_1_PRIORITY), (ROW_X_4_H3_2, ROW_X_4_H3_2_PRIORITY),
    (ROW_X_4_H3_3, ROW_X_4_H3_3_PRIORITY), (ROW_X_4_H3_4, ROW_X_4_H3_4_PRIORITY),
    (ROW_X_4_H3_5, ROW_X_4_H3_5_PRIORITY),
    (ROW_X_4_D1_1, ROW_X_4_D1_1_PRIORITY), (ROW_X_4_D1_2, ROW_X_4_D1_2_PRIORITY),
    (ROW_X_4_D1_3, ROW_X_4_D1_3_PRIORITY), (ROW_X_4_D1_4, ROW_X_4_D1_4_PRIORITY),
    (ROW_X_4_D1_5, ROW_X_4_D1_5_PRIORITY),
]

OPPONENT_PATTERNS = [
    # ROW 1
    (ROW_O_1_H1_1, ROW_O_1_H1_1_PRIORITY), (ROW_O_1_H1_2, ROW_O_1_H1_2_PRIORITY),
    (ROW_O_1_H1_3, ROW_O_1_H1_3_PRIORITY), (ROW_O_1_H1_4, ROW_O_1_H1_4_PRIORITY),
    (ROW_O_1_H1_5, ROW_O_1_H1_5_PRIORITY),
    (ROW_O_1_H2_1, ROW_O_1_H2_1_PRIORITY), (ROW_O_1_H2_2, ROW_O_1_H2_2_PRIORITY),
    (ROW_O_1_H2_3, ROW_O_1_H2_3_PRIORITY), (ROW_O_1_H2_4, ROW_O_1_H2_4_PRIORITY),
    (ROW_O_1_H2_5, ROW_O_1_H2_5_PRIORITY),
    (ROW_O_1_H3_1, ROW_O_1_H3_1_PRIORITY), (ROW_O_1_H3_2, ROW_O_1_H3_2_PRIORITY),
    (ROW_O_1_H3_3, ROW_O_1_H3_3_PRIORITY), (ROW_O_1_H3_4, ROW_O_1_H3_4_PRIORITY),
    (ROW_O_1_H3_5, ROW_O_1_H3_5_PRIORITY),
    (ROW_O_1_D1_1, ROW_O_1_D1_1_PRIORITY), (ROW_O_1_D1_2, ROW_O_1_D1_2_PRIORITY),
    (ROW_O_1_D1_3, ROW_O_1_D1_3_PRIORITY), (ROW_O_1_D1_4, ROW_O_1_D1_4_PRIORITY),
    (ROW_O_1_D1_5, ROW_O_1_D1_5_PRIORITY),
    # ROW 2
    (ROW_O_2_H1_1, ROW_O_2_H1_1_PRIORITY), (ROW_O_2_H1_2, ROW_O_2_H1_2_PRIORITY),
    (ROW_O_2_H1_3, ROW_O_2_H1_3_PRIORITY), (ROW_O_2_H1_4, ROW_O_2_H1_4_PRIORITY),
    (ROW_O_2_H1_5, ROW_O_2_H1_5_PRIORITY), (ROW_O_2_H1_6, ROW_O_2_H1_6_PRIORITY),
    (ROW_O_2_H1_7, ROW_O_2_H1_7_PRIORITY), (ROW_O_2_H1_8, ROW_O_2_H1_8_PRIORITY),
    (ROW_O_2_H1_9, ROW_O_2_H1_9_PRIORITY),
    (ROW_O_2_H2_1, ROW_O_2_H2_1_PRIORITY), (ROW_O_2_H2_2, ROW_O_2_H2_2_PRIORITY),
    (ROW_O_2_H2_3, ROW_O_2_H2_3_PRIORITY), (ROW_O_2_H2_4, ROW_O_2_H2_4_PRIORITY),
    (ROW_O_2_H2_5, ROW_O_2_H2_5_PRIORITY), (ROW_O_2_H2_6, ROW_O_2_H2_6_PRIORITY),
    (ROW_O_2_H2_7, ROW_O_2_H2_7_PRIORITY), (ROW_O_2_H2_8, ROW_O_2_H2_8_PRIORITY),
    (ROW_O_2_H2_9, ROW_O_2_H2_9_PRIORITY),
    (ROW_O_2_H3_1, ROW_O_2_H3_1_PRIORITY), (ROW_O_2_H3_2, ROW_O_2_H3_2_PRIORITY),
    (ROW_O_2_H3_3, ROW_O_2_H3_3_PRIORITY), (ROW_O_2_H3_4, ROW_O_2_H3_4_PRIORITY),
    (ROW_O_2_H3_5, ROW_O_2_H3_5_PRIORITY), (ROW_O_2_H3_6, ROW_O_2_H3_6_PRIORITY),
    (ROW_O_2_H3_7, ROW_O_2_H3_7_PRIORITY), (ROW_O_2_H3_8, ROW_O_2_H3_8_PRIORITY),
    (ROW_O_2_H3_9, ROW_O_2_H3_9_PRIORITY),
    (ROW_O_2_D1_1, ROW_O_2_D1_1_PRIORITY), (ROW_O_2_D1_2, ROW_O_2_D1_2_PRIORITY),
    (ROW_O_2_D1_3, ROW_O_2_D1_3_PRIORITY), (ROW_O_2_D1_4, ROW_O_2_D1_4_PRIORITY),
    (ROW_O_2_D1_5, ROW_O_2_D1_5_PRIORITY), (ROW_O_2_D1_6, ROW_O_2_D1_6_PRIORITY),
    (ROW_O_2_D1_7, ROW_O_2_D1_7_PRIORITY), (ROW_O_2_D1_8, ROW_O_2_D1_8_PRIORITY),
    (ROW_O_2_D1_9, ROW_O_2_D1_9_PRIORITY),
    # ROW 3
    (ROW_O_3_H1_1, ROW_O_3_H1_1_PRIORITY), (ROW_O_3_H1_2, ROW_O_3_H1_2_PRIORITY),
    (ROW_O_3_H1_3, ROW_O_3_H1_3_PRIORITY), (ROW_O_3_H1_4, ROW_O_3_H1_4_PRIORITY),
    (ROW_O_3_H1_5, ROW_O_3_H1_5_PRIORITY), (ROW_O_3_H1_6, ROW_O_3_H1_6_PRIORITY),
    (ROW_O_3_H1_7, ROW_O_3_H1_7_PRIORITY),
    (ROW_O_3_H2_1, ROW_O_3_H2_1_PRIORITY), (ROW_O_3_H2_2, ROW_O_3_H2_2_PRIORITY),
    (ROW_O_3_H2_3, ROW_O_3_H2_3_PRIORITY), (ROW_O_3_H2_4, ROW_O_3_H2_4_PRIORITY),
    (ROW_O_3_H2_5, ROW_O_3_H2_5_PRIORITY), (ROW_O_3_H2_6, ROW_O_3_H2_6_PRIORITY),
    (ROW_O_3_H2_7, ROW_O_3_H2_7_PRIORITY),
    (ROW_O_3_H3_1, ROW_O_3_H3_1_PRIORITY), (ROW_O_3_H3_2, ROW_O_3_H3_2_PRIORITY),
    (ROW_O_3_H3_3, ROW_O_3_H3_3_PRIORITY), (ROW_O_3_H3_4, ROW_O_3_H3_4_PRIORITY),
    (ROW_O_3_H3_5, ROW_O_3_H3_5_PRIORITY), (ROW_O_3_H3_6, ROW_O_3_H3_6_PRIORITY),
    (ROW_O_3_H3_7, ROW_O_3_H3_7_PRIORITY),
    (ROW_O_3_D1_1, ROW_O_3_D1_1_PRIORITY), (ROW_O_3_D1_2, ROW_O_3_D1_2_PRIORITY),
    (ROW_O_3_D1_3, ROW_O_3_D1_3_PRIORITY), (ROW_O_3_D1_4, ROW_O_3_D1_4_PRIORITY),
    (ROW_O_3_D1_5, ROW_O_3_D1_5_PRIORITY), (ROW_O_3_D1_6, ROW_O_3_D1_6_PRIORITY),
    (ROW_O_3_D1_7, ROW_O_3_D1_7_PRIORITY),
    # ROW 4
    (ROW_O_4_H1_1, ROW_O_4_H1_1_PRIORITY), (ROW_O_4_H1_2, ROW_O_4_H1_2_PRIORITY),
    (ROW_O_4_H1_3, ROW_O_4_H1_3_PRIORITY), (ROW_O_4_H1_4, ROW_O_4_H1_4_PRIORITY),
    (ROW_O_4_H1_5, ROW_O_4_H1_5_PRIORITY),
    (ROW_O_4_H2_1, ROW_O_4_H2_1_PRIORITY), (ROW_O_4_H2_2, ROW_O_4_H2_2_PRIORITY),
    (ROW_O_4_H2_3, ROW_O_4_H2_3_PRIORITY), (ROW_O_4_H2_4, ROW_O_4_H2_4_PRIORITY),
    (ROW_O_4_H2_5, ROW_O_4_H2_5_PRIORITY),
    (ROW_O_4_H3_1, ROW_O_4_H3_1_PRIORITY), (ROW_O_4_H3_2, ROW_O_4_H3_2_PRIORITY),
    (ROW_O_4_H3_3, ROW_O_4_H3_3_PRIORITY), (ROW_O_4_H3_4, ROW_O_4_H3_4_PRIORITY),
    (ROW_O_4_H3_5, ROW_O_4_H3_5_PRIORITY),
    (ROW_O_4_D1_1, ROW_O_4_D1_1_PRIORITY), (ROW_O_4_D1_2, ROW_O_4_D1_2_PRIORITY),
    (ROW_O_4_D1_3, ROW_O_4_D1_3_PRIORITY), (ROW_O_4_D1_4, ROW_O_4_D1_4_PRIORITY),
    (ROW_O_4_D1_5, ROW_O_4_D1_5_PRIORITY),
]


def get_highest_priority_board(boards: list[list[list[int]]], player: int):
    """Get the board with highest priority for given player"""
    highest_priority_board = None
    highest_priority = -1

    for board in boards:
        priority = get_priority(board, player)
        if priority > highest_priority:
            highest_priority = priority
            highest_priority_board = board

    return highest_priority_board


def get_priority(board: list[list[int]], player: int) -> float:
    """
    Calculate priority score for a board state.
    
    Args:
        board: 2D board (5x5)
        player: 1 for X (bot), 2 for O (opponent)
    
    Returns:
        Priority score (higher = better position)
    """
    board_1d = board_2d_to_1d(board)
    
    # player = 1 means bot is X, opponent is O
    # player = 2 means bot is O, opponent is X
    if player == 1:
        bot_patterns = BOT_PATTERNS
        opp_patterns = OPPONENT_PATTERNS
    else:
        bot_patterns = OPPONENT_PATTERNS
        opp_patterns = BOT_PATTERNS
    
    priority = 0.0
    priority += sum_pattern_priority(board_1d, bot_patterns, player)
    priority += sum_pattern_priority(board_1d, opp_patterns, player)
    
    return priority


def sum_pattern_priority(board: list[int], patterns: list[tuple], player: int) -> float:
    """
    Sum priorities of all matching patterns (considering all transformations).
    Each pattern is counted only once even if multiple transformations match.
    """
    transformations = [
        t_identity, t_rot90, t_rot180, t_rot270,
        t_reflect_h, t_reflect_v, t_reflect_main, t_reflect_anti
    ]
    
    total = 0.0
    for pattern, priority in patterns:
        for transform in transformations:
            transformed_pattern = apply_transformation(pattern, transform)
            if pattern_matches(board, transformed_pattern, player):
                total += priority
                break  # Don't count same pattern multiple times via different transforms
    return total


def pattern_matches(board: list[int], pattern: list[int], player: int) -> bool:
    """
    Check if board matches pattern.
    
    Pattern values:
        0 = Wildcard (matches anything)
        1 = Must be X
        2 = Must be O
        3 = Must NOT be opponent (can be empty or same player)
    """
    opponent = 2 if player == 1 else 1
    
    for i in range(25):
        p = pattern[i]
        b = board[i]
        
        if p == 0:
            continue
        elif p == 1:
            if b != 1:
                return False
        elif p == 2:
            if b != 2:
                return False
        elif p == 3:
            if b == opponent:
                return False
    return True

#===================================Unlimited Space logic====================================
BOARD_SIZE = 10
LOSE_THRESHOLD = 0.05 # 5%
DANGER_LOSE_RATE_THRESHOLD = 0.01

def best_steps_unlimited(currBoard: list[list[int]], player: int, last_move_col: int, last_move_row: int):
    boards_5_x_5= []
    glob_c_r = []
    for c in range(2, BOARD_SIZE - 2):
        for r in range(2, BOARD_SIZE - 2):
            board_5_x_5 = get_board_5_x_5(currBoard, r, c)
            board_5_x_5_2D = board_1d_to_2d(board_5_x_5)
            boards_5_x_5.append(board_5_x_5_2D)
            glob_c_r.append((c, r))
    
    best_board = get_highest_priority_board(boards_5_x_5, player)
    index = boards_5_x_5.index(best_board)
    glob_c, glob_r = glob_c_r[index]
            


    return get_best_step_5x5(best_board, player, glob_r, glob_c)

    

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

def convert_to_db_schema_1d(board_1d: list[int]) -> list[int]:
    """
    Chuyển đổi board 1D từ get_board_5_x_5() sang format DB schema
    
    get_board_5_x_5() đang duyệt theo COL trước ROW (SAI):
        for c in range(...):
            for r in range(...):
                board_5_x_5_index = (r - ...) * 5 + (c - ...)
    
    DB Schema cần duyệt theo ROW trước COL (ĐÚNG):
        i11, i12, i13, i14, i15, i21, i22, ..., i55
    
    Args:
        board_1d: Board 1D [0-24] từ get_board_5_x_5() (col-major order)
        
    Returns:
        Board 1D [0-24] theo DB schema (row-major order: i11->i55)
    """
    result = [0] * 25
    for idx in range(25):
        # get_board_5_x_5 duyệt: col trước, row sau
        col = idx // 5
        row = idx % 5
        # DB schema cần: row trước, col sau
        db_index = row * 5 + col
        result[db_index] = board_1d[idx]
    return result

def convert_to_db_schema_1d(board_2d: list[list[int]]) -> list[int]:
    """
    Chuyển đổi board 2D sang format DB schema 1D
    
    DB Schema cần duyệt theo ROW trước COL:
        i11, i12, i13, i14, i15, i21, i22, ..., i55
    
    Args:
        board_2d: Board 2D array [[...], [...], ...] (5x5)
                  board_2d[row][col] với row, col từ 0 đến 4
        
    Returns:
        Board 1D [0-24] theo DB schema (row-major order: i11->i55)
        
    Example:
        board_2d = [[1, 0, 2, 0, 1],    # row 0: i11, i12, i13, i14, i15
                    [2, 1, 0, 1, 0],    # row 1: i21, i22, i23, i24, i25
                    [0, 0, 1, 0, 2],    # row 2: i31, i32, i33, i34, i35
                    [1, 2, 0, 2, 0],    # row 3: i41, i42, i43, i44, i45
                    [0, 1, 2, 0, 1]]    # row 4: i51, i52, i53, i54, i55
        
        result = [1, 0, 2, 0, 1, 2, 1, 0, 1, 0, 0, 0, 1, 0, 2, 1, 2, 0, 2, 0, 0, 1, 2, 0, 1]
    """
    result = []
    for row in range(5):
        for col in range(5):
            result.append(board_2d[row][col])
    return result

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
        col_index = BOARD_SIZE - 3
    elif last_move_col < 2:
        col_index = 2

    return col_index
    
def get_row_index_5_x_5(last_move_row: int) -> int:
    # row limit (board edge)
    row_index = 0
    if last_move_row > BOARD_SIZE - 3:
        row_index = BOARD_SIZE - 3
    elif last_move_row < 2:
        row_index = 2

    return row_index

#==========================================Game Logic 15x15==========================================

class TicTacToe15x15:
    """
    Game logic cho Tic-Tac-Toe 15x15
    Chiến thắng khi có 5 ô liên tiếp theo hàng ngang, dọc hoặc chéo
    """
    
    def __init__(self):
        """Khởi tạo board 15x15"""
        self.board = [[0 for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
        self.current_player = 1  # Player 1 (X) đi trước
        self.last_move = None  # (row, col)
        self.winner = None
        self.game_over = False
        
    def reset(self):
        """Reset game về trạng thái ban đầu"""
        self.board = [[0 for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
        self.current_player = 1
        self.last_move = None
        self.winner = None
        self.game_over = False
        
    def is_valid_move(self, row: int, col: int) -> bool:
        """
        Kiểm tra nước đi có hợp lệ không
        
        Args:
            row: Hàng (0-14)
            col: Cột (0-14)
            
        Returns:
            True nếu hợp lệ, False nếu không
        """
        if self.game_over:
            return False
            
        if row < 0 or row >= BOARD_SIZE or col < 0 or col >= BOARD_SIZE:
            return False
            
        return self.board[row][col] == 0
    
    def make_move(self, row: int, col: int) -> bool:
        """
        Thực hiện nước đi
        
        Args:
            row: Hàng (0-14)
            col: Cột (0-14)
            
        Returns:
            True nếu thành công, False nếu không hợp lệ
        """
        if not self.is_valid_move(row, col):
            return False
            
        self.board[row][col] = self.current_player
        self.last_move = (row, col)
        
        # Kiểm tra thắng
        if self.check_winner(row, col):
            self.winner = self.current_player
            self.game_over = True
            return True
            
        # Kiểm tra hòa (board đầy)
        if self.is_board_full():
            self.game_over = True
            self.winner = 0  # Draw
            return True
            
        # Chuyển lượt
        self.current_player = 2 if self.current_player == 1 else 1
        return True
    
    def check_winner(self, row: int, col: int) -> bool:
        """
        Kiểm tra xem có người thắng không sau nước đi vừa rồi
        
        Args:
            row: Hàng vừa đi
            col: Cột vừa đi
            
        Returns:
            True nếu có người thắng
        """
        player = self.board[row][col]
        
        # Kiểm tra 4 hướng: ngang, dọc, chéo chính, chéo phụ
        directions = [
            (0, 1),   # Ngang
            (1, 0),   # Dọc
            (1, 1),   # Chéo chính
            (1, -1)   # Chéo phụ
        ]
        
        for dr, dc in directions:
            count = 1  # Đếm ô hiện tại
            
            # Đếm theo hướng thuận
            r, c = row + dr, col + dc
            while (0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE and 
                   self.board[r][c] == player):
                count += 1
                r += dr
                c += dc
            
            # Đếm theo hướng ngược
            r, c = row - dr, col - dc
            while (0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE and 
                   self.board[r][c] == player):
                count += 1
                r -= dr
                c -= dc
            
            # Nếu có 5 ô liên tiếp -> thắng
            if count >= 5:
                return True
                
        return False
    
    def is_board_full(self) -> bool:
        """Kiểm tra board đã đầy chưa"""
        for row in self.board:
            if 0 in row:
                return False
        return True
    
    def get_ai_move(self) -> tuple:
        """
        Lấy nước đi tốt nhất cho AI
        
        Returns:
            (row, col) hoặc (-1, -1) nếu không tìm thấy
        """
        if self.last_move is None:
            # Nước đi đầu tiên -> đi giữa board
            return (BOARD_SIZE // 2, BOARD_SIZE // 2)
        
        last_row, last_col = self.last_move
        return best_steps_unlimited(self.board, self.current_player, last_col, last_row)
    
    def print_board(self):
        """In board ra console (hiển thị đủ 15x15)"""
        print("\n    ", end="")
        # Header cột
        for i in range(BOARD_SIZE):
            print(f"{i:2d}", end=" ")
        print()
        print("   " + "─" * (BOARD_SIZE * 3 + 1))
        
        # In từng hàng
        for i, row in enumerate(self.board):
            print(f"{i:2d} │", end="")
            for cell in row:
                if cell == 0:
                    print(" ·", end=" ")
                elif cell == 1:
                    print(" X", end=" ")
                else:
                    print(" O", end=" ")
            print("│")
        
        print("   " + "─" * (BOARD_SIZE * 3 + 1))
        print()


def play_game_human_vs_ai():
    """
    Chơi game: Human (X) vs AI (O)
    """
    game = TicTacToe15x15()
    
    print("=" * 70)
    print(" " * 20 + "🎮 TIC-TAC-TOE 15x15")
    print(" " * 20 + "HUMAN vs AI")
    print("=" * 70)
    print("📋 Quy tắc: 5 ô liên tiếp theo hàng ngang/dọc/chéo để thắng")
    print("👤 Bạn là X (đi trước) | 🤖 AI là O")
    print("=" * 70)
    
    while not game.game_over:
        game.print_board()
        
        if game.current_player == 1:
            # Human turn
            print(f"🎯 Lượt của BẠN (X)")
            try:
                row = int(input("   Nhập hàng (0-14): "))
                col = int(input("   Nhập cột (0-14): "))
                
                if not game.make_move(row, col):
                    print("❌ Nước đi không hợp lệ! Thử lại.\n")
                    continue
                    
            except ValueError:
                print("❌ Vui lòng nhập số!\n")
                continue
            except KeyboardInterrupt:
                print("\n\n👋 Thoát game!")
                return
                
        else:
            # AI turn
            print(f"🤖 Lượt của AI (O)")
            start_time = time.time()
            row, col = game.get_ai_move()
            elapsed = time.time() - start_time
            
            if row == -1 or col == -1:
                print("⚠️  AI không tìm thấy nước đi tốt, chọn ngẫu nhiên...")
                # Tìm ô trống đầu tiên
                found = False
                for r in range(BOARD_SIZE):
                    for c in range(BOARD_SIZE):
                        if game.is_valid_move(r, c):
                            row, col = r, c
                            found = True
                            break
                    if found:
                        break
            
            print(f"   AI đi: ({row}, {col}) - Suy nghĩ trong {elapsed:.2f}s")
            game.make_move(row, col)
            time.sleep(0.3)
    
    # Game kết thúc
    game.print_board()
    print("=" * 70)
    if game.winner == 0:
        print(" " * 30 + "🤝 HÒA!")
    elif game.winner == 1:
        print(" " * 25 + "🎉 CHÚC MỪNG! BẠN THẮNG!")
    else:
        print(" " * 28 + "💻 AI THẮNG!")
    print("=" * 70)


def play_game_ai_vs_ai():
    """
    Chơi game: AI (X) vs AI (O)
    """
    game = TicTacToe15x15()
    
    print("=" * 70)
    print(" " * 20 + "🤖 TIC-TAC-TOE 15x15")
    print(" " * 23 + "AI vs AI")
    print("=" * 70)
    print()
    
    move_count = 0
    
    while not game.game_over:
        game.print_board()
        
        player_name = "AI-X" if game.current_player == 1 else "AI-O"
        symbol = "X" if game.current_player == 1 else "O"
        print(f"🤖 Lượt của {player_name} ({symbol})")
        
        start_time = time.time()
        row, col = game.get_ai_move()
        elapsed = time.time() - start_time
        
        if row == -1 or col == -1:
            print(f"⚠️  {player_name} không tìm thấy nước đi tốt, chọn ngẫu nhiên...")
            # Tìm ô trống đầu tiên
            found = False
            for r in range(BOARD_SIZE):
                for c in range(BOARD_SIZE):
                    if game.is_valid_move(r, c):
                        row, col = r, c
                        found = True
                        break
                if found:
                    break
        
        print(f"   {player_name} đi: ({row}, {col}) - Suy nghĩ trong {elapsed:.2f}s")
        game.make_move(row, col)
        move_count += 1
        
        time.sleep(0.3)
    
    # Game kết thúc
    game.print_board()
    print("=" * 70)
    print(f"📊 Tổng số nước đi: {move_count}")
    if game.winner == 0:
        print(" " * 30 + "🤝 HÒA!")
    elif game.winner == 1:
        print(" " * 28 + "🎉 AI-X THẮNG!")
    else:
        print(" " * 28 + "💻 AI-O THẮNG!")
    print("=" * 70)


#==========================================Main==========================================

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print(" " * 20 + "🎮 TIC-TAC-TOE 15x15")
    print("=" * 70)
    print("\n📋 Chọn chế độ chơi:")
    print("   1️⃣  Human vs AI")
    print("   2️⃣  AI vs AI")
    print()
    
    try:
        choice = input("👉 Nhập lựa chọn (1/2): ").strip()
        
        if choice == "1":
            play_game_human_vs_ai()
        elif choice == "2":
            play_game_ai_vs_ai()
        else:
            print("❌ Lựa chọn không hợp lệ!")
    except KeyboardInterrupt:
        print("\n\n👋 Tạm biệt!")