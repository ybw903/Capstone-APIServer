from flask import Flask,request,jsonify,g,redirect
from flaskext.mysql import MySQL
import bcrypt
import jwt
from functools import wraps
from datetime import datetime, timedelta
from pyfcm import FCMNotification
from config import config, FCM_KEY
import time

app = Flask(__name__)

mysql = MySQL()
app.config['MYSQL_DATABASE_USER']=config['MYSQL_DATABASE_USER']
app.config['MYSQL_DATABASE_PASSWORD']=config['MYSQL_DATABASE_PASSWORD']
app.config['MYSQL_DATABASE_DB']=config['MYSQL_DATABASE_DB']
app.config['MYSQL_DATABASE_HOST']=config['MYSQL_DATABASE_HOST']
app.config['JWT_SECRET_KEY'] = config['JWT_SECRET_KEY']
algorithm = 'HS256'
mysql.init_app(app)

@app.route("/hello")
def home():
    return "hello!"

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        access_token = request.headers.get("Authorization")
        if access_token is not None:
            try:
                payload = jwt.decode(access_token, app.config['JWT_SECRET_KEY'],"HS256")
            except jwt.ExpiredSignatureError:
                return jsonify({'message': 'Signature expired'}), 403
            except jwt.InvalidTokenError:
                payload = None

            if payload is None:
                print("maybe payloade expired")
                return jsonify({'message': 'Invalid token'}), 403

            print(payload)
            user_name = payload["user_name"]
            g.user_name = user_name
        else:
            return "no"
        return f(*args, **kwargs)
    return decorated_function


@app.route("/users/sign-up", methods=["POST"])
def sign_up():
    new_user = request.json
    new_user['password'] = bcrypt.hashpw(new_user['password'].encode('UTF-8'), bcrypt.gensalt()).decode('utf-8')
    conn = mysql.connect()
    cursor = conn.cursor()

    user_name = new_user["username"]
    password = new_user["password"]

    sql = "select user_name from user_info " + "where user_name = '" + user_name + "';"
    print(sql)
    cursor.execute(sql)
    col = cursor.fetchone()

    # 아이디 중복 방지
    if(col!= None):
        return jsonify({'message': 'id duplicate'}),403
    sql = "INSERT INTO user_info (user_name, password) VALUES('%s', '%s')"%(user_name, password)
    print(sql)
    cursor.execute(sql)
    conn.commit()
    conn.close()
    # 예외처리 추가필요
    return jsonify({'message':'created'}), 201


@app.route("/users/login", methods=["POST"])
def login():
    user_info = request.json
    print(user_info)
    user_name = user_info["username"]
    password = user_info["password"].encode('utf-8')

    conn = mysql.connect()
    cursor = conn.cursor()

    sql = "select password, user_name, car_plate, email from user_info " + "where user_name = '"+user_name+"';"
    cursor.execute(sql)

    cols = cursor.fetchone()
    conn.close()
    if(cols==None): # err1 잘못된 아이디
        return jsonify({'Message': 'Login Failed'}), 400
    else:
        check = bcrypt.checkpw(password,cols[0].encode('utf-8'))
        print(check)
        if(check):
            payload={
                "user_name": user_name,
                "exp": datetime.utcnow()+timedelta(seconds=60*60*24)
            }
            token = jwt.encode(payload, app.config['JWT_SECRET_KEY'], "HS256")
            return jsonify({
                'access_token': token.decode("UTF-8"),
                'user_info': {'user_name': cols[1], 'car_plate': cols[2], 'email': cols[3]}

            }), 200
        else: # err1 잘못된 비밀번호
            return jsonify({'Message': 'Login Failed'}), 400

