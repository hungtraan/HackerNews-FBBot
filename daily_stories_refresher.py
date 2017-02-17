from apscheduler.schedulers.blocking import BlockingScheduler
import db as DB
import logging, os

logging.basicConfig()
sched = BlockingScheduler()

if 'DAILY_STORIES_REFRESH_EVERY_X_MINUTES' in os.environ:
	interval = int(os.environ['DAILY_STORIES_REFRESH_EVERY_X_MINUTES'])
else:
	interval = 1

@sched.scheduled_job('interval', minutes=interval)
def daily_stories_refresher():
    print "Starting caching process [1/2]: Top stories"
    # print('This job is run every 15 minutes.')
    DB.cache_today_stories_memcached(None, 'top')
    print "Today's [top] stories cached\n"

    print "Starting caching process [2/2]: Best stories"
    DB.cache_today_stories_memcached(None, 'best')
    print "Today's [best] stories cached"

# @sched.scheduled_job('cron', day_of_week='mon-fri', hour=17)
# def scheduled_job():
#     print('This job is run every weekday at 5pm.')

print "Daily Stories Refresher started, refreshes every %d seconds"%(interval*60)
sched.start()
