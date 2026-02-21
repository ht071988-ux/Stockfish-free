
from flask import Flask, request, jsonify, render_template_string
import chess
import chess.engine
import threading

ENGINE_CMD = "stockfish"

app = Flask(_name_)

board = chess.Board()
board_lock = threading.Lock()
player_color = chess.WHITE
last_check_square = None
last_engine_move_type = "move"   # 🔥 thêm biến này

engine = chess.engine.SimpleEngine.popen_uci(ENGINE_CMD)
engine.configure({
"Threads": 4,
"Hash": 512,
"Skill Level": 20,
"UCI_LimitStrength": False
})

ENGINE_THINK_TIME = 5.0

def engine_play_async():
def task():
global last_check_square, last_engine_move_type

with board_lock:  
        if board.is_game_over():  
            return  

        result = engine.play(board, chess.engine.Limit(time=ENGINE_THINK_TIME))  

        capture = board.is_capture(result.move)  
        castle = board.is_castling(result.move)  

        board.push(result.move)  

        if board.is_check():  
            ks = board.king(board.turn)  
            last_check_square = chess.square_name(ks)  
            last_engine_move_type = "check"  
        elif castle:  
            last_engine_move_type = "castle"  
        elif capture:  
            last_engine_move_type = "capture"  
        else:  
            last_engine_move_type = "move"  

threading.Thread(target=task).start()

@app.route("/")
def index():
return render_template_string(TEMPLATE, fen=board.fen())

@app.route("/set_color", methods=["POST"])
def set_color():
global player_color, last_check_square

color = request.json.get("color")  

with board_lock:  
    board.reset()  
    last_check_square = None  
    player_color = chess.WHITE if color == "white" else chess.BLACK  

if player_color == chess.BLACK:  
    engine_play_async()  

return jsonify({"fen": board.fen()})

@app.route("/reset", methods=["POST"])
def reset():
global last_check_square

with board_lock:  
    board.reset()  
    last_check_square = None  

if player_color == chess.BLACK:  
    engine_play_async()  

return jsonify({"fen": board.fen()})

@app.route("/move", methods=["POST"])
def move():
global last_check_square

data = request.json  
mv = chess.Move.from_uci(data.get("move"))  

with board_lock:  
    if mv not in board.legal_moves:  
        return jsonify({"ok": False})  

    capture = board.is_capture(mv)  
    castle = board.is_castling(mv)  

    board.push(mv)  

    if board.is_check():  
        ks = board.king(board.turn)  
        last_check_square = chess.square_name(ks)  
    else:  
        last_check_square = None  

    if board.turn != player_color:  
        engine_play_async()  

    return jsonify({  
        "ok": True,  
        "fen": board.fen(),  
        "check_square": last_check_square,  
        "capture": capture,  
        "castle": castle  
    })

@app.route("/engine_move")
def engine_move():
with board_lock:
return jsonify({
"fen": board.fen(),
"check_square": last_check_square,
"move_type": last_engine_move_type   # 🔥 thêm cái này
})

@app.route("/legal")
def legal():
square = request.args.get("square")
sq = chess.parse_square(square)
moves = []

with board_lock:  
    for mv in board.legal_moves:  
        if mv.from_square == sq:  
            moves.append(chess.square_name(mv.to_square))  

return jsonify({"moves": moves})