@app.route("/users", methods=['POST'])
@login_required
def updateUser():
    conn = mysql.connect()
    cursor = conn.cursor()

    update_info = request.json
    print(update_info)
    username = update_info["username"]
    car_plate = update_info["car_plate"]
    email = update_info["email"]

    sql = "UPDATE user_info SET car_plate = '%s', email ='%s' WHERE user_name = '%s';"%(car_plate,email, username)
    print(sql)
    cursor.execute(sql)
    conn.commit()

    sql = "select user_name, car_plate, email from user_info " + "where user_name = '" + username + "';"
    cursor.execute(sql)
    cols = cursor.fetchone()
    conn.close()

    return jsonify({"Message": "success", 'user_info': {'user_name': cols[0], 'car_plate': cols[1], 'email': cols[2]}}), 200

@app.route("/users/token", methods =['POST'])
def tokenUpload():
    conn = mysql.connect()
    cursor = conn.cursor()
    tokenInfo = request.json
    user_name = tokenInfo['user_name']
    token = tokenInfo['token']
    sql = "select * from userFCMKey where user_name = '%s'"%user_name
    cursor.execute(sql)
    cols = cursor.fetchone()
    if cols == None:
        sql = "INSERT INTO userFCMKey (user_name, FCMtoken) VALUES ('%s', '%s')"%(user_name, token)
        cursor.execute(sql)
        conn.commit()
        conn.close()
        return jsonify({"Message": "created"}),201
    sql = "Update userFCMKey SET FCMtoken = '%s' WHERE (user_name) = ('%s')"%(token, user_name)
    cursor.execute(sql)
    conn.commit()
    conn.close()
    return jsonify({"Message": "updated"}), 200

@app.route("/users/<username>")
@login_required
def getUser(username):
    conn = mysql.connect()
    cursor = conn.cursor()
    print(username)
    sql = "select user_name, car_plate, email from user_info " + "where user_name = '"+username+"';"
    cursor.execute(sql)
    cols = cursor.fetchone()
    conn.close()
    print(cols)
    if(cols==None):
        return jsonify({'Message': 'failed load info'}), 400
    return jsonify({'Message': 'success', 'user_info': {'user_name': cols[0], 'car_plate': cols[1], 'email': cols[2]}}), 200

@app.route("/userfavorite", methods=['POST'])
@login_required
def AddUserFavorite():
    add_data = request.json
    username = add_data['username']
    idpark = add_data['idpark']

    conn = mysql.connect()
    cursor = conn.cursor()

    sql = "INSERT INTO user_favorite_park (username, idpark) VALUES('%s', '%s');"%(username, idpark)
    cursor.execute(sql)
    conn.commit()
    conn.close()
    return jsonify({'message': 'success'})

@app.route("/userfavorite/<username>/<idpark>", methods=['DELETE'])
@login_required
def DelUserFavorite(username, idpark):
    conn = mysql.connect()
    cursor = conn.cursor()

    sql = "DELETE FROM user_favorite_park WHERE username = '%s' AND idpark = '%s';"%(username, idpark)
    cursor.execute(sql)
    conn.commit()
    conn.close()
    return jsonify({'message': 'success'})

@app.route("/userfavorite/<username>")
@login_required
def getUserFavorite(username):
    conn = mysql.connect()
    cursor = conn.cursor()

    sql = "SELECT * FROM user_favorite_park ufp, parking_list_info pli where ufp.idpark = pli.info_id AND username = '%s'"%username
    print(sql)
    cursor.execute(sql)
    rows = cursor.fetchall()

    results = []
    for row in rows:
        results.append(
            {'id': row[3], 'name': row[4], 'p_class': row[5], 'info_type': row[6], 'address': row[7], 'avail': row[8],
             'day_type': row[9], 'op_day': row[10], 'bill_tpye': row[11], 'lat': row[12], 'lng': row[13], 'tel': row[14],
             'default_bill': row[15], 'add_bill': row[16], 'last_update': row[17], 'week_day_start': row[18],
             'week_day_end': row[19], 'week_end_start': row[20], 'week_end_end': row[21]})

    sql = "SELECT * FROM user_favorite_park ufp, parking_list pl where ufp.idpark = pl.idparking AND username = '%s';"%username

    cursor.execute(sql)
    rows = cursor.fetchall()
    results2=[]
    for row in rows:
        results2.append({'id': str(row[3]), 'name': row[4], 'lat': row[5], 'lng': row[6], 'avail': row[7], 'op_day': row[8],
                         'default_bill': row[9],
                         'add_bill': row[10], 'week_day_start': row[11], 'week_day_end': row[12],
                         'week_end_start': row[13], 'week_end_end': row[14], 'tel': row[15], 'p_class': row[16], 'address': row[17]})
    conn.close()
    print(results)
    return jsonify({'statusCode':'200', 'status': 'OK', 'results': results, 'results2' : results2})

