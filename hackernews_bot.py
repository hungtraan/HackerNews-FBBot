import sys, json, traceback
import HN_API as HN, FacebookAPI as FB, NLP, db as DB
from flask import Flask, request, current_app, url_for
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
import logging

application = Flask(__name__, instance_relative_config=True)
application.config.from_object('config')
application.config.from_pyfile('config.py', silent=True)	# Config for local development is found at: instance/config.py. This will overwrite configs in the previous line. The instance folder is ignored in .gitignore, so it won't be deployed to Heroku, in effect applying the production configs.

app = application

@app.route('/webhook', methods=['GET'])
def handle_verification():
	print "Handling Verification."
	if request.args.get('hub.verify_token', '') == app.config['OWN_WEBHOOK_TOKEN']:
		print "Webhook verified!"
		return request.args.get('hub.challenge', '')
	else:
		print "Wrong verification token!"

# ======================= Bot processing ===========================

@app.route('/webhook', methods=['POST'])
def handle_messages():
	payload = request.get_data()

	token = app.config['PAT']

	webhook_type = get_type_from_payload(payload)

	# Handle messages
	if webhook_type == 'postback':
		for sender_id, postback_payload in postback_events(payload):

			# Get user from DB
			user = DB.get_user(sender_id)

			if postback_payload == 'HELP_PAYLOAD':
				handle_help(sender_id)

			if postback_payload == 'GET_STARTED':				
				handle_first_time_user(user)
				offer_subscription(sender_id)
				
			elif postback_payload == 'SUBSCRIBE_DAILY_PAYLOAD':
				response = subscribe('daily', sender_id)
				
			elif postback_payload == 'SUBSCRIBE_WEEKLY_PAYLOAD':
				response = subscribe('weekly', sender_id)

			elif postback_payload == 'UNSUBSCRIBE_WEEKLY_PAYLOAD':
				response = unsubscribe(sender_id)

			if response:
				FB.send_message(token, sender_id, response)


	elif webhook_type == 'message':
		for sender_id, message in messaging_events(payload):
			user = DB.get_user(sender_id)
			
			# Only process message in here
			if not message:
				return "ok"

			# Start processing valid requests
			try:
				FB.show_typing(token, sender_id)
				response = processIncoming(sender_id, message)
				FB.show_typing(token, sender_id, 'typing_off')

				if response is not None and response != 'pseudo':
					# 'pseudo' is an "ok" signal for functions that sends response on their own
					# without returning anything back this function
					print response
					FB.send_message(token, sender_id, response)

				elif response != 'pseudo':
					FB.send_message(token, sender_id, "Sorry I don't understand that")

			except Exception, e:
				print e
				traceback.print_exc()
				FB.send_message(app.config['PAT'], sender_id, NLP.oneOf(NLP.error))
	return "ok"

def processIncoming(user_id, message):
	if message['type'] == 'text':
		message_text = message['data']
		if message_text == "news":
			stories = DB.get_daily_subscription()
			FB.send_stories(app.config['PAT'], user_id, stories)
		elif message_text == "Subscribe":
			return subscribe(user_id)
		else:
			FB.send_message(app.config['PAT'], user_id, "Just a sec, I'm looking that up...")
			stories = HN.stories_from_search(message_text)
			FB.send_stories(app.config['PAT'], user_id, stories)
		return "pseudo"
	# ==/ END Text message type =====================================================

	# Location message type =========================================================
	elif message['type'] == 'location':
		response = "I've received location (%s,%s) (y)"%(message['data'][0],message['data'][1])
		return response

	# ==/ END Location message type ==================================================

	# Audio message type =========================================================
	elif message['type'] == 'audio':
		audio_url = message['data']
		return "I've received your voice message" #%s"%(audio_url)

	# ==/ End Audio message type ====================================================

	# Unrecognizable incoming, remove context and reset all data to start afresh
	else:
		return "*scratch my head*"


# Get type of webhook
# Current support: message, postback
# Reference: https://developers.facebook.com/docs/messenger-platform/webhook-reference/message-received
def get_type_from_payload(payload):
	data = json.loads(payload)
	if "postback" in data["entry"][0]["messaging"][0]:
		return "postback"

	elif "message" in data["entry"][0]["messaging"][0]:
		return "message"

def postback_events(payload):
	data = json.loads(payload)
	
	postbacks = data["entry"][0]["messaging"]
	
	for event in postbacks:
		sender_id = event["sender"]["id"]
		postback_payload = event["postback"]["payload"]
		yield sender_id, postback_payload

