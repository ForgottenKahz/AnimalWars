from gevent import monkey
monkey.patch_all()


import random
import json
import pprint
import time
import uuid
from threading import Thread
from flask import Flask, render_template, session, request
from flask.ext.socketio import SocketIO, emit, join_room, leave_room



# from flask.ext.sqlalchemy import SQLAlchemy

app = Flask(__name__)
#app.config.from_object('app.config')
app.debug = True
app.config['SECRET_KEY'] = 'secret!'
app.secret_key = 'secret!'
socketio = SocketIO(app)
thread = None
num_clients  = 0

character_images = ['/static/cat.jpg','/static/bird.jpg','/static/cow.png','/static/wolf.jpg','/static/shark.jpg']

current_games = {}
player_queue = []
connected_clients = {}


class Game:
    def __init__(self,player1,player2,gameid,gamemap):
        self.player1 = player1
        self.player2 = player2
        self.gameid = gameid
        self.gamemap = gamemap
        self.total_nodes = 30
        self.explored_nodes = 0
        self.unexplored_nodes = []
        self.turn = 1

class Client:
    def __init__(self,clientId):
        self.name = ''
        self.character = ''
        self.picture=''
        self.opponentid = ''
        self.gameid = ''
        self.id = clientId
        self.points = 0

def background_thread():
    """Example of how to send server generated events to clients."""
    count = 0
    while True:
        time.sleep(10)
        count += 1
        socketio.emit('my response',
                      {'data': 'Server generated event', 'count': count},
                      namespace='/test')


# db = SQLAlchemy(app)

def createNetwork(numNodes):
    maxWeight = 100
    maxConnections = 3
    nodes = []
    edges = []
    nodeids = []
    for i in range(1,numNodes+1):
        nodeWeight = random.randint(1, maxWeight)
        id = "n"+str(i)
        nodeids.append(id)
        if i==1:
            nodeData = {'id': id, 'points': nodeWeight, 'bar': 1, 'baz': 2,'isplayer':True, 'whichplayer':'player1', 'group': "nodes", 'explored': False}
        elif i==2:
            nodeData = {'id': id, 'points': nodeWeight, 'bar': 1, 'baz': 2,'isplayer':True,'whichplayer':'player2', 'group': "nodes", 'explored': False}
        else:            
            nodeData = {'id': id, 'points': nodeWeight, 'bar': 1, 'baz': 2,'isplayer':False, 'whichplayer':'none','group': "nodes", 'explored': False}
        newNode = {"data": nodeData}
        nodes.append(newNode)
    

    for i in range(1,numNodes+1):
        numConnections = random.randint(1, maxConnections)
        currentId = 'n'+str(i)

        # this is for each connection for the current node.
        for j in range(1,maxConnections+1):
            connectToNode = random.randint(1, numNodes)
            connectToNodeId = 'n'+str(connectToNode)
            id = currentId+'-'+connectToNodeId
            weight = 1
            source = currentId
            target = connectToNodeId
            connectionNodeData = {"id": id, "weight": weight, 'group': "edges", "source": source, "target": target}
            edgesRecord = {"data": connectionNodeData}
            edges.append(edgesRecord)

    nodeData = {'id': 'player1','group': "nodes"}
    newNode = {"data": nodeData}
    nodes.append(newNode)

    nodeData = {'id': 'player2','group': "nodes"}
    newNode = {"data": nodeData}
    nodes.append(newNode)
    

    elements = {"nodes": nodes, "edges": edges}
    elements = json.dumps(elements, indent=2, separators=(',', ': '))
    return elements,nodeids


@app.route('/')
def index():
    #print elements
    global thread
    if thread is None:
        thread = Thread(target=background_thread)
        thread.start()
    return render_template('chooseanimal.html')

@app.route('/getnetwork/<numnodes>')
def get_network(numnodes):
    elements = createNetwork(int(numnodes))
    return elements

