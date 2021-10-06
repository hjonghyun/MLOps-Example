from flask import Flask
import time
import os
from flask import request
import json

app = Flask(__name__)

kf_url = "http://your kubernetes cluster URL"
TRAIN_DATA_PATH="/data/mnist/train"
FAISS_TRAIN_DATA_PATH="/data/faiss/train"
DATA_INTERVAL = 1
NUM_TRAINED_DATA = [10005, 10007]
NUM_SEEKED_DATA = [0, 0]

from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()

def get_jobs():
    list_jobs = scheduler.get_jobs()
    return [str(job) + " Pending" if job.pending else str(job) + " Running" for job in list_jobs]


    
@app.route("/start")
def start():
    if scheduler.running:
        scheduler.resume()
    else:
        job_id = scheduler.add_job(exec_data, 'cron', second='*/59', id="data1")
        scheduler.start()
    
    return {"jobs": get_jobs()}



def seek_data(train_data_path, faiss_data_path):
    cnt_list = [count_files(train_data_path), count_files(faiss_data_path)]
    return cnt_list  

def count_files(folder):
    total = 0
    for root, dirs, files in os.walk(folder):
        total += len(files)
    return total




def exec_data():
    global NUM_SEEKED_DATA, NUM_TRAINED_DATA

    NUM_SEEKED_DATA = seek_data(TRAIN_DATA_PATH, FAISS_TRAIN_DATA_PATH)
    print("NUM_SEEKED_DATA")
    print(NUM_SEEKED_DATA[1])
    print("NUM_TRAINED_DATA")
    print(NUM_TRAINED_DATA[1])
    text = "{} new data for embedding and {} new data for faiss is detected".format(str(NUM_SEEKED_DATA[0] - NUM_TRAINED_DATA[0]), str(NUM_SEEKED_DATA[1] - NUM_TRAINED_DATA[1]))
    app.logger.info(text)

    if NUM_SEEKED_DATA[0] > NUM_TRAINED_DATA[0] + DATA_INTERVAL or NUM_SEEKED_DATA[1] > NUM_TRAINED_DATA[1] + DATA_INTERVAL:
        send_interactive_slack(text)    
    else:
        send_notice_slack(text, "No Need to Train!!!")
        

from slack_sdk.webhook import WebhookClient
webhook_url = "http://your slack webhook URL"
webhook = WebhookClient(webhook_url)

def send_interactive_slack(text):
    p = {
            "text": text,
            "attachments": [
                {
                    "text": "Would you like to train models?",
                    "fallback": "abcd",
                    "callback_id": "confirm",
                    "color": "#3AA3E3",
                    "attachment_type": "default",
                    "actions": [
                        {
                            "name": "answer",
                            "type": "button",
                            "text": "Train!",
                            "value": "train",
                            "confirm": {
                                "title": "Are you sure?",
                                "text": "Do Train?",
                                "ok_text": "Yes",
                                "dismiss_text": "No"
                            }
                        },
                        {
                            "name": "answer",
                            "type": "button",
                            "text": "Nope!",
                            "value": "nope"
                        }
                    ]
                }
            ]
    }
    webhook.send(text=p["text"], response_type="in_channel", attachments=p["attachments"])

def send_notice_slack(text, text2):
    p = {
            "text": text,
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": text
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": text2
                    }
                }
            ]
    }
    webhook.send(text=p["text"], blocks=p["blocks"])
    
@app.route("/actions", methods=["POST"])
def action():
    print("in actions")
    data = request.form["payload"]
    data = json.loads(data)
    answer = data["actions"][0]["value"]
    app.logger.info(answer)

    status = ""
    if answer == "train":
        global NUM_SEEKED_DATA, NUM_TRAINED_DATA
        NUM_TRAINED_DATA[0] = NUM_SEEKED_DATA[0]
        NUM_TRAINED_DATA[1] = NUM_SEEKED_DATA[1]

        send_notice_slack("Here is Kubeflow URL", "Kubeflow URL: {}".format(kf_url))

    return '', 204


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)