TEMPLATE = """
<!doctype html>

<html>  
<head>  
<meta name="viewport" content="width=device-width,initial-scale=1">  
<style>  
body{background:#000;text-align:center;font-family:sans-serif;}  
#controls{margin:10px;}  
button{padding:8px 14px;border-radius:10px;border:none;cursor:pointer;margin:4px;}  
#board{display:grid;grid-template-columns:repeat(8,1fr);width:min(95vw,520px);margin:20px auto;border-radius:18px;overflow:hidden;}  
.square{aspect-ratio:1/1;display:flex;align-items:center;justify-content:center;position:relative;}  
.light{background:#e6d2b5;}  
.dark{background:#b58863;}  
.piece{width:90%;height:90%;pointer-events:none;}  
.check{box-shadow: inset 0 0 0 3px red;}  
.dot{width:20%;height:20%;background:rgba(0,0,0,0.7);border-radius:50%;position:absolute;}  
</style>  
</head>  
<body>  <div id="controls">  
<button onclick="setColor('white')">Play White</button>  
<button onclick="setColor('black')">Play Black</button>  
<button onclick="resetBoard()">Reset</button>  
</div>  <div id="board"></div>  <audio id="moveSound" src="/static/move-opponent.mp3"></audio>
<audio id="checkSound" src="/static/move-check.mp3"></audio>
<audio id="castleSound" src="/static/castle.mp3"></audio>
<audio id="captureSound" src="/static/capture.mp3"></audio>

<script>  
  
const pieceSVG={  
'p':"https://upload.wikimedia.org/wikipedia/commons/c/c7/Chess_pdt45.svg",  
'r':"https://upload.wikimedia.org/wikipedia/commons/f/ff/Chess_rdt45.svg",  
'n':"https://upload.wikimedia.org/wikipedia/commons/e/ef/Chess_ndt45.svg",  
'b':"https://upload.wikimedia.org/wikipedia/commons/9/98/Chess_bdt45.svg",  
'q':"https://upload.wikimedia.org/wikipedia/commons/4/47/Chess_qdt45.svg",  
'k':"https://upload.wikimedia.org/wikipedia/commons/f/f0/Chess_kdt45.svg",  
'P':"https://upload.wikimedia.org/wikipedia/commons/4/45/Chess_plt45.svg",  
'R':"https://upload.wikimedia.org/wikipedia/commons/7/72/Chess_rlt45.svg",  
'N':"https://upload.wikimedia.org/wikipedia/commons/7/70/Chess_nlt45.svg",  
'B':"https://upload.wikimedia.org/wikipedia/commons/b/b1/Chess_blt45.svg",  
'Q':"https://upload.wikimedia.org/wikipedia/commons/1/15/Chess_qlt45.svg",  
'K':"https://upload.wikimedia.org/wikipedia/commons/4/42/Chess_klt45.svg"  
};  
  
let selected=null;  
let legalMoves=[];  
let currentFen="{{ fen }}";  
let playerColor="white";  
  
function playSound(type){  
let s;  
if(type==="castle") s=document.getElementById("castleSound");  
else if(type==="capture") s=document.getElementById("captureSound");  
else if(type==="check") s=document.getElementById("checkSound");  
else s=document.getElementById("moveSound");  
s.currentTime=0;  
s.play();  
}  
  
function buildMatrix(fen){  
const rows=fen.split(' ')[0].split('/');  
const matrix=[];  
for(let r=0;r<8;r++){  
let row=[];  
for(let ch of rows[r]){  
if(!isNaN(ch)){for(let i=0;i<parseInt(ch);i++)row.push('');}  
else row.push(ch);  
}  
matrix.push(row);  
}  
return matrix;  
}  
  
function drawBoard(fen,checkSquare=null){  
currentFen=fen;  
const boardEl=document.getElementById("board");  
boardEl.innerHTML='';  
const matrix=buildMatrix(fen);  
  
for(let r=0;r<8;r++){  
for(let f=0;f<8;f++){  
  
let row = playerColor==="white" ? r : 7-r;  
let col = playerColor==="white" ? f : 7-f;  
  
const sq=document.createElement("div");  
sq.className="square "+((row+col)%2==0?"light":"dark");  
  
const algebraic=String.fromCharCode(97+col)+(8-row);  
  
if(checkSquare===algebraic)sq.classList.add("check");  
  
const piece=matrix[row][col];  
  
if(piece){  
const img=document.createElement("img");  
img.src=pieceSVG[piece];  
img.className="piece";  
sq.appendChild(img);  
}  
  
if(legalMoves.includes(algebraic)){  
const dot=document.createElement("div");  
dot.className="dot";  
sq.appendChild(dot);  
}  
  
sq.onclick=()=>{  
if(selected){  
const move=selected+algebraic;  
selected=null;  
legalMoves=[];  
fetch("/move",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({move:move})})  
.then(r=>r.json())  
.then(data=>{  
if(data.ok){  
  
let type="move";  
if(data.castle) type="castle";  
else if(data.capture) type="capture";  
else if(data.check_square) type="check";  
  
playSound(type);  
drawBoard(data.fen,data.check_square);  
}  
});  
}else{  
selected=algebraic;  
fetch("/legal?square="+algebraic)  
.then(r=>r.json())  
.then(data=>{  
legalMoves=data.moves;  
drawBoard(currentFen);  
});  
}  
};  
  
boardEl.appendChild(sq);  
}  
}  
}  
  
function setColor(color){  
playerColor=color;  
fetch("/set_color",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({color:color})})  
.then(r=>r.json())  
.then(data=>{  
drawBoard(data.fen,null);  
});  
}  
  
function resetBoard(){  
fetch("/reset",{method:"POST"})  
.then(r=>r.json())  
.then(data=>{  
drawBoard(data.fen,null);  
});  
}  
  
setInterval(()=>{  
fetch("/engine_move")  
.then(r=>r.json())  
.then(data=>{  
if(data.fen !== currentFen){  
playSound(data.move_type);   // 🔥 chỉ thêm dòng này  
drawBoard(data.fen,data.check_square);  
}  
});  
},1000);  
  
drawBoard(currentFen);  
  
</script>  </body>  
</html>  
"""  if name == "main":
app.run(host="0.0.0.0", port=5000)
