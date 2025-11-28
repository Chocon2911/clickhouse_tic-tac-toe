# Tic-Tac-Toe 5x5 AI Project with ClickHouse Database

## 📋 Project Overview

This project implements an intelligent Tic-Tac-Toe AI system that uses statistical probability methods and a ClickHouse database to make optimal moves. The AI analyzes historical game data stored in ClickHouse to calculate win rates for each possible move, enabling data-driven decision making.

### Key Features

- **Statistical AI**: Uses probability-based decision making by querying historical game outcomes
- **ClickHouse Database**: Stores millions of game states and outcomes for fast querying
- **Multiple Game Modes**:
  - 5x5 board (classic mode) - Fully functional
  - 15x15 board (extended mode) - Fully functional
  - 100x100 board (unlimited space) - **In Development** ⚠️
- **Web Interface**: Flask-based web application with interactive UI
- **Console Interface**: Command-line game interface for testing
- **Symmetry Optimization**: Uses canonical board forms to reduce database size

---

## 🏗️ Architecture

### System Components

1. **Database Layer (ClickHouse)**
   - Stores game states and outcomes
   - Tables organized by move count (layers 9-25 for wins, separate table for draws)
   - Optimized for fast COUNT queries

2. **AI Engine**
   - Queries database for each possible move
   - Calculates win/loss/draw probabilities
   - Selects move with highest win rate or lowest loss rate

3. **Game Logic**
   - Board state management
   - Win condition checking (5 in a row)
   - Move validation

4. **Interface Layer**
   - Flask web server (`app.py`)
   - Console interface (`statistic_ai.py`)
   - Alternative web interface (`app_v1_1.py`)

---

## 📊 Database Structure

### Tables

The database contains the following tables:

- **`ttt_5_draw`**: Stores all draw game outcomes
- **`ttt_5_l9` to `ttt_5_l25`**: Stores win outcomes for each move count (layer)
  - Odd layers (9, 11, 13, ..., 25): X wins
  - Even layers (10, 12, 14, ..., 24): O wins

### Schema

Each table contains:
- `canonical_form`: String representation of board state
- `win_actor`: 'X', 'O', or 'D' (draw)
- `i11` to `i55`: Individual cell values ('X', 'O', or empty)

### Data Ingestion

- **`ingest.py`**: Main ingestion script for CSV files
- **`ingest_old.py`**: Legacy ingestion script
- **`ingest_draw_old.py`**: Legacy draw data ingestion

---

## 🤖 AI Logic

### Decision Making Process

1. **Board Normalization**: Convert current board to canonical form using symmetry transformations
   - 8 transformations: identity, rotations (90°, 180°, 270°), reflections (horizontal, vertical, main diagonal, anti-diagonal)
   - Select lexicographically smallest form

2. **Move Evaluation**: For each possible move:
   - Create hypothetical board state
   - Convert to canonical form
   - Query database for matching game states
   - Count wins, losses, and draws
   - Calculate probabilities

3. **Move Selection**:
   - Primary: Choose move with highest win rate
   - Fallback: If no winning move, choose move with lowest loss rate
   - Safety: If in danger (high loss rate), prioritize defensive moves

### For 15x15/100x100 Boards

The AI uses a sliding window approach:
- Extract 5x5 regions around opponent's last move
- Query database for each 5x5 region
- Accumulate win/loss rates across all regions
- Select move with best aggregated statistics

---

## 📁 File Structure

```
clickhouse_tic-tac-toe/
├── app.py                      # Main Flask web application (15x15)
├── app_v1_1.py                 # Alternative Flask app (100x100 - in development)
├── statistic_ai.py             # Console game interface (5x5)
├── statistic_ai_100_x_100.py   # AI logic for 15x15/100x100 boards
├── ingest.py                   # CSV data ingestion script
├── ingest_old.py               # Legacy ingestion script
├── ingest_draw_old.py          # Legacy draw data ingestion
├── requirements.txt            # Python dependencies
├── docker-compose.yml          # ClickHouse Docker configuration
├── README.md                   # Basic project documentation
├── CURSOR_README.md            # This comprehensive documentation
│
├── data/                       # CSV data files
│   ├── ttt_5_l9.csv
│   ├── ttt_5_l10.csv
│   ├── ...
│   ├── ttt_5_l25.csv
│   └── tic_tac_toe_draw_layer_25_quoted.csv
│
├── schema/                     # ClickHouse table schemas
│   ├── ttt_5_draw.sql
│   ├── ttt_5_l9.sql
│   ├── ttt_5_l10.sql
│   ├── ...
│   └── ttt_5_l25.sql
│
└── templates/                  # Flask HTML templates
    └── index.html              # Web game interface
```

---

## 🚀 Setup Instructions

### Prerequisites

- Python 3.9+
- Docker and Docker Compose (for ClickHouse)
- pip package manager

