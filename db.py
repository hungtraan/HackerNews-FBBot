from mysql.connector import MySQLConnection, Error
import os, json, sys, traceback, FacebookAPI as FB, HN_API as HN
from datetime import datetime
from sets import Set

from flask import current_app as app
import urlparse
import pylibmc


# --------- Setting up MySQL database info ---------
# Register database schemes in URLs.
urlparse.uses_netloc.append('mysql')

DB = {}
try:
    if 'CLEARDB_DATABASE_URL' in os.environ:
        url = urlparse.urlparse(os.environ['CLEARDB_DATABASE_URL'])
        DB['HOST'] = url.hostname
        DB['USERNAME'] = url.username
        DB['PASSWORD'] = url.password
        DB['DB'] = url.path[1:]
        DB['PORT'] = url.port

except Exception:
    print 'Unexpected error:', sys.exc_info()

def get_mysql_connection():
    conn = MySQLConnection(host=DB['HOST'],
        database=DB['DB'],
        user=DB['USERNAME'],
        password=DB['PASSWORD'])
    return conn
# /--------- END Setting up database info ---------

# --------- Setting up Memcached ---------

Memcached = {}

def get_memcached_connection():
    Memcached['servers'] = os.environ.get('MEMCACHIER_SERVERS', '').split(',')
    Memcached['user'] = os.environ.get('MEMCACHIER_USERNAME', '')
    Memcached['password'] = os.environ.get('MEMCACHIER_PASSWORD', '')
    
    MemcachedClient = pylibmc.Client(Memcached['servers'], binary=True,
                        username=Memcached['user'], password=Memcached['password'],
                        behaviors={
                          # Faster IO
                          "tcp_nodelay": True,

                          # Keep connection alive
                          'tcp_keepalive': True,

                          # Timeout for set/get requests
                          'connect_timeout': 2000, # ms
                          'send_timeout': 750 * 1000, # us
                          'receive_timeout': 750 * 1000, # us
                          '_poll_timeout': 2000, # ms

                          # Better failover
                          'ketama': True,
                          'remove_failed': 1,
                          'retry_timeout': 2,
                          'dead_timeout': 30,
                        })
    return MemcachedClient

MemcachedClient = get_memcached_connection()
# --------- Setting up Memcached ---------


def create_user(user_id, user):
    query = "INSERT INTO users " \
            "(facebook_user_id, first_name, last_name, profile_pic, locale, timezone, gender, last_seen, created_at) " \
            "VALUES "\
            "(%s,%s,%s,%s,%s,%s,%s,%s,%s)"
    timestamp = datetime.strftime(datetime.now(),"%Y-%m-%d %H:%M:%S")
    args = (user_id, user['first_name'],user['last_name'],user['profile_pic'],user['locale'],user['timezone'],user['gender'],"1970-01-01 00:00:00",timestamp)
    
    try:
        conn = get_mysql_connection()
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
        conn = get_mysql_connection()
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
        conn = get_mysql_connection()
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

def get_daily_top_stories(limit=0):
    stories = None
    stories = get_cached_daily_subscription_memcached()
    if stories is not None:
        if limit:
            return stories[:limit]
        else:
            return stories

    # Cached stories does not exist, get stories from HN and set in cache
    else:
        news = HN.get_stories()
        cache_today_stories_memcached(news)
        
        if limit:
            return news[:limit]
        else:
            return news
        # return news

def get_stories_from_search(keyword, search_type="top", limit=0):
    # @search_type: values either "top" or "recent"
    keyword_with_type = keyword + "_%s"%(search_type)

    stories = None
    stories = get_cached_search_result(keyword_with_type)
    if stories is not None:
        if limit:
            return stories[:limit]
        else:
            return stories

    # Cached stories does not exist, get stories from HN and set in cache
    else:
        stories = HN.stories_from_search(keyword, search_type)
        cache_stories(keyword_with_type, stories)

        if limit:
            return stories[:limit]
        else:
            return stories
        
def get_cached_search_result(keyword):
    try:
        return MemcachedClient.get(keyword)
        
    except Exception, e:
        print(e)
        traceback.print_exc()

def cache_today_stories_mysql(news=None):
    #@input: news = list of dicts
    if news is None:
        news = HN.get_stories()

    news_insert = json.dumps(news)
    query = "INSERT INTO daily_stories " \
        "(date, data) " \
        "VALUES (%s, %s)"
    today = datetime.date(datetime.now())
    args = (today, news_insert)

    try:
        conn = get_mysql_connection()
        cursor = conn.cursor()
        cursor.execute(query, args)
        conn.commit()

    except Exception, e:
        print(e)
        traceback.print_exc()

    finally:
        cursor.close()
        conn.close()

def cache_today_stories_memcached(news=None, story_type='top'):
    if news is None:
        news = HN.get_stories()
        
    try:
        key = "today_stories_%s"%(story_type)
        MemcachedClient.set(key, news, time=2000) # 2000s - cache expiry time in SECONDS
    except Exception, e:
        print(e)
        traceback.print_exc()

def cache_stories(keyword, stories):
    try:
        MemcachedClient.set(keyword, stories, time=2000) # 2000s - cache expiry time in SECONDS
        cached_keywords = MemcachedClient.get('cached_keywords')
        if cached_keywords is None:
            cached_keywords = Set()
        cached_keywords.add(keyword)
        MemcachedClient.set('cached_keywords', cached_keywords, time=172800) # 2-day expiry

    except Exception, e:
        print(e)
        traceback.print_exc()


def get_cached_daily_subscription_mysql():
    query = "SELECT data " \
        "FROM daily_stories " \
        "WHERE date=%s"
    today = datetime.strftime(datetime.date(datetime.now()), "%Y-%m-%d")
    args = (today,)

    try:
        conn = get_mysql_connection()
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

def get_cached_daily_subscription_memcached(story_type='top'):
    try:
        key = "today_stories_%s"%(story_type)
        return MemcachedClient.get(key)
        
    except Exception, e:
        print(e)
        traceback.print_exc()

def get_all_subscriptions(active=1):
    query = "SELECT keyword, GROUP_CONCAT(facebook_user_id) FROM subscriptions " \
            "WHERE active=%s " \
            "GROUP BY keyword"
    args = (active, )
    try:
        conn = get_mysql_connection()
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
            "WHERE keyword=%s AND active=1"
    args = (keyword, )
    try:
        conn = get_mysql_connection()
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
        conn = get_mysql_connection()
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
        conn = get_mysql_connection()
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
