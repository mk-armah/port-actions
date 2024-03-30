import requests
from datetime import datetime, timedelta
import base64
import json
import os

PAGE_SIZE=100

class LeadTimeForChanges:
    def __init__(self,owner,repo, workflows, branch, number_of_days, commit_counting_method="last", pat_token=""):
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
        
        print(f"Owner/Repo: {self.owner}/{self.repo}")
        print(f"Number of days: {self.number_of_days}")
        print(f"Workflows: {self.workflows}")
        print(f"Branch: {self.branch}")
        print(f"Commit counting method '{self.commit_counting_method}' being used")
        
        pr_result = self.process_pull_requests()
        workflow_result = self.process_workflows()
    
        return evaluate_lead_time(pr_result, workflow_result)

    @property
    def get_auth_header(self):
        encoded_credentials = base64.b64encode(f":{self.pat_token}".encode()).decode()
        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/json",
        }
        return headers
    
    def get_pull_requests(self):
        url = f"{self.github_url}/pulls?state=all&head={self.branch}&per_page={PAGE_SIZE}&state=closed"
        response = requests.get(url, headers=self.auth_header)
        if response.status_code == 404:
            print("Repo is not found or you do not have access")
            exit()
        return response.json()
    
    def process_pull_requests(self):
        prs = get_pull_requests()
        pr_counter = 0
        total_pr_hours = 0
        for pr in prs:
            merged_at = pr.get('merged_at')
            if merged_at and datetime.strptime(merged_at, "%Y-%m-%dT%H:%M:%SZ") > datetime.utcnow() - timedelta(days=self.number_of_days):
                pr_counter += 1
                commits_url = f"https://api.github.com/repos/{self.owner}/{self.repo}/pulls/{pr['number']}/commits?per_page={PAGE_SIZE}"
                commits_response = requests.get(commits_url, headers=self.auth_header).json()
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
    
    def get_workflows(self,owner):
        if not(self.workflows):
            workflow_url = f"{self.github_url}/workflows"
            response = requests.get(workflow_url, headers=self.auth_header)
            if response.status_code == 404:
                print("Repo is not found or you do not have access")
                exit()
            workflows = response.json()
            workflow_ids = [workflow['id'] for workflow in workflows['workflows']]
            print(f"Found {len(workflow_ids)} workflows in Repo")
            return workflow_ids
        else:
            return self.workflows
    
    def process_workflows(self,workflows_response):
        workflows_ids = self.get_workflows()
        total_workflow_hours = 0
        workflow_counter = 0
        for workflow_id in workflow_ids:
            runs_url = f"{self.github_url}/actions/workflows/{workflow_id}/runs?per_page=100&status=completed"
            runs_response = requests.get(runs_url, headers=self.auth_header).json()
            for run in runs_response['workflow_runs']:
                if run['head_branch'] == branch and datetime.strptime(run['created_at'], "%Y-%m-%dT%H:%M:%SZ") > datetime.utcnow() - timedelta(days=self.number_of_days):
                    workflow_counter += 1
                    start_time = datetime.strptime(run['created_at'], "%Y-%m-%dT%H:%M:%SZ")
                    end_time = datetime.strptime(run['updated_at'], "%Y-%m-%dT%H:%M:%SZ")
                    duration = end_time - start_time
                    total_workflow_hours += duration.total_seconds() / 3600
        return workflow_counter, total_workflow_hours
    
    def calculate_rating(lead_time_for_changes_in_hours):
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
        print(f"PR average time duration: {pr_average} hours")
        print(f"Workflow average time duration: {workflow_average} hours")
        print(f"Lead time for changes in hours: {lead_time_for_changes_in_hours}")
    
        report = {
                "pr_average_time_duration" : round(pr_average,2),
                "workflow_average_time_duration" : round(workflow_average,2),
                "lead_time_for_changes_in_hours": round(lead_time_for_changes_in_hours,2)
        }
        rating = calculate_rating(lead_time_for_changes_in_hours)
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