### Installation Steps

1. **Clone the repository** (if applicable)

2. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Start ClickHouse using Docker**:
   ```bash
   docker-compose up -d
   ```

4. **Create database and tables**:
   ```bash
   python ingest.py
   ```

5. **Verify tables are created**:
   ```bash
   python ingest.py --verify
   ```

6. **Ingest game data** (if CSV files are available):
   ```bash
   # Follow instructions in README.md for data ingestion
   ```

---

## 🎮 Usage

### Console Interface (5x5)

Run the console-based game:
```bash
python statistic_ai.py
```

Options:
- **Mode 1**: Human vs AI
- **Mode 2**: AI vs AI (for testing)

### Web Interface (15x15)

Start the Flask server:
```bash
python app.py
```

Then open your browser to:
```
http://localhost:5000
```

### Web Interface (100x100 - In Development)

⚠️ **Note**: This feature is currently under development and may not be fully functional.

Start the alternative Flask server:
```bash
python app_v1_1.py
```

Then open your browser to:
```
http://localhost:5000
```

---

## 🔧 Configuration

### Database Connection

Edit the following constants in the Python files:

```python
CLICKHOUSE_HTTP = "http://localhost:8123"
CLICKHOUSE_USER = "default"
CLICKHOUSE_PASS = "admin"
DATABASE = "tictactoe"
```

### Board Size

For 15x15/100x100 modes, adjust the `BOARD_SIZE` constant:
```python
BOARD_SIZE = 15  # or 100 for unlimited space mode
```

---

## 📈 Current Status

### ✅ Fully Functional

- **5x5 Board Mode**: Complete and tested
- **15x15 Board Mode**: Complete and tested
- **Database Integration**: Working
- **Web Interface (15x15)**: Functional
- **Console Interface**: Functional
- **AI Decision Making**: Optimized and working

### 🚧 In Development

- **100x100 Board Mode**: 
  - AI logic implemented in `statistic_ai_100_x_100.py`
  - Web interface in `app_v1_1.py`
  - **Status**: Still being refined and tested
  - **Issues**: May have edge case handling problems, performance optimizations needed

### 🔮 Future Enhancements

- Performance optimization for large boards
- Caching mechanisms for frequently queried board states
- Machine learning integration for move prediction
- Multiplayer support
- Game replay and analysis features

---

## 🧪 Testing

### Test Database Connection

```python
python -c "from statistic_ai import execute_query; print(execute_query('SELECT 1'))"
```

### Test AI Logic

Run AI vs AI mode to test decision making:
```bash
python statistic_ai.py
# Select option 2
```

### Verify Data Integrity

```bash
python ingest.py --verify
```

---

## 📝 Technical Details

### Symmetry Transformations

The project uses 8 symmetry transformations to normalize board states:
- Identity
- Rotations: 90°, 180°, 270°
- Reflections: Horizontal, Vertical, Main Diagonal, Anti-Diagonal

This reduces database size by ~8x while maintaining query accuracy.

### Query Optimization

- Connection pooling for database queries
- Parallel query execution where possible
- Canonical form caching (implicit through normalization)

### Performance Considerations

- **5x5 Mode**: Fast (< 1 second per move)
- **15x15 Mode**: Moderate (1-3 seconds per move)
- **100x100 Mode**: Slower (5-10+ seconds per move) - optimization needed

---

## 🐛 Known Issues

1. **100x100 Mode**: 
   - May have coordinate mapping issues
   - Performance degradation with large boards
   - Edge case handling incomplete

2. **Database Queries**:
   - Some board states may not have data (returns 0 matches)
   - Fallback to random move when no data available

3. **Web Interface**:
   - No undo functionality in 100x100 mode
   - Limited error handling for network issues

---

## 📚 Dependencies

- `clickhouse-connect>=0.7.16`: ClickHouse database client
- `python-dotenv>=1.0.1`: Environment variable management
- `typer>=0.12.3`: CLI framework
- `rich>=13.9.4`: Terminal formatting
- `requests>=2.31.0`: HTTP requests
- `flask`: Web framework (not in requirements.txt, should be added)
- `numpy`: Numerical operations (not in requirements.txt, should be added)

---

## 👥 Contributing

When contributing to this project:

1. Test your changes with both 5x5 and 15x15 modes
2. Verify database queries are optimized
3. Update this README if adding new features
4. Document any new AI logic or algorithms

---

## 📄 License

[Specify license if applicable]

---

## 🙏 Acknowledgments

- ClickHouse for the high-performance database
- Flask for the web framework
- All contributors to the project

---

## 📞 Support

For issues or questions:
- Check existing issues in the repository
- Review the code comments for implementation details
- Test with smaller board sizes first (5x5) before moving to larger boards

---

**Last Updated**: [Current Date]
**Version**: 1.0
**Status**: Active Development

