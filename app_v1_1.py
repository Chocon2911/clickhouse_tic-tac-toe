from flask import Flask, render_template, request, jsonify
import sys

# Import AI logic
try:
    from statistic_ai_100_x_100 import best_steps_unlimited
    print("✅ Import AI thành công!")
except ImportError as e:
    print(f"⚠️ Lỗi import: {e}")
    sys.exit(1)

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/ai_move', methods=['POST'])
def ai_move():
    """Gọi AI để lấy nước đi - KHÔNG có game logic"""
    try:
        data = request.get_json()
        board = data.get('board')
        player = data.get('player', 2)
        last_move_row = data.get('last_move_row', 7)
        last_move_col = data.get('last_move_col', 7)
        
        # Chỉ gọi AI và trả về
        best_row, best_col = best_steps_unlimited(
            board, 
            player, 
            last_move_col,
            last_move_row
        )
        
        return jsonify({'row': best_row, 'col': best_col})
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({'row': -1, 'col': -1}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)