@app.route("/parks/<lat>/<lng>/<dist>")
def parkinglist(lat, lng,dist):
    conn = mysql.connect()
    cursor = conn.cursor()
    # sql = "select * from parking_list " + "where (lat,lng) = ('%s', '%s') ;"%(lat, lng)
    # 프로시저 처리?

    sql = "SELECT *, (6371*acos(cos(radians('%s'))*cos(radians(info_lat))*cos(radians(info_lng)" \
          "-radians('%s'))+sin(radians('%s'))*sin(radians(info_lat))))" \
          "AS distance FROM parking_list_info HAVING distance <= '%s' ORDER BY distance "%(lat, lng, lat, dist)

    cursor.execute(sql)
    rows = cursor.fetchall()

    results = []
    for row in rows:
        results.append({'id': row[0], 'name': row[1], 'p_class': row[2], 'info_type': row[3], 'address': row[4], 'avail': row[5],
                    'day_type':row[6], 'op_day': row[7], 'bill_tpye': row[8],  'lat': row[9], 'lng': row[10], 'tel': row[11],
                        'default_bill': row[12], 'add_bill': row[13], 'last_update': row[14], 'week_day_start':row[15],
                        'week_day_end': row[16], 'week_end_start': row[17], 'week_end_end': row[18]})

    results2 = []
    sql = "SELECT *, (6371*acos(cos(radians('%s'))*cos(radians(lat))*cos(radians(lng)" \
          "-radians('%s'))+sin(radians('%s'))*sin(radians(lat))))" \
          "AS distance FROM parking_list HAVING distance <= '%s' ORDER BY distance " % (lat, lng, lat, dist)
    cursor.execute(sql)
    rows = cursor.fetchall()
    for row in rows:
        results2.append({'id':row[0], 'name': row[1], 'lat': row[2], 'lng': row[3], 'avail':row[4], 'op_day':row[5],'default_bill':row[6],
                         'add_bill': row[7], 'week_day_start': row[8], 'week_day_end':row[9],
                         'week_end_start': row[10], 'week_end_end': row[11], 'tel': row[12], 'p_class': row[13]})

    conn.close()
    if(len(results)+len(results2)>80):
        return jsonify({'statusCode':'200', 'status': 'OK', 'len': len(results)+len(results2), 'large': True}), 200
    return jsonify({'statusCode':'200', 'status': 'OK', 'results': results, 'results2' : results2,'len': len(results)+len(results2),'large': False}), 200

@app.route("/booking/users/<name>")
@login_required
def get_booking(name):
    print(name)
    conn = mysql.connect()
    cursor = conn.cursor()
    sql = "select * from reservation where (user_name) = ('%s');" % (name)

    cursor.execute(sql)
    rows = cursor.fetchall()
    results = []
    print(rows)
    for row in rows:
        print(type(row[5]))
        print(row[5])
        res_time = datetime.strftime(row[5],'%Y-%m-%d\n%H시 %M분')
        results.append(
            {'id': row[0], 'parking_info': {'parking_id':row[2], 'parking_name':row[3]}, 'carplate':row[4], 'date':  res_time, 'booking_state': row[7]}
        )
    conn.close()
    return jsonify(results), 200

