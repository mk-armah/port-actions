import httpx
from datetime import datetime, timedelta
import base64
import json
import os
import time
from loguru import logger
import asyncio

PAGE_SIZE = 100

async def send_api_request(url, headers, params=None):
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response

def with_pagination(func):
    async def wrapper(url, headers, params=None):
        items = []
        while url:
            response = await func(url, headers, params)
            items.extend(response.json())
            url = get_next_link_from_headers(response.headers)
        return items
    return wrapper

def with_rate_limit_handling(func):
    async def wrapper(url, headers, params=None):
        logger.info("URL AT RATE LIMIT FUNCTION",url)
        backoff_time = 1  # Starting backoff time in seconds
        max_backoff_time = 60  # Maximum backoff time in seconds
        while True:
            response = await func(url, headers, params)
            if response.status_code == 429:  # Rate limit exceeded
                reset_time = float(response.headers.get('X-RateLimit-Reset', 0))
                wait_time = max(reset_time - time.time(), 3)  # Ensure at least a 3-second wait
                logger.warning(f"Rate limit exceeded. Waiting for {wait_time} seconds.")
                await asyncio.sleep(wait_time)
            elif response.status_code in {500, 502, 503, 504}:
                logger.error(f"Server error ({response.status_code}). Retrying in {backoff_time} seconds.")
                await asyncio.sleep(backoff_time)
                backoff_time = min(backoff_time * 2, max_backoff_time)  # Exponential backoff
            else:
                return response
    return wrapper

def get_next_link_from_headers(headers):
    links = headers.get('Link', '')
    next_link = [link.split(';')[0].strip('<>') for link in links.split(',') if 'rel="next"' in link]
    return next_link[0] if next_link else None

@with_pagination
@with_rate_limit_handling
async def send_api_request_with_enhancements(url, headers, params=None):
    logger.info("URL AT SEND API REQUEST ENHANCEMENT", url)
    return await send_api_request(url, headers, params)

class LeadTimeForChanges:
    def __init__(self, owner, repo, workflows, branch, number_of_days, commit_counting_method="last", pat_token=""):
        self.owner = owner
        self.repo = repo
        self.workflows = json.loads(workflows)
        self.branch = branch
        self.number_of_days = number_of_days
        self.commit_counting_method = commit_counting_method
        self.pat_token = pat_token
        self.auth_header = {
            "Authorization": f"Basic {base64.b64encode(f':{pat_token}'.encode()).decode()}",
            "Content-Type": "application/json"
        }
        self.github_url = f"https://api.github.com/repos/{self.owner}/{self.repo}"

    async def __call__(self):
        logger.info(f"Owner/Repo: {self.owner}/{self.repo}")
        pr_result = await self.process_pull_requests()
        workflow_result = await self.process_workflows()
        return await self.evaluate_lead_time(pr_result, workflow_result)

    async def process_pull_requests(self):
        url = f"{self.github_url}/pulls"
        params = {"state": "closed", "head": self.branch, "per_page": PAGE_SIZE}
        prs = await send_api_request_with_enhancements(url, self.auth_header, params)
        pr_counter = 0
        total_pr_hours = 0
        for pr in prs:
            merged_at = pr.get('merged_at')
            if merged_at and datetime.strptime(merged_at, "%Y-%m-%dT%H:%M:%SZ") > datetime.utcnow() - timedelta(days=self.number_of_days):
                pr_counter += 1
                commits_url = f"{self.github_url}/pulls/{pr['number']}/commits"
                commits_response = await send_api_request_with_enhancements(commits_url, self.auth_header, {"per_page": PAGE_SIZE})
                if commits_response:
                    start_date = datetime.strptime(commits_response[-1]['commit']['committer']['date'], "%Y-%m-%dT%H:%M:%SZ") if self.commit_counting_method == "last" else datetime.strptime(commits_response[0]['commit']['committer']['date'], "%Y-%m-%dT%H:%M:%SZ")
                    merged_at = datetime.strptime(merged_at, "%Y-%m-%dT%H:%M:%SZ")
                    total_pr_hours += (merged_at - start_date).total_seconds() / 3600
        return pr_counter, total_pr_hours

    async def process_workflows(self):
        workflow_ids = self.workflows if self.workflows else await self.get_workflows()
        total_workflow_hours = 0
        workflow_counter = 0
        for workflow_id in workflow_ids:
            runs_url = f"{self.github_url}/actions/workflows/{workflow_id}/runs"
            runs_response = await send_api_request_with_enhancements(runs_url, self.auth_header, {"per_page": PAGE_SIZE, "status": "completed"})
            for run in runs_response:
                if run['head_branch'] == self.branch and datetime.strptime(run['created_at'], "%Y-%m-%dT%H:%M:%SZ") > datetime.utcnow() - timedelta(days=self.number_of_days):
                    workflow_counter += 1
                    total_workflow_hours += (datetime.strptime(run['updated_at'], "%Y-%m-%dT%H:%M:%SZ") - datetime.strptime(run['created_at'], "%Y-%m-%dT%H:%M:%SZ")).total_seconds() / 3600
        return workflow_counter, total_workflow_hours

    async def get_workflows(self):
        workflow_url = f"{self.github_url}/workflows"
        workflows = await send_api_request_with_enhancements(workflow_url, self.auth_header)
        return [workflow['id'] for workflow in workflows]

    async def evaluate_lead_time(self, pr_result, workflow_result):
        pr_counter, total_pr_hours = pr_result
        workflow_counter, total_workflow_hours = workflow_result
        pr_average = total_pr_hours / max(pr_counter, 1)
        workflow_average = total_workflow_hours / max(workflow_counter, 1)
        lead_time_for_changes_in_hours = pr_average + workflow_average
        report = {
            "pr_average_time_duration": round(pr_average, 2),
            "workflow_average_time_duration": round(workflow_average, 2),
            "lead_time_for_changes_in_hours": round(lead_time_for_changes_in_hours, 2),
            "rating": self.calculate_rating(lead_time_for_changes_in_hours)
        }
        logger.info(report)
        return json.dumps(report, default=str)

    def calculate_rating(self, lead_time_for_changes_in_hours):
        if lead_time_for_changes_in_hours < 1:
            return {"rating": "Elite", "color": "brightgreen"}
        elif lead_time_for_changes_in_hours <= 24:
            return {"rating": "High", "color": "green"}
        elif lead_time_for_changes_in_hours <= 168:
            return {"rating": "Medium", "color": "yellow"}
        else:
            return {"rating": "Low", "color": "red"}

if __name__ == "__main__":
    owner = os.getenv('OWNER')
    repo = os.getenv('REPOSITORY')
    token = os.getenv('GITHUB_TOKEN')  # Your personal access token or GitHub App token
    workflows = os.getenv('WORKFLOWS', "[]")
    branch = os.getenv('BRANCH', "main")
    time_frame = int(os.getenv('TIMEFRAME_IN_DAYS', 30))

    lead_time_for_changes = LeadTimeForChanges(owner, repo, workflows, branch, time_frame, pat_token=token)
    report = asyncio.run(lead_time_for_changes())
    with open(os.getenv('GITHUB_ENV'), 'a') as github_env:
        github_env.write(f"lead_time_for_changes_report={report}\n")
