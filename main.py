# main.py
import schedule, time, json, os
from scraper import get_news
from summarizer import summarize, send_texts
from responder import check_and_reply

STATE = "last_briefing.txt"

def morning_job():
    news = get_news()
    stories, briefing = summarize(news)
    send_texts(stories)
    open(STATE, "w").write(briefing)

def reply_job():
    if os.path.exists(STATE):
        check_and_reply(open(STATE).read())

schedule.every().day.at("07:00").do(morning_job)
schedule.every(5).minutes.do(reply_job)

while True:
    schedule.run_pending()
    time.sleep(30)