from apscheduler.schedulers.blocking import BlockingScheduler
import logging, os
import db as DB, FacebookAPI as FB
import config

def tick():
	print('Tick! The time is: %s' % datetime.now())

def send_daily_subscription():
	print "[Scheduled task] Send daily subscription"
	stories = DB.get_daily_top_stories()
	users = DB.get_subscribers_by_keyword('daily')
	
	try:
		for user_id in users:
			FB.send_message(config.PAT, user_id, "Here are today's top stories:")
			FB.send_stories(config.PAT, user_id, stories)

	except Exception, e:
		print(e)
		traceback.print_exc()

	print "[Scheduled task DONE] Sent daily subscription"


logging.basicConfig()
scheduler = BlockingScheduler()
scheduler.add_executor('threadpool')
if 'SCHED_HOUR' in os.environ:
	scheduler_hour = int(os.environ['SCHED_HOUR'])
else:
	scheduler_hour = 20

if 'SCHED_MIN' in os.environ:
	scheduler_min = int(os.environ['SCHED_MIN'])
else:
	scheduler_min = 48

job = scheduler.add_job(send_daily_subscription, 'cron', hour=scheduler_hour, minute=scheduler_min, id='job1')

try:
	print "[Scheduler started] Sends everyday at %s:%s"%(scheduler_hour, scheduler_min)
	scheduler.start()

except (KeyboardInterrupt, SystemExit):
	scheduler.remove_job('job1')
	scheduler.shutdown()
	print "Scheduler shutdown"