@app.route('/login/<username>/<character>',methods= ['GET','POST'])
def get_username(username,character):
    print username + " is connected"+ " with character "+ character
    return render_template('index.html',username=username,character = int(character))


@socketio.on('my info', namespace='/test')
def test_message(message):
    print message['username']
    char1 = message['character']
    charimage = character_images[int(char1)]
    emit('my response', {'mypictureurl': charimage},room=session['id'])

@socketio.on('username created', namespace='/test')
def test_message(message):
    print message['username']
    session['username'] = message['username']
   # emit('recieved username', {'data': message['data'], 'count': session['receive_count']})

@socketio.on('send move', namespace='/test')
def send_move(message):
    print "got the mesages"
    destinationNode =  message['destination']
    playertype = message['playertype']  
    profit = int(message['profit'])
    totalPoints = message['totalpoints']  
    thisClient = connected_clients[session['id']]
    thisClient.points += profit
    current_game = thisClient.gameid

    thisGame = current_games[current_game]
    if destinationNode in thisGame.unexplored_nodes:
        thisGame.unexplored_nodes.remove(destinationNode)
    print "unexplored nodes left = ",len(thisGame.unexplored_nodes)

    print "sent move",playertype,destinationNode   
    emit('recieve move', {'playertype': playertype, 'destination':destinationNode,'opponentpoints':totalPoints,'profit':profit},room=thisClient.opponentid)
    
    if(len(thisGame.unexplored_nodes)>0):
        emit ('my turn',{'data': 'its my turn'},room = thisClient.opponentid)
        emit ('their turn',{'data': 'its your turn '},room =thisClient.id)
    else:
        player1 = thisGame.player1
        player2 = thisGame.player2
        if player1.points>player2.points:
            emit ('player won',{'data': 'congrats you won'},room =player1.id)
            emit ('player lost',{'data': 'congrats you lost'},room =player2.id)            
        elif player2.points>player1.points:
            emit ('player won',{'data': 'congrats you won'},room =player2.id)
            emit ('player lost',{'data': 'congrats you lost'},room =player1.id)
        else:    
            emit ('tie game',{'data': 'tie game'},room =player1.id)
            emit ('tie game',{'data': 'tie game'},room =player2.id)



@socketio.on('ready to play', namespace='/test')
def ready_to_play(message):
    myClient = connected_clients[session['id']] # get my client
    current_game = myClient.gameid              # get the game this client is playing ins id
    
    thisGame = current_games[current_game] # get the actual game object

    emit ('my turn',{'data': 'its my turn'},room = thisGame.player1.id)
    emit ('their turn',{'data': 'its your turn '},room = thisGame.player2.id)
    
   # emit('recieved username', {'data': message['data'], 'count': session['receive_count']})

@socketio.on('player info', namespace='/test')
def test_message(message):
    session['username'] = message['username']
    session['character'] = message['character']
    charurl = character_images[int(message['character'])]
    oppid = connected_clients[session['id']].opponentid
    emit('opponent info', {'opponentid': message['username'], 'opponentcharacter':session['character'], 'characterurl':  charurl},room=oppid)



@socketio.on('special event', namespace='/test')
def test_message(message):
    session['receive_count'] = session.get('receive_count', 0) + 1
    #for sessid,socket in request.namespace.server.sockets.items():
     #   if socket['/test'].session['id'] 
    emit('my response',
         {'data': message['data'], 'count': session['receive_count']})


@socketio.on('my broadcast event', namespace='/test')
def test_message(message):
    session['receive_count'] = session.get('receive_count', 0) + 1
    emit('my response',
         {'data': message['data'], 'count': session['receive_count']},
         broadcast=True)


@socketio.on('join', namespace='/test')
def join(message):
    join_room(message['room'])
    session['receive_count'] = session.get('receive_count', 0) + 1
    emit('my response',
         {'data': 'In rooms: ' + ', '.join(request.namespace.rooms),
          'count': session['receive_count']})

@socketio.on('joingame', namespace='/test')
def join(message):
    session['gameid'] = message['gameid']


