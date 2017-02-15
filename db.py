from mysql.connector import MySQLConnection, Error
import json, sys, traceback, FacebookAPI as FB, HN_API as HN
from datetime import datetime
from flask import current_app as app

HOST = 'us-cdbr-iron-east-04.cleardb.net'
USERNAME = 'b3333c6f779dde'
PASSWORD = 'b10bfad4'
DB = 'heroku_72ea7ac5f998832'

def create_user(user_id, user):
    query = "INSERT INTO users " \
            "(facebook_user_id, first_name, last_name, profile_pic, locale, timezone, gender, last_seen, created_at) " \
            "VALUES "\
            "(%s,%s,%s,%s,%s,%s,%s,%s,%s)"
    timestamp = datetime.strftime(datetime.now(),"%Y-%m-%d %H:%M:%S")
    args = (user_id, user['first_name'],user['last_name'],user['profile_pic'],user['locale'],user['timezone'],user['gender'],"1970-01-01 00:00:00",timestamp)
    
    try:
        conn = MySQLConnection(host=HOST,database=DB,user=USERNAME,password=PASSWORD)
        cursor = conn.cursor()
        cursor.execute(query, args) 
        conn.commit()

    except Error as error:
        print(error)
 
    finally:
        cursor.close()
        conn.close()

def get_user(user_id):
    query = "SELECT * FROM users WHERE facebook_user_id=%s"
    args = (user_id,)
    try:
        conn = MySQLConnection(host=HOST,database=DB,user=USERNAME,password=PASSWORD)
        cursor = conn.cursor()
        cursor.execute(query, args)

        row = cursor.fetchone()
        # Sample return (100, 1, u'21', u'2412', u'2', u'1', u'1', u'1', datetime.datetime(2017, 2, 10, 5, 21, 32), None)
        if row is None:
            user_fb = FB.get_user_fb(app.config['PAT'], user_id)
            create_user(user_id, user_fb)

        else:
            user_fb = {
                "facebook_user_id": row[1],
                "first_name": row[2],
                "last_name": row[3],
                "profile_pic": row[4],
                "locale": row[5],
                "timezone": row[6],
                "gender": row[7],
                "last_seen": row[8], # datetime.strptime
                "created_at": row[9]
            }
        # Make this an object here --> user['first_name']
        return user_fb

    except Exception, e:
        print e
        traceback.print_exc()

    finally:
        cursor.close()
        conn.close()

def update_user(user_id, field, value):
    query = "UPDATE users "\
            "SET %s = %s " \
            "WHERE facebook_user_id = %s "
    data = (field, value, user_id)
    try:
        conn = MySQLConnection(host=HOST,database=DB,user=USERNAME,password=PASSWORD)
        cursor = conn.cursor()
        cursor.execute(query, data)
        conn.commit()
    
    except Exception, e:
        print(e)
        traceback.print_exc()


    finally:
        cursor.close()
        conn.close()

def get_users_with_subscriptions(subscription_keyword):
    pass

def get_daily_subscription():
    cached = get_cached_daily_subscription()
    if cached is not None:
        return json.loads(cached[0])
    else:
        news = HN.get_stories()
        news = json.dumps(news)
        # news = [1,2,3]

        query = "INSERT INTO daily_stories " \
            "(date, data) " \
            "VALUES (%s, %s)"
        today = datetime.date(datetime.now())
        args = (today, news)

        try:
            conn = MySQLConnection(host=HOST,database=DB,user=USERNAME,password=PASSWORD)
            cursor = conn.cursor()
            cursor.execute(query, args)
            conn.commit()
            return news

        except Exception, e:
            print(e)
            traceback.print_exc()


        finally:
            cursor.close()
            conn.close()

def get_cached_daily_subscription():
    query = "SELECT data " \
        "FROM daily_stories " \
        "WHERE date=%s"
    today = datetime.strftime(datetime.date(datetime.now()), "%Y-%m-%d")
    args = (today,)

    try:
        conn = MySQLConnection(host=HOST,database=DB,user=USERNAME,password=PASSWORD)
        cursor = conn.cursor()
        cursor.execute(query, args)
        news = cursor.fetchone()
        
        return news

    except Exception, e:
        print(e)
        traceback.print_exc()


    finally:
        cursor.close()
        conn.close()

