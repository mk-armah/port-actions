from datetime import datetime, timedelta
import os
import base64
import json
import requests

PAGE_SIZE = 100

class DeploymentFrequency:
    def __init__(self, owner,repo, workflows, branch, number_of_days, pat_token=""):
        self.owner, self.repo = owner, repo
        self.workflow_url = "https://api.github.com/repos/{self.owner}/{self.repo}/actions/workflows"
        self.workflows = json.loads(workflows)
        self.branch = branch
        self.number_of_days = number_of_days
        self.pat_token = pat_token
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
        if not(self.workflows):
            response = requests.get(self.workflow_url, headers=self.auth_header)
            if response.status_code == 404:
                print("Repo is not found or you do not have access")
                exit()
            workflows = response.json()
            workflow_ids = [workflow['id'] for workflow in workflows['workflows']]
            print(f"Found {len(workflow_ids)} workflows in Repo")
        else:
            return self.workflows

    # async def send_api_request(
    #     self,
    #     endpoint: str,
    #     method: str = "GET",
    #     query_params: Optional[dict[str, Any]] = None,
    #     json_data: Optional[dict[str, Any]] = None,
    # ) -> dict[str, Any]:
    #     try:
    #         url = f"{self.api_url}/{endpoint}"
    #         logger.debug(
    #             f"URL: {url}, Method: {method}, Params: {query_params}, Body: {json_data}"
    #         )
    #         response = await self.http_client.request(
    #             method=method,
    #             url=url,
    #             params=query_params,
    #             json=json_data,
    #         )
    #         response.raise_for_status()
            
    #         logger.debug(f"Successfully retrieved data for endpoint: {endpoint}")

    #         return response.json()

    #     except httpx.HTTPStatusError as e:
    #         logger.error(
    #             f"HTTP error on {endpoint}: {e.response.status_code} - {e.response.text}"
    #         )
    #         raise
    #     except httpx.HTTPError as e:
    #         logger.error(f"HTTP error on {endpoint}: {str(e)}")
    #         raise
            
    # def fetch_workflow_runs(self):
    #     workflows_response = self.get_workflows()
    #     if self.workflows:
    #         workflow_ids = [workflow['id'] for workflow in workflows_response['workflows'] if workflow['name'] in self.workflows]
    #     else:
    #         workflow_ids = [workflow['id'] for workflow in workflows_response['workflows']]
    #         print(f"Found {len(workflows)} workflows in Repo")
    #     workflow_runs_list = []
    #     unique_dates = set()
    #     for workflow_id in workflow_ids:
    #         runs_url = f"{self.workflow_url}/{workflow_id}/runs?per_page={PAGE_SIZE}&status=completed"
    #         runs_response = requests.get(runs_url, headers=self.auth_header).json()
    #         for run in runs_response['workflow_runs']:
    #             run_date = datetime.strptime(run['created_at'], "%Y-%m-%dT%H:%M:%SZ")
    #             if run['head_branch'] == self.branch and run_date > datetime.now() - timedelta(days=self.number_of_days):
    #                 workflow_runs_list.append(run)
    #                 unique_dates.add(run_date.date())
    #     return workflow_runs_list, unique_dates

    # def calculate_deployments_per_day(self, workflow_runs_list):
    #     if self.number_of_days > 0:
    #         return len(workflow_runs_list) / self.number_of_days
    #     return 0

    def fetch_workflow_runs(self):
        workflows = self.get_workflows()
        workflow_runs_list = []
        unique_dates = set()
        for workflow_id in workflow_ids:
            runs_url = f"{self.workflow_url}/{workflow_id}/runs?per_page={PAGE_SIZE}&status=completed"
            runs_response = requests.get(runs_url, headers=self.auth_header).json()
            for run in runs_response['workflow_runs']:
                run_date = datetime.strptime(run['created_at'], "%Y-%m-%dT%H:%M:%SZ")
                if run['head_branch'] == self.branch and run_date > datetime.now() - timedelta(days=self.number_of_days):
                    workflow_runs_list.append(run)
                    unique_dates.add(run_date.date())
        return workflow_runs_list, unique_dates

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

        print(f"Owner/Repo: {self.owner}/{self.repo}")
        print(f"Workflows: {self.workflows}")
        print(f"Branch: {self.branch}")
        print(f"Number of days: {self.number_of_days}")
        print(f"Deployment frequency over the last {self.number_of_days} days is {deployments_per_day} per day")
        print(f"Rating: {rating} ({color})")
        return json.dumps(results, default=str)

if __name__ == "__main__":
    owner = os.getenv('OWNER')
    repo = os.getenv('REPOSITORY')
    pat_token = os.getenv('GITHUB_TOKEN')
    workflows = os.getenv('WORKFLOWS',"[]")
    branch = os.getenv('BRANCH',"main")
    time_frame = int(os.getenv('TIMEFRAME_IN_DAYS',30))
    
    df = DeploymentFrequency( owner,repo, workflows, branch, time_frame,pat_token)
    report = df.report()
    
    with open(os.getenv('GITHUB_ENV'), 'a') as github_env:
        github_env.write(f"deployment_frequency_report={report}\n")
