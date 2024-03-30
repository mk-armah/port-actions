import httpx
from datetime import datetime, timedelta
import base64
import json
import os
from loguru import logger

PAGE_SIZE = 100

class LeadTimeForChanges:
    def __init__(self, owner, repo, workflows, branch, number_of_days, commit_counting_method="last", pat_token=""):
        self.owner = owner
        self.repo = repo
        self.workflows = json.loads(workflows)
        self.branch = branch
        self.number_of_days = number_of_days
        self.commit_counting_method = commit_counting_method
        self.pat_token = pat_token
        self.auth_header = self.get_auth_header
        self.github_url = f"https://api.github.com/repos/{self.owner}/{self.repo}"

    def __call__(self):
        
        logger.info(f"Owner/Repo: {self.owner}/{self.repo}")
        logger.info(f"Number of days: {self.number_of_days}")
        logger.info(f"Workflows: {self.workflows}")
        logger.info(f"Branch: {self.branch}")
        logger.info(f"Commit counting method '{self.commit_counting_method}' being used")
        
        pr_result = self.process_pull_requests()
        workflow_result = self.process_workflows()
    
        return self.evaluate_lead_time(pr_result, workflow_result)

    @property
    def get_auth_header(self):
        encoded_credentials = base64.b64encode(f":{self.pat_token}".encode()).decode()
        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/json",
        }
        return headers
    
    async def send_api_requests(self, url, params=None):
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self.auth_header, params=params)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error occurred: {e.response.status_code}")
            except Exception as e:
                logger.error(f"An error occurred: {e}")

    async def get_pull_requests(self):
        url = f"{self.github_url}/pulls"
        params = {"state": "closed", "head": self.branch, "per_page": PAGE_SIZE}
        return await self.send_api_requests(url, params=params)
    
    async def process_pull_requests(self):
        prs = await self.get_pull_requests()
        pr_counter = 0
        total_pr_hours = 0
        for pr in prs:
            merged_at = pr.get('merged_at')
            if merged_at and datetime.strptime(merged_at, "%Y-%m-%dT%H:%M:%SZ") > datetime.utcnow() - timedelta(days=self.number_of_days):
                pr_counter += 1
                commits_url = f"{self.github_url}/pulls/{pr['number']}/commits"
                params = {"per_page": PAGE_SIZE}
                commits_response = await self.send_api_requests(commits_url, params=params)
                if commits_response:
                    if self.commit_counting_method == "last":
                        start_date = commits_response[-1]['commit']['committer']['date']
                    elif self.commit_counting_method == "first":
                        start_date = commits_response[0]['commit']['committer']['date']
                    start_date = datetime.strptime(start_date, "%Y-%m-%dT%H:%M:%SZ")
                    merged_at = datetime.strptime(merged_at, "%Y-%m-%dT%H:%M:%SZ")
                    duration = merged_at - start_date
                    total_pr_hours += duration.total_seconds() / 3600
        return pr_counter, total_pr_hours
    
    async def get_workflows(self):
        if not(self.workflows):
            workflow_url = f"{self.github_url}/workflows"
            workflows = await self.send_api_requests(workflow_url)
            if workflows:
                workflow_ids = [workflow['id'] for workflow in workflows['workflows']]
                logger.info(f"Found {len(workflow_ids)} workflows in Repo")
                return workflow_ids
        else:
            return self.workflows
    
    async def process_workflows(self):
        workflow_ids = await self.get_workflows()
        total_workflow_hours = 0
        workflow_counter = 0
        for workflow_id in workflow_ids:
            runs_url = f"{self.github_url}/actions/workflows/{workflow_id}/runs"
            params = {"per_page": 100, "status": "completed"}
            runs_response = await self.send_api_requests(runs_url, params=params)
            for run in runs_response['workflow_runs']:
                if run['head_branch'] == self.branch and datetime.strptime(run['created_at'], "%Y-%m-%dT%H:%M:%SZ") > datetime.utcnow() - timedelta(days=self.number_of_days):
                    workflow_counter += 1
                    start_time = datetime.strptime(run['created_at'], "%Y-%m-%dT%H:%M:%SZ")
                    end_time = datetime.strptime(run['updated_at'], "%Y-%m-%dT%H:%M:%SZ")
                    duration = end_time - start_time
                    total_workflow_hours += duration.total_seconds() / 3600
        return workflow_counter, total_workflow_hours
    
    def calculate_rating(self,lead_time_for_changes_in_hours):
        daily_deployment=24
        weekly_deployment=24*7
        monthly_deployment=24*30
        every_six_months_deployment=24*30*6
        
        if lead_time_for_changes_in_hours <= 0:
            rating = "None"
            color = "lightgrey"
        elif lead_time_for_changes_in_hours < 1:
            rating = "Elite"
            color = "brightgreen"
        elif lead_time_for_changes_in_hours <= daily_deployment:
            rating = "Elite"
            color = "brightgreen"
        elif daily_deployment < lead_time_for_changes_in_hours <= weekly_deployment:
            rating = "High"
            color = "green"
        elif weekly_deployment < lead_time_for_changes_in_hours <= monthly_deployment:
            rating = "High"
            color = "green"
        elif monthly_deployment < lead_time_for_changes_in_hours <= every_six_months_deployment:
            rating = "Medium"
            color = "yellow"
        else: 
            # lead_time_for_changes_in_hours > every_six_months_deployment
            rating = "Low"
            color = "red"
            
        display_metric = round(lead_time_for_changes_in_hours, 2)
        display_unit = "hours"
            
        return {
            "rating": rating,
            "color": color,
            "display_metric": display_metric,
            "display_unit": display_unit
        }
    
    
    def evaluate_lead_time(self,pr_result, workflow_result):
        pr_counter, total_pr_hours = pr_result
        workflow_counter, total_workflow_hours = workflow_result
        if pr_counter == 0:
            pr_counter = 1
        if workflow_counter == 0:
            workflow_counter = 1
        pr_average = total_pr_hours / pr_counter
        workflow_average = total_workflow_hours / workflow_counter
        lead_time_for_changes_in_hours = pr_average + workflow_average
        logger.info(f"PR average time duration: {pr_average} hours")
        logger.info(f"Workflow average time duration: {workflow_average} hours")
        logger.info(f"Lead time for changes in hours: {lead_time_for_changes_in_hours}")
    
        report = {
                "pr_average_time_duration" : round(pr_average,2),
                "workflow_average_time_duration" : round(workflow_average,2),
                "lead_time_for_changes_in_hours": round(lead_time_for_changes_in_hours,2)
        }
        rating = self.calculate_rating(lead_time_for_changes_in_hours)
        report.update(rating)
    
        return json.dumps(report, default=str)
    
if __name__ == "__main__":
    owner = os.getenv('OWNER')
    repo = os.getenv('REPOSITORY')
    token = os.getenv('GITHUB_TOKEN')  # Your personal access token or GitHub App token
    workflows = os.getenv('WORKFLOWS',"[]")
    branch = os.getenv('BRANCH',"main")
    time_frame = int(os.getenv('TIMEFRAME_IN_DAYS',30))

    lead_time_for_changes = LeadTimeForChanges(owner,repo, workflows, branch, time_frame, pat_token=token)
    report = lead_time_for_changes()
    with open(os.getenv('GITHUB_ENV'), 'a') as github_env:
        github_env.write(f"lead_time_for_changes_report={report}\n")