@app.route("/booking/cancle", methods=['POST'])
@login_required
def cancleBooking():
    cancle_info = request.json
    idreservation = cancle_info['idreservation']

    conn = mysql.connect()
    cursor = conn.cursor()

    sql = "Update reservation SET state = 3 WHERE (idreservation) = ('%s')"%(idreservation)
    cursor.execute(sql)
    conn.commit()

    # sql = "Update parking_list SET cur_avail = cur_avail+1 WHERE (idparking) = ('%s')"%(idparking)
    # cursor.execute(sql)
    # conn.commit()
    conn.close()
    # 에러 추가
    return jsonify({'result': 'OK'}), 200

@app.route("/booking", methods=["POST"])
@login_required
def requestbooking():
    booking_data = request.json
    user_name = booking_data["username"]
    car_plate = booking_data["car_plate"]
    parking_id = booking_data["parking_id"]
    parking_name = booking_data["parking_name"]
    startDate = booking_data["startDate"]
    endDate = booking_data["endDate"]
    cost = booking_data["cost"]

    startTime = int(startDate.split(" ")[1].split(":")[0])
    endTime = int(endDate.split(" ")[1].split(":")[0])
    print(startTime)
    print(endTime)
    conn = mysql.connect()
    cursor = conn.cursor()

    # 예약내역 존재 시 예약 실패
    sql = "select idreservation from reservation where user_name= '"+ user_name +"' AND state < "+"2;"
    print(sql)
    cursor.execute(sql)
    cols = cursor.fetchone()
    if(cols!=None):
        return jsonify({'Message': 'alredeay booking'}),400

    # 예약 테이블에 집어 넣기 전에 주차가능 여부 확인
    # 주차장 공간
    sql = "select tot_avail from parking_list where (idparking) = ('%s') ;"%(parking_id)
    print(sql)
    cursor.execute(sql)
    cols = cursor.fetchone()
    tot_avail = cols[0]

    # 현재 예약된 공간
    sql = '''select count(*) from reservation where parking_id = '%s' 
    AND (
    HOUR(end_date)>%d OR HOUR(start_date)<%d 
    OR (%d<=HOUR(start_date)AND %d<=HOUR(end_date))
    OR (HOUR(end_date)<%d AND state=1)
    );
    '''%(parking_id,startTime,endTime, startTime, endTime,startTime)
    print(sql)
    cursor.execute(sql)
    cur_used = cursor.fetchone()[0]

    cur_avail = tot_avail-cur_used
    print(cur_avail)
    if(cur_avail<0):
        return jsonify({'Message:': 'park full'}), 400

    # 예약 테이블 변경
    sql ='''
    INSERT INTO reservation (user_name, parking_id, parking_name, start_date, end_date, state, car_plate,cost)
     VALUES('%s', '%s', '%s', '%s', '%s' ,'%d', '%s', '%d');
    '''% (user_name,parking_id,parking_name,startDate, endDate, 0,car_plate,cost)

    # 예약&입차X 0, 예약&입차 1, 나갔을 경우 2, 비정상인 경우 3(취소)
    print(sql)
    cursor.execute(sql)
    conn.commit()
    conn.close()

    return jsonify( {'statusCode' : '200', 'Message': 'booking Success!'}), 200

