import datetime
import os
import base64
import json
import httpx
from loguru import logger
import asyncio

PAGE_SIZE = 100


class DeploymentFrequency:
    def __init__(self, owner, repo, workflows, branch, number_of_days, pat_token=""):
        self.owner, self.repo = owner, repo
        self.workflow_url = (
            f"https://api.github.com/repos/{self.owner}/{self.repo}/actions/workflows"
        )
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

    # async def send_api_requests(self, url, params=None):
    #     async with httpx.AsyncClient() as client:
    #         try:
    #             response = await client.get(
    #                 url, headers=self.auth_header, params=params
    #             )
    #             response.raise_for_status()
    #             return response.json()
    #         except httpx.HTTPStatusError as e:
    #             logger.error(f"HTTP error occurred: {e.response.status_code}")
    #         except Exception as e:
    #             logger.error(f"An error occurred: {e}")

    async def send_api_requests(self, url, params=None):
        backoff_time = 1
        max_backoff_time = 60

        async with httpx.AsyncClient() as client:
            while True:
                try:
                    response = await client.get(
                        url, headers=self.auth_header, params=params
                    )

                    if response.status_code == 429 or response.status_code == 403:
                        reset_time = float(response.headers.get("X-RateLimit-Reset", 0))
                        current_time = time.time()
                        wait_time = max(reset_time - current_time, 3)
                        logger.warning(
                            f"Rate limit exceeded. Waiting for {wait_time} seconds."
                        )
                        await asyncio.sleep(wait_time)
                        continue

                    response.raise_for_status()
                    return response.json()

                except httpx.HTTPStatusError as e:
                    if e.response.status_code in {500, 502, 503, 504}:
                        logger.warning(
                            f"Server error ({e.response.status_code}). Retrying in {backoff_time} seconds."
                        )
                        await asyncio.sleep(backoff_time)
                        backoff_time = min(backoff_time * 2, max_backoff_time)
                    else:
                        logger.error(f"HTTP error occurred: {e.response.status_code}")
                        break

                except Exception as e:
                    logger.error(f"An error occurred: {e}")
                    break

    async def get_workflows(self):
        if not (self.workflows):
            workflows = await self.send_api_requests(self.workflow_url)
            if workflows:
                workflow_ids = [workflow["id"] for workflow in workflows["workflows"]]
                logger.info(f"Found {len(workflow_ids)} workflows in Repo")
                return workflow_ids
        else:
            return self.workflows

    async def fetch_workflow_runs(self):
        workflow_ids = await self.get_workflows()
        workflow_runs_list = []
        unique_dates = set()
        for workflow_id in workflow_ids:
            runs_url = f"{self.workflow_url}/{workflow_id}/runs"
            params = {"per_page": PAGE_SIZE, "status": "completed"}
            runs_response = await self.send_api_requests(runs_url, params=params)
            for run in runs_response["workflow_runs"]:
                run_date = datetime.datetime.strptime(
                    run["created_at"], "%Y-%m-%dT%H:%M:%SZ"
                )
                if run[
                    "head_branch"
                ] == self.branch and run_date > datetime.datetime.now() - datetime.timedelta(
                    days=self.number_of_days
                ):
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

    async def __call__(self):
        workflow_runs_list, unique_dates = await self.fetch_workflow_runs()
        deployments_per_day = self.calculate_deployments_per_day(workflow_runs_list)
        rating, color = self.compute_rating(deployments_per_day)

        logger.info(f"Owner/Repo: {self.owner}/{self.repo}")
        logger.info(f"Workflows: {self.workflows}")
        logger.info(f"Branch: {self.branch}")
        logger.info(f"Number of days: {self.number_of_days}")
        logger.info(
            f"Deployment frequency over the last {self.number_of_days} days is {deployments_per_day} per day"
        )
        logger.info(f"Rating: {rating} ({color})")

        print("Unique Dates", unique_dates)
        return json.dumps(
            {
                "deployment_frequency": round(deployments_per_day, 2),
                "rating": rating,
                "number_of_unique_deployment_days": len(unique_dates),
                "number_of_unique_deployment_month":len(unique_months = {date.month for date in unique_dates}),
                "number_of_unique_deployment_weeks": len({date.isocalendar()[1] for date in unique_dates})
                "total_deployments": len(workflow_runs_list),
            },
            default=str,
        )


if __name__ == "__main__":
    owner = os.getenv("OWNER")
    repo = os.getenv("REPOSITORY")
    pat_token = os.getenv("GITHUB_TOKEN")
    workflows = os.getenv("WORKFLOWS", "[]")
    branch = os.getenv("BRANCH", "main")
    time_frame = int(os.getenv("TIMEFRAME_IN_DAYS", 30))

    deployment_frequency = DeploymentFrequency(
        owner, repo, workflows, branch, time_frame, pat_token
    )
    report = asyncio.run(deployment_frequency())

    with open(os.getenv("GITHUB_ENV"), "a") as github_env:
        github_env.write(f"deployment_frequency_report={report}\n")
