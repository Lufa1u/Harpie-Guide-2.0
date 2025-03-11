import random
import json
from datetime import datetime, timezone


def generate_basic_header():
    with open("./user_agents.txt", "r", encoding="utf-8") as file:
        user_agents = file.read().splitlines()

    user_agent = random.choice(user_agents)

    if "Windows" in user_agent:
        platform = "Windows"
    elif "Macintosh" in user_agent:
        platform = "Mac"
    else:
        platform = "Other"

    headers = {
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": f'"{platform}"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": user_agent
    }

    return json.dumps(headers, indent=4)



def get_current_time():
    return datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