def get_all_subscriptions(active=True):
    query = "SELECT keyword, GROUP_CONCAT(facebook_user_id) FROM subscriptions " \
            "WHERE active=%s " \
            "GROUP BY keyword"
    args = (active, )
    try:
        conn = MySQLConnection(host=HOST,database=DB,user=USERNAME,password=PASSWORD)
        cursor = conn.cursor()
        cursor.execute(query, args)

        rows = cursor.fetchall()
        # print('Total Row(s):', cursor.rowcount)
        subscriptions = {} # keyword -> users[]
        
        for row in rows:
            users = row[1].split(",")
            subscriptions[row[0]] = users

        return subscriptions

    except Exception, e:
        print(e)
        traceback.print_exc()


    finally:
        cursor.close()
        conn.close()

def get_subscribers_by_keyword(keyword):
    query = "SELECT facebook_user_id FROM subscriptions " \
            "WHERE keyword=%s"
    args = (keyword, )
    try:
        conn = MySQLConnection(host=HOST,database=DB,user=USERNAME,password=PASSWORD)
        cursor = conn.cursor()
        cursor.execute(query, args)

        rows = cursor.fetchall()
        # print('Total Row(s):', cursor.rowcount)
        subscribers = [] 
        
        if rows is not None:
            for row in rows:
                subscribers.append(row[0])

        return subscribers

    except Exception, e:
        print(e)
        traceback.print_exc()


    finally:
        cursor.close()
        conn.close()

def add_subscription(user_id, subscription_keyword):
    update = False
    success = False

    exist_query = """
    SELECT *
    FROM subscriptions
    WHERE facebook_user_id=%s AND keyword=%s
    """
    exist_args = (user_id, subscription_keyword)

    try:
        conn = MySQLConnection(host=HOST,database=DB,user=USERNAME,password=PASSWORD)
        cursor = conn.cursor()
        cursor.execute(exist_query, exist_args) 
        row = cursor.fetchone()
        
        if row is not None:
            update = True
            
        if not update:
            query = "INSERT INTO subscriptions " \
                    "(facebook_user_id, keyword, created_at, updated_at, active) " \
                    "VALUES "\
                    "(%s,%s,%s,%s,1)"
            # timestamp = datetime.strftime(datetime.now(), "%Y-%m-%d %H:%M:%S")
            args = (user_id, subscription_keyword, datetime.now(), datetime.now())
        else:
            query = "UPDATE subscriptions "\
                "SET active = 1 " \
                "WHERE facebook_user_id = %s AND keyword = %s"
            args = (user_id, subscription_keyword)

        cursor.execute(query, args) 
        conn.commit()
        success = True

    except Exception, e:
        print e
        traceback.print_exc()
 
    finally:
        cursor.close()
        conn.close()
        return success

def remove_subscription(user_id, subscription_keyword):
    success = False
    query = "UPDATE subscriptions "\
            "SET active = 0 " \
            "WHERE facebook_user_id = %s AND keyword = %s"
    args = (user_id, subscription_keyword)

    try:
        conn = MySQLConnection(host=HOST,database=DB,user=USERNAME,password=PASSWORD)
        cursor = conn.cursor()
        cursor.execute(query, args) 
        conn.commit()
        success = True

    except Exception, e:
        print e
        traceback.print_exc()
 
    finally:
        cursor.close()
        conn.close()
        return success

def update_last_seen(user_id):
    now = datetime.now()
    timestamp = datetime.strftime(now,"%Y-%m-%d %H:%M:%S")
    update_user(user_id, 'last_seen', timestamp)



"""
db heroku_72ea7ac5f998832
mysql://b3333c6f779dde:b10bfad4@us-cdbr-iron-east-04.cleardb.net/heroku_72ea7ac5f998832?reconnect=true
"""