@socketio.on('leave', namespace='/test')
def leave(message):
    leave_room(message['room'])
    session['receive_count'] = session.get('receive_count', 0) + 1
    emit('my response',
         {'data': 'In Rooms' + ', '.join(request.namespace.rooms),
          'count': session['receive_count']})

@socketio.on('get num clients', namespace='/test')
def get_numclients(message):
    global num_clients
    session['receive_count'] = session.get('receive_count', 0) + 1
    emit('my response',
         {'data': num_clients})


@socketio.on('my room event', namespace='/test')
def send_room_message(message):
    session['receive_count'] = session.get('receive_count', 0) + 1
    emit('my response',
         {'data': message['data'], 'count': session['receive_count']},
         room=message['room'])


@socketio.on('goodbye', namespace='/test')
def goodbye(message):
    if session['id'] in player_queue:
        player_queue.remove(session['id'])
    current_client = connected_clients[session['id']]
    emit('OpponentLeftGame', {'data': 'OpponentLeftGame','opponentid': session['id']},room=current_client.opponentid)
    print('Client disconnected')



@socketio.on('connect', namespace='/test')
def test_connect():

    # establish globals
    global num_clients 
    global player_queue
    global connected_clients

    # incriment the number of connected clients
    num_clients+=1
    
    # create a unique user id
    session['id'] = str(uuid.uuid4())

    new_client = Client(session['id'])

    connected_clients[session['id']] = new_client

    session['gameid'] = 'null'

    # because we don't have multicast support we need to join a room named the client id
    join_room(session['id'])
    

    # check if there is a player waiting for a partner..
    if len(player_queue)>0 and player_queue[0] != session['id']:
        opponent_id = player_queue[0]
        
        # lets make a new game
        new_game_id = str(uuid.uuid4())
        
        # lets get the game map
        elements,nodeslist = createNetwork(30)

        # lets create a name game
        new_game = Game(opponent_id,session['id'],new_game_id,elements)        
        new_game.unexplored_nodes = nodeslist

        # lets addd this game to the current games list
        current_games[new_game_id] = new_game

        # here we initialize the client class data
        myclient = connected_clients[session['id']]
        theirclient = connected_clients[opponent_id]
        
        # add the game id to both clients
        myclient.gameid = new_game_id
        theirclient.gameid = new_game_id
        
        myclient.opponentid = opponent_id
        theirclient.opponentid = session['id']

        # lets add the client objects to the game object 

        new_game.player1 = theirclient
        new_game.player2 = myclient
        player_queue.remove(opponent_id)

        emit('ConnectedToGame', {'data': 'Client Connected To Game', 'gameid': new_game_id,'playertype':'player2','clientid':session['id'],'gamemap':elements})
        emit('ConnectedToGame', {'data': 'Client Connected To Game', 'gameid': new_game_id,'playertype':'player1', 'clientid':session['id'],'gamemap':elements},room=opponent_id)
        
    else:
        player_queue.append(session['id'])
        emit('ConnectedToPlayerQueue', {'data': 'Client Added To Player Queue','clientid':session['id']})


@socketio.on('disconnect', namespace='/test')
def test_disconnect():
    if session['id'] in player_queue:
        player_queue.remove(session['id'])
    #opponentid = 
    current_client = connected_clients[session['id']]
    emit('OpponentLeftGame', {'data': 'OpponentLeftGame','opponentid': session['id']},room=current_client.opponentid)
    print('Client disconnected')


@app.errorhandler(404)
def not_found(error):
  return render_template('404.html'), 404


if __name__ == '__main__':
    socketio.run(app,'127.0.0.1',5000)

#from app.core.views import mod as core
#app.register_blueprint(core)

# Later on you'll import the other blueprints the same way:
#from app.comments.views import mod as commentsModule
#from app.posts.views import mod as postsModule
#app.register_blueprint(commentsModule)
#app.register_blueprint(postsModule)

