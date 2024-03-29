import datetime
import pytz  # Make sure to install pytz if you haven't: pip install pytz
import os
import base64
import json
import requests

class DeploymentFrequency:
    def __init__(self, owner_repo, workflows, branch, number_of_days, pat_token=""):
        self.owner_repo = owner_repo
        self.workflows = workflows.split(',')
        self.branch = branch
        self.number_of_days = number_of_days
        self.pat_token = pat_token
        self.owner, self.repo_name = owner_repo.split('/')
        self.auth_header = self.get_auth_header

    @property
    def get_auth_header(self):
        encoded_credentials = base64.b64encode(f":{self.pat_token}".encode()).decode()
        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/json",
        }
        return headers
    
    def get_workflows(self):
        url = f"https://api.github.com/repos/{self.owner}/{self.repo_name}/actions/workflows"
        response = requests.get(url, headers=self.auth_header)
        if response.status_code == 404:
            print("Repo is not found or you do not have access")
            exit()
        return response.json()

    def fetch_workflow_runs(self):
        workflows_response = self.get_workflows()
        if self.workflows:
            workflow_ids = [workflow['id'] for workflow in workflows_response['workflows'] if workflow['name'] in self.workflows]
        else:
            workflow_ids = [workflow['id'] for workflow in workflows_response['workflows']]
            print(f"Found {len(workflows)} workflows in Repo")
        workflow_runs_list = []
        unique_dates = set()
        for workflow_id in workflow_ids:
            runs_url = f"https://api.github.com/repos/{owner}/{self.repo_name}/actions/workflows/{workflow_id}/runs?per_page=100&status=completed"
            runs_response = requests.get(runs_url, headers=self.auth_header).json()
            for run in runs_response['workflow_runs']:
                if run['head_branch'] == self.branch and datetime.strptime(run['created_at'], "%Y-%m-%dT%H:%M:%SZ") > datetime.utcnow() - timedelta(days=self.number_of_days):
                    workflow_runs_list.append(run)
                    unique_dates.add(run_date.date())
        return workflow_runs_list, unique_dates
                
    # def fetch_workflow_runs(self):
    #     workflow_runs_list = []
    #     unique_dates = set()
    #     now_utc = datetime.datetime.now(pytz.utc)

    #     for workflow_name in self.workflows:
    #         workflows = self.repo.get_workflows()
    #         for workflow in workflows:
    #             if workflow.name == workflow_name:
    #                 runs = workflow.get_runs(branch=self.branch)
    #                 for run in runs:
    #                     run_date = run.created_at.replace(tzinfo=pytz.utc)
    #                     if run_date > now_utc - datetime.timedelta(days=self.number_of_days):
    #                         workflow_runs_list.append(run)
    #                         unique_dates.add(run_date.date())

    #     return workflow_runs_list, unique_dates

    def calculate_deployments_per_day(self, workflow_runs_list):
        if self.number_of_days > 0:
            return len(workflow_runs_list) / self.number_of_days
        return 0

    def compute_rating(self, deployments_per_day):
        daily_deployment = 1
        weekly_deployment = 1 / 7
        monthly_deployment = 1 / 30
        yearly_deployment = 1 / 365

        if deployments_per_day > daily_deployment:
            return "Elite", "brightgreen"
        elif weekly_deployment <= deployments_per_day <= daily_deployment:
            return "High", "green"
        elif monthly_deployment <= deployments_per_day < weekly_deployment:
            return "Medium", "yellow"
        elif yearly_deployment < deployments_per_day < monthly_deployment:
            return "Low", "red"
        else:
            return "None", "lightgrey"

    def report(self):
        workflow_runs_list, unique_dates = self.fetch_workflow_runs()
        deployments_per_day = self.calculate_deployments_per_day(workflow_runs_list)
        rating, color = self.compute_rating(deployments_per_day)

        results = {
            "deployment_frequency": round(deployments_per_day, 2),
            "rating": rating,
            "number_of_unique_deployment_days": len(unique_dates),
            "total_deployments": len(workflow_runs_list)
        }

        print(f"Owner/Repo: {self.owner}/{self.repo_name}")
        print(f"Workflows: {', '.join(self.workflows)}")
        print(f"Branch: {self.branch}")
        print(f"Number of days: {self.number_of_days}")
        print(f"Deployment frequency over the last {self.number_of_days} days is {deployments_per_day} per day")
        print(f"Rating: {rating} ({color})")
        return json.dumps(results, default=str)

if __name__ == "__main__":
    owner_repo = os.getenv('REPOSITORY')
    token = os.getenv('GITHUB_TOKEN')  # Your personal access token or GitHub App token
    workflows = os.getenv('WORKFLOWS')
    branch = 'main'
    time_frame = int(os.getenv('TIMEFRAME_IN_DAYS'))
    number_of_days = 30 if not time_frame else time_frame
    
    df = DeploymentFrequency(owner_repo,workflows, branch, number_of_days, pat_token=token)
    report = df.report()
    
    with open(os.getenv('GITHUB_ENV'), 'a') as github_env:
        github_env.write(f"deployment_frequency_report={report}\n")
