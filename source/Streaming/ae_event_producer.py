import os
import json
import random
import time
import uuid
from datetime import datetime, timezone

from azure.eventhub import EventHubProducerClient, EventData

CONNECTION_STR = os.environ["EVENTHUB_CONNECTION_STRING"]
EVENT_HUB_NAME = os.environ.get("EVENTHUB_NAME", "ae-events")

ORGS = [
    ("RXQ", "Buckinghamshire Healthcare NHS Trust"),
    ("RXW", "The Shrewsbury And Telford Hospital NHS Trust"),
    ("RA7", "University Hospitals Bristol And Weston NHS Foundation Trust"),
    ("RR8", "Leeds Teaching Hospitals NHS Trust"),
    ("RGM", "Royal Papworth Hospital NHS Foundation Trust"),
    ("RJZ", "King's College Hospital NHS Foundation Trust"),
    ("RTX", "University Hospitals of Morecambe Bay NHS Foundation Trust"),
    ("RL4", "The Royal Wolverhampton NHS Trust"),
    ("RXN", "Lancashire Teaching Hospitals NHS Foundation Trust"),
    ("RBS", "Alder Hey Children's NHS Foundation Trust"),
]

ATTENDANCE_TYPES = [1, 2, 3]
ATTENDANCE_WEIGHTS = [0.65, 0.15, 0.20]

AGE_BANDS = ["0-17", "18-24", "25-44", "45-64", "65-84", "85+"]
AGE_WEIGHTS = [0.18, 0.12, 0.22, 0.22, 0.18, 0.08]

GENDERS = ["Male", "Female", "Other"]
GENDER_WEIGHTS = [0.49, 0.49, 0.02]

DISPOSITIONS = ["Discharged", "Admitted", "Transferred", "Left before treatment"]
DISPOSITION_WEIGHTS = [0.68, 0.22, 0.06, 0.04]


def make_event():
    org_code, org_name = random.choice(ORGS)
    return {
        "event_id": str(uuid.uuid4()),
        "arrival_time": datetime.now(timezone.utc).isoformat(),
        "org_code": org_code,
        "org_name": org_name,
        "attendance_type": random.choices(ATTENDANCE_TYPES, ATTENDANCE_WEIGHTS)[0],
        "age_band": random.choices(AGE_BANDS, AGE_WEIGHTS)[0],
        "gender": random.choices(GENDERS, GENDER_WEIGHTS)[0],
        "disposition": random.choices(DISPOSITIONS, DISPOSITION_WEIGHTS)[0],
    }


def main():
    producer = EventHubProducerClient.from_connection_string(
        conn_str=CONNECTION_STR, eventhub_name=EVENT_HUB_NAME
    )
    print(f"Sending synthetic A&E events to '{EVENT_HUB_NAME}'. Ctrl+C to stop.")
    with producer:
        while True:
            batch = producer.create_batch()
            n = random.randint(1, 3)
            events = [make_event() for _ in range(n)]
            for event in events:
                batch.add(EventData(json.dumps(event)))
            producer.send_batch(batch)
            for event in events:
                print(f"sent: {event['org_code']} type={event['attendance_type']} at {event['arrival_time']}")
            time.sleep(3)


if __name__ == "__main__":
    main()