# Generate tuples of (sender_id, message_text) from the provided payload.
# This part technically clean up received data to pass only meaningful data to processIncoming() function
def messaging_events(payload):
	
	data = json.loads(payload)
	
	messaging_events = data["entry"][0]["messaging"]
	
	for event in messaging_events:
		sender_id = event["sender"]["id"]

		# Not a message
		if "message" not in event:
			yield sender_id, None

		if "message" in event and "text" in event["message"] and "quick_reply" not in event["message"]:
			data = event["message"]["text"].encode('unicode_escape')
			yield sender_id, {'type':'text', 'data': data, 'message_id': event['message']['mid']}

		elif "attachments" in event["message"]:
			if "location" == event['message']['attachments'][0]["type"]:
				coordinates = event['message']['attachments'][
					0]['payload']['coordinates']
				latitude = coordinates['lat']
				longitude = coordinates['long']

				yield sender_id, {'type':'location','data':[latitude, longitude],'message_id': event['message']['mid']}

			elif "audio" == event['message']['attachments'][0]["type"]:
				audio_url = event['message'][
					'attachments'][0]['payload']['url']
				yield sender_id, {'type':'audio','data': audio_url, 'message_id': event['message']['mid']}
			
			else:
				yield sender_id, {'type':'text','data':"I don't understand this", 'message_id': event['message']['mid']}
		
		elif "quick_reply" in event["message"]:
			data = event["message"]["quick_reply"]["payload"]
			yield sender_id, {'type':'quick_reply','data': data, 'message_id': event['message']['mid']}
		
		else:
			yield sender_id, {'type':'text','data':"I don't understand this", 'message_id': event['message']['mid']}


def handle_help(user_id):
	intro = "I am your daily HackerNews aggregator"
	FB.send_message(app.config['PAT'], user_id, intro)
	FB.send_intro_screenshots(app, app.config['PAT'], user_id)

def handle_first_time_user(user):
	user_id = user['user_id']
	token = app.config['PAT']

	hi = "%s %s, nice to meet you :)"%(NLP.sayHiTimeZone(user), user['first_name'])
	FB.send_message(token, user_id, hi)

	FB.send_picture(app.config['PAT'], user_id, 'https://monosnap.com/file/I6WEAs2xvpZ5qTNmVauNguEzcaRrnI.png')
	
	handle_help(user_id)
	FB.send_message(app.config['PAT'], user_id, "Next time just tell me \"help\" to view this again :D")

def subscribe(sender_id, keyword='daily'):
	print("User %s subscribed to %s"%(sender_id, keyword))
	if DB.add_subscription(sender_id, keyword):
		return "You're now subscribed to %s updates! :D"%(keyword)

def unsubscribe(sender_id, keyword='daily'):
	print("User %s unsubscribed from %s"%(sender_id, keyword))
	if DB.remove_subscription(sender_id, keyword):
		return "You're now unsubscribed from %s updates! :D"%(keyword)
	
def get_all_subscriptions():
	return DB.get_all_subscriptions()

def tick():
	print('Tick! The time is: %s' % datetime.now())

def send_daily_subscription():
	# with app.app_context():
	# ctx = app.test_request_context('https://2c85143c.ngrok.io/')
	ctx = app.test_request_context('https://hacker-news-bot.herokuapp.com/')
	ctx.push()

	stories = DB.get_daily_subscription()
	users = DB.get_subscribers_by_keyword('daily')
	for user_id in users:
		FB.send_stories(app.config['PAT'], user_id, stories)

	ctx.pop()


# logging.basicConfig()
scheduler = BackgroundScheduler()
scheduler.add_executor('processpool')
# job = scheduler.add_job(send_daily_subscription, 'interval', seconds=10, id='job1')
job = scheduler.add_job(send_daily_subscription, 'cron', day_of_week='mon-sun', hour=3, minute=03, id='job1')
try:
	scheduler.start()
	print "Scheduler started"

except (KeyboardInterrupt, SystemExit):
	scheduler.remove_job('job1')
	scheduler.shutdown()

# Allows running with simple `python <filename> <port>`
if __name__ == '__main__':
	if len(sys.argv) == 2: # Allow running on customized ports
		app.run(port=int(sys.argv[1]))

	else:
		app.run() # Default port 5000