@app.route("/booking/check-in", methods=['POST'])
def check_in():

    income_info = request.json
    print(income_info)
    idparking = income_info['idparking']
    parking_name = income_info['parking_name']
    car_plate = income_info['car_plate']
    now = income_info['now']

    now_date = '%d-%d-%d %d:%d:%d'%(now[0], now[1], now[2], now[3], now[4], now[5])
    now_hour = now[3]
    conn = mysql.connect()
    cursor = conn.cursor()

    # 예약내역 일치 번호판 조회
    sql = '''
    select idreservation,user_name,start_date,end_date from reservation 
    where (parking_id, car_plate, state) = ('%s', '%s', '%d') 
    AND HOUR(start_date)<= %d AND %d<HOUR(end_date)
    ;'''%(idparking, car_plate, 0, now_hour,now_hour)
    cursor.execute(sql)

    cols = cursor.fetchone()
    # 일치내역 X
    if (cols == None):
        conn.close()
        return jsonify({'Message': 'NoBooking'}), 403

    # 예약테이블 갱신 ()
    sql = "Update reservation SET state = 1 where (idreservation) = ('%s');"%(cols[0])
    cursor.execute(sql)
    conn.commit()

    # 출입기록 삽입
    sql = "INSERT INTO exit_entry (parking_name,username,car_plate,indate,resID) VALUES('%s', '%s', '%s', '%s', '%s');" % (parking_name, cols[1], car_plate, now_date,cols[0])
    print(sql)
    cursor.execute(sql)
    conn.commit()
    conn.close()

    return jsonify({'Message': 'YesBooking'}), 200

def pushNotificatioin(cost, push_tokens):
    push_service = FCMNotification(api_key=FCM_KEY)

    result = push_service.notify_single_device(registration_id=push_tokens, message_title='금액 청구',
                                               message_body=str(cost)+"원 청구되었습니다.")

def getTimeweight(unit):
    return {'일':60*60*60, '시간':60*60, '분':60}[unit]

@app.route("/booking/check-out", methods=['POST'])
def check_out():
    outcome_info = request.json
    # print(outcome_info)
    parking_name = outcome_info['parking_name']
    car_plate = outcome_info['car_plate']
    default_bill_info = outcome_info['default_bill']
    add_bill_info = outcome_info['add_bill']
    now = outcome_info['now']

    now_date = '%d-%d-%d %d:%d:%d'%(now[0], now[1], now[2], now[3], now[4], now[5])

    conn = mysql.connect()
    cursor = conn.cursor()

    # 해당 차량 예약내역 조회(+출입기록 ID)
    sql = '''SELECT id_exit_entry, resID from exit_entry WHERE (parking_name, car_plate, exited) = ('%s', '%s', 0)
    '''%(parking_name, car_plate)

    print(sql)
    cursor.execute(sql)
    cols = cursor.fetchone()
    if(cols == None):
        return jsonify({"Message: Anonymous Car"}),400
    sql = '''SELECT end_date,cost, user_name FROM reservation WHERE idreservation = ('%s')'''%(cols[1])
    cursor.execute(sql)


    # 이용시간 + 금액 계산
    (outPredTime, curCost, user_name) = cursor.fetchone()# 예정출차시간, 금액
    endTime = datetime(now[0],now[1],now[2],now[3],now[4],now[5]) # 실제출차시간

    timeDiff = endTime - outPredTime # 이용시간
    timeDiff_seconds = timeDiff.total_seconds()
    print(timeDiff)
    if(timeDiff_seconds>0):
        add_time =  getTimeweight(add_bill_info['unit'])*add_bill_info['time']
        add_cost = add_bill_info['cost']

        cost = 0

        while timeDiff_seconds > add_time:
            timeDiff_seconds -= add_time
            cost += add_cost

        print(cost)
        curCost+=cost

    print(curCost)
    # sql = "SELECT FCMtoken FROM userFCMKey where user_name = '%s "%user_name
    # print(sql);
    # cursor.execute(sql)
    # token = cursor.fetchone()
    # pushNotificatioin(curCost, token)

    # 출입기록 업데이트
    sql = "UPDATE exit_entry SET outdate = '%s', exited = 1 WHERE (id_exit_entry) = ('%s');"%(now_date, cols[0])
    print(sql)
    cursor.execute(sql)
    conn.commit()

    # 예약종료 업데이트
    sql = "UPDATE reservation SET state = 2, cost = %d WHERE (idreservation) = ('%s');"%(curCost, cols[1])
    print(sql)
    cursor.execute(sql)
    conn.commit()

    conn.close()
    return jsonify({'Message': 'BYE', 'cost': curCost}), 200


if(__name__=='__main__'):
    app.run(